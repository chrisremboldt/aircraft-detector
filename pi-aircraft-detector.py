#!/usr/bin/env python3
"""
Aircraft Detection System for Raspberry Pi

This system creates a visual "radar" to detect aircraft in flight by identifying
small, high-contrast moving objects against the sky. It uses a standard
Raspberry Pi camera (any revision) accessed via OpenCV for frame capture.

Architecture:
1. Camera Module: Raspberry Pi camera module
2. Processing Unit: Raspberry Pi (4 recommended for performance)
3. Computer Vision: OpenCV for image processing and detection
4. Data Storage: Local SQLite database for detection logging
5. Visualization: Optional web interface for monitoring detections

Requirements:
- Raspberry Pi (4 or newer recommended)
- Raspberry Pi camera module (any revision)
- Python 3.7+
- OpenCV 4.x
- SQLite3
- Flask (for optional web interface)
"""

import cv2
import numpy as np
import time
import os
import datetime
import threading
import argparse
import logging
from flask import Flask, Response, render_template
import json
import math

from rpi_camera import RPiCamera as Camera
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aircraft_detector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables
detected_aircraft = []
current_frame = None
detection_active = False
db_path = "aircraft_detections.db"

class AircraftTracker:
    """Tracks detected aircraft across multiple frames"""
    
    def __init__(self, max_disappeared=50, max_distance=50):
        self.next_object_id = 0
        self.objects = {}  # Dictionary of tracked objects {ID: centroid}
        self.disappeared = {}  # Dictionary tracking frames since last seen
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        
    def register(self, centroid):
        """Register a new object with the next available ID"""
        self.objects[self.next_object_id] = {
            "centroid": centroid,
            "first_seen": datetime.datetime.now(),
            "trajectory": [centroid],
            "speed": 0,
            "direction": 0
        }
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1
        
    def deregister(self, object_id):
        """Deregister an object that has disappeared for too long"""
        del self.objects[object_id]
        del self.disappeared[object_id]
        
    def update(self, centroids):
        """Update tracked objects with new centroids"""
        # If no centroids, mark all objects as disappeared
        if len(centroids) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects
        
        # If no existing objects, register all new centroids
        if len(self.objects) == 0:
            for centroid in centroids:
                self.register(centroid)
        else:
            # Match existing objects to new centroids
            object_ids = list(self.objects.keys())
            object_centroids = [obj["centroid"] for obj in self.objects.values()]
            
            # Calculate distances between each pair of objects and centroids
            distances = {}
            for i, object_id in enumerate(object_ids):
                distances[object_id] = {}
                for j, centroid in enumerate(centroids):
                    distances[object_id][j] = np.linalg.norm(
                        np.array(object_centroids[i]) - np.array(centroid)
                    )
                    
            # Find the smallest distance for each object
            assigned_centroids = set()
            for object_id in object_ids:
                if not distances[object_id]:  # Skip if no distances for this object
                    continue
                    
                # Find the closest centroid that hasn't been assigned yet
                min_distance = float('inf')
                min_index = None
                
                for j, distance in distances[object_id].items():
                    if j not in assigned_centroids and distance < min_distance:
                        min_distance = distance
                        min_index = j
                
                # If we found a centroid within the maximum distance
                if min_index is not None and min_distance < self.max_distance:
                    # Update the object with the new centroid
                    old_centroid = self.objects[object_id]["centroid"]
                    self.objects[object_id]["centroid"] = centroids[min_index]
                    self.objects[object_id]["trajectory"].append(centroids[min_index])
                    
                    # Calculate speed and direction
                    if len(self.objects[object_id]["trajectory"]) > 1:
                        dx = centroids[min_index][0] - old_centroid[0]
                        dy = centroids[min_index][1] - old_centroid[1]
                        self.objects[object_id]["speed"] = math.sqrt(dx**2 + dy**2)
                        self.objects[object_id]["direction"] = math.degrees(math.atan2(dy, dx))
                    
                    # Reset the disappeared counter
                    self.disappeared[object_id] = 0
                    
                    # Mark this centroid as assigned
                    assigned_centroids.add(min_index)
                else:
                    # No suitable centroid found, increment disappeared counter
                    self.disappeared[object_id] += 1
            
            # Register any centroids that weren't matched
            for i, centroid in enumerate(centroids):
                if i not in assigned_centroids:
                    self.register(centroid)
                    
        # Deregister objects that have disappeared for too long
        for object_id in list(self.disappeared.keys()):
            if self.disappeared[object_id] > self.max_disappeared:
                self.deregister(object_id)
                
        return self.objects



class ImageProcessor:
    """Processes camera frames to detect aircraft"""
    
    def __init__(self, min_area=25, contrast_threshold=50, confidence_threshold=0.6):
        self.min_area = min_area  # Minimum contour area to consider
        self.contrast_threshold = contrast_threshold  # Minimum contrast difference
        self.confidence_threshold = confidence_threshold  # Detection confidence threshold
        self.prev_gray = None  # Previous frame for motion detection
        self.tracker = AircraftTracker()  # Aircraft tracking across frames
        self.frame_count = 0  # Count of processed frames
        
    def detect_sky(self, frame):
        """
        Detect the sky region in the frame
        Returns a binary mask where sky pixels are white (255)
        """
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Sky is typically blue with high value and relatively low saturation
        # Adjust these thresholds based on your specific conditions
        lower_blue = np.array([90, 30, 120])
        upper_blue = np.array([140, 255, 255])
        
        # Create a mask for blue regions
        sky_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Morphological operations to clean up the mask
        kernel = np.ones((5, 5), np.uint8)
        sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_OPEN, kernel)
        sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_CLOSE, kernel)
        
        return sky_mask
        
    def process_frame(self, frame):
        """
        Process a single frame to detect aircraft
        Returns the annotated frame and a list of detections
        """
        self.frame_count += 1
        detections = []
        
        # Skip if frame is None
        if frame is None:
            return frame, detections
            
        # Create a copy of the frame for annotations
        annotated_frame = frame.copy()
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Detect sky region
        sky_mask = self.detect_sky(frame)
        
        # Initialize previous frame if not available
        if self.prev_gray is None:
            self.prev_gray = gray.copy()
            return annotated_frame, detections
            
        # Motion detection: calculate absolute difference between frames
        frame_delta = cv2.absdiff(self.prev_gray, gray)
        
        # Apply threshold to highlight significant changes
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Dilate thresholded image to fill in holes
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Apply sky mask to focus only on motion in the sky
        thresh = cv2.bitwise_and(thresh, thresh, mask=sky_mask)
        
        # Find contours of moving objects
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # List to store centroids of detected objects
        centroids = []
        
        # Process each contour
        for contour in contours:
            # Filter by contour area - adjust minimum size as needed
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
                
            # Get bounding box
            (x, y, w, h) = cv2.boundingRect(contour)
            
            # Calculate centroid
            centroid_x = int(x + w/2)
            centroid_y = int(y + h/2)
            
            # Skip if not in sky region
            if sky_mask[centroid_y, centroid_x] == 0:
                continue
                
            # Calculate contrast ratio in the region
            roi = gray[y:y+h, x:x+w]
            min_val, max_val, _, _ = cv2.minMaxLoc(roi)
            contrast = max_val - min_val
            
            # Only mark high-contrast moving objects
            if contrast > self.contrast_threshold:
                # Calculate confidence based on contrast and size
                confidence = min(1.0, (contrast / 255) * (area / 100))
                
                if confidence >= self.confidence_threshold:
                    # Add centroid to list for tracking
                    centroids.append((centroid_x, centroid_y))
                    
                    # Store detection
                    detections.append({
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                        "centroid": (centroid_x, centroid_y),
                        "contrast": contrast,
                        "confidence": confidence,
                        "area": area
                    })
        
        # Update aircraft tracker
        tracked_objects = self.tracker.update(centroids)
        
        # Draw tracking objects on frame
        for object_id, object_data in tracked_objects.items():
            centroid = object_data["centroid"]
            speed = object_data["speed"]
            direction = object_data["direction"]
            
            # Draw centroid and ID
            cv2.circle(annotated_frame, centroid, 4, (0, 255, 0), -1)
            cv2.putText(annotated_frame, f"ID: {object_id}", 
                       (centroid[0] - 10, centroid[1] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                       
            # Draw trajectory
            trajectory = object_data["trajectory"]
            if len(trajectory) > 1:
                for i in range(1, len(trajectory)):
                    cv2.line(annotated_frame, trajectory[i-1], trajectory[i], (0, 255, 0), 2)
                    
            # Add speed and direction info
            cv2.putText(annotated_frame, 
                       f"Spd: {speed:.1f} Dir: {direction:.0f}°", 
                       (centroid[0] - 10, centroid[1] + 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw detections on frame
        for detection in detections:
            x, y, w, h = detection["x"], detection["y"], detection["width"], detection["height"]
            
            # Draw rectangle around aircraft
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            
            # Draw detection info
            cv2.putText(annotated_frame, 
                       f"Aircraft? (Conf: {detection['confidence']:.2f})", 
                       (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Update previous frame
        self.prev_gray = gray.copy()
        
        # Add frame info
        cv2.putText(annotated_frame, 
                   f"Frame: {self.frame_count} | Detections: {len(detections)}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return annotated_frame, detections

class WebInterface:
    """Optional web interface for viewing detections"""
    
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.setup_routes()
        
    def setup_routes(self):
        """Set up Flask routes"""
        @self.app.route('/')
        def index():
            return render_template('index.html')
            
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.generate_frames(),
                           mimetype='multipart/x-mixed-replace; boundary=frame')
                           
        @self.app.route('/detections')
        def get_detections():
            db = Database(db_path)
            db.initialize()
            detections = db.get_recent_detections(100)
            db.close()
            return json.dumps(detections)
            
    def generate_frames(self):
        """Generate video frames for streaming"""
        while True:
            if current_frame is not None:
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', current_frame)
                if not ret:
                    continue
                    
                # Yield the frame in the correct format for Flask streaming response
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                      
            time.sleep(0.1)  # Small delay to reduce CPU usage
            
    def start(self):
        """Start the web server in a separate thread"""
        threading.Thread(target=lambda: self.app.run(
            host=self.host, port=self.port, debug=False
        ), daemon=True).start()
        logger.info(f"Web interface started at http://{self.host}:{self.port}")

def save_detection_image(frame, detection, output_dir="detections"):
    """Save an image of a detected aircraft"""
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{output_dir}/aircraft_{timestamp}.jpg"
    
    # Extract region with some padding
    x, y, w, h = detection["x"], detection["y"], detection["width"], detection["height"]
    padding = 50
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(frame.shape[1], x + w + padding)
    y2 = min(frame.shape[0], y + h + padding)
    
    # Save cropped image
    try:
        cv2.imwrite(filename, frame[y1:y2, x1:x2])
        logger.info(f"Saved detection image to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save detection image: {e}")
        return None

def main():
    """Main function to run the aircraft detection system"""
    global current_frame, detection_active
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Aircraft Detection System')
    parser.add_argument('--display', action='store_true', help='Display video feed')
    parser.add_argument('--web', action='store_true', help='Enable web interface')
    parser.add_argument('--web-port', type=int, default=8080, help='Web interface port')
    parser.add_argument('--save-detections', action='store_true', help='Save detection images')
    parser.add_argument('--min-area', type=int, default=25, help='Minimum contour area')
    parser.add_argument('--contrast-threshold', type=int, default=50, help='Minimum contrast')
    parser.add_argument('--confidence-threshold', type=float, default=0.6, help='Detection confidence threshold')
    args = parser.parse_args()
    
    # Initialize camera
    camera = Camera()
    if not camera.initialize():
        logger.error("Failed to initialize camera. Exiting.")
        return

    # Initialize database
    db = Database(db_path)
    if not db.initialize():
        logger.error("Failed to initialize database. Exiting.")
        camera.release()
        return
    
    # Initialize image processor
    processor = ImageProcessor(
        min_area=args.min_area,
        contrast_threshold=args.contrast_threshold,
        confidence_threshold=args.confidence_threshold
    )
    
    # Start web interface if requested
    if args.web:
        web = WebInterface(port=args.web_port)
        web.start()
    
    detection_active = True
    
    try:
        while detection_active:
            # Capture frame
            frame = camera.capture_frame()
            if frame is None:
                logger.warning("Failed to capture frame. Retrying...")
                time.sleep(1)
                continue
            
            # Process frame
            annotated_frame, detections = processor.process_frame(frame)
            
            # Update global current frame for web interface
            current_frame = annotated_frame
            
            # Record detections in database
            for detection in detections:
                # Save detection image if requested
                image_path = None
                if args.save_detections:
                    image_path = save_detection_image(frame, detection)
                
                # Record in database
                db.record_detection(
                    detection["x"], 
                    detection["y"], 
                    detection["width"], 
                    detection["height"], 
                    detection["contrast"], 
                    detection["confidence"],
                    image_path
                )
            
            # Display frame if requested
            if args.display:
                cv2.imshow('Aircraft Detector', annotated_frame)
                
                # Break on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    
    except KeyboardInterrupt:
        logger.info("Detection stopped by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # Cleanup
        detection_active = False
        camera.release()
        db.close()
        
        if args.display:
            cv2.destroyAllWindows()
        
        logger.info("Aircraft detection system stopped")

if __name__ == "__main__":
    main()