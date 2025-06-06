#!/usr/bin/env python3
"""
Aircraft Detection System for Raspberry Pi

This system creates a visual "radar" to detect aircraft in flight by identifying
small, high-contrast moving objects against the sky. Frames are captured using
the libcamera stack through the Picamera2 library (OpenCV is only used for
image processing).

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
import json
import math
import requests
import web_interface
from web_interface import WebInterface

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
db_path = "aircraft_detections.db"

class ADSBIntegration:
    def __init__(self, adsb_url="http://localhost:8080/data/aircraft.json"):
        self.adsb_url = adsb_url
        self.camera_lat = None
        self.camera_lon = None

    def get_nearby_aircraft(self, max_distance_nm=50):
        try:
            response = requests.get(self.adsb_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                aircraft_list = data.get('aircraft', [])
                filtered = []
                for ac in aircraft_list:
                    if self._is_valid_aircraft(ac, max_distance_nm):
                        filtered.append(self._format_aircraft_data(ac))
                return filtered
        except Exception as e:
            print(f"ADS-B API error: {e}")
        return []

    def _is_valid_aircraft(self, aircraft, max_distance_nm):
        if aircraft.get('seen_pos', 999) > 60:
            return False
        if not aircraft.get('alt_baro') or aircraft.get('alt_baro') < 500:
            return False
        if self.camera_lat and self.camera_lon and 'lat' in aircraft and 'lon' in aircraft:
            distance = self._calculate_distance(self.camera_lat, self.camera_lon,
                                               aircraft['lat'], aircraft['lon'])
            if distance > max_distance_nm:
                return False
        return True

    def _format_aircraft_data(self, aircraft):
        return {
            'icao': aircraft.get('hex', '').upper(),
            'callsign': aircraft.get('flight', '').strip(),
            'altitude': aircraft.get('alt_baro'),
            'ground_speed': aircraft.get('gs'),
            'track': aircraft.get('track'),
            'latitude': aircraft.get('lat'),
            'longitude': aircraft.get('lon'),
            'vertical_rate': aircraft.get('baro_rate'),
            'squawk': aircraft.get('squawk'),
            'last_seen': aircraft.get('seen', 0),
            'last_position': aircraft.get('seen_pos', 0)
        }

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 3440.065
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (math.sin(delta_lat/2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def correlate_with_detection(self, detection_timestamp):
        nearby_aircraft = self.get_nearby_aircraft()
        return {
            'timestamp': detection_timestamp,
            'adsb_aircraft_count': len(nearby_aircraft),
            'aircraft': nearby_aircraft
        }

    def set_camera_location(self, latitude, longitude):
        self.camera_lat = latitude
        self.camera_lon = longitude

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
        """Process a single frame to detect aircraft using motion and contrast."""
        self.frame_count += 1
        detections = []

        if frame is None:
            return frame, detections

        annotated_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Light blur to preserve small objects
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.prev_gray is None:
            self.prev_gray = gray.copy()
            return annotated_frame, detections

        # STEP 1: Motion detection
        frame_delta = cv2.absdiff(self.prev_gray, gray)

        motion_thresh = cv2.adaptiveThreshold(
            frame_delta, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        kernel_small = np.ones((3, 3), np.uint8)
        motion_thresh = cv2.morphologyEx(motion_thresh, cv2.MORPH_OPEN, kernel_small)
        motion_thresh = cv2.dilate(motion_thresh, kernel_small, iterations=1)

        contours, _ = cv2.findContours(motion_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        centroids = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area or area > 2000:
                continue

            (x, y, w, h) = cv2.boundingRect(contour)

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 5.0:
                continue

            roi = gray[y:y+h, x:x+w]
            if roi.size == 0:
                continue

            roi_mean = np.mean(roi)

            padding = max(10, max(w, h))
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(gray.shape[1], x + w + padding)
            y2 = min(gray.shape[0], y + h + padding)

            background_roi = gray[y1:y2, x1:x2]
            background_mean = np.mean(background_roi)

            contrast = abs(roi_mean - background_mean)

            internal_contrast = np.std(roi)

            contrast_score = min(1.0, contrast / 100.0)

            optimal_size = 100
            size_score = 1.0 - abs(area - optimal_size) / optimal_size
            size_score = max(0, min(1.0, size_score))

            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                shape_score = min(1.0, circularity * 2)
            else:
                shape_score = 0

            movement_score = min(1.0, np.sum(motion_thresh[y:y+h, x:x+w]) / (w * h * 255))

            confidence = (
                contrast_score * 0.4 +
                size_score * 0.2 +
                shape_score * 0.2 +
                movement_score * 0.2
            )

            if confidence >= self.confidence_threshold:
                centroid_x = int(x + w / 2)
                centroid_y = int(y + h / 2)
                centroids.append((centroid_x, centroid_y))

                detections.append({
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "centroid": (centroid_x, centroid_y),
                    "contrast": contrast,
                    "confidence": confidence,
                    "area": area,
                    "aspect_ratio": aspect_ratio,
                    "movement_score": movement_score,
                    "shape_score": shape_score,
                })

        tracked_objects = self.tracker.update(centroids)

        for object_id, object_data in tracked_objects.items():
            centroid = object_data["centroid"]
            speed = object_data["speed"]
            direction = object_data["direction"]

            cv2.circle(annotated_frame, centroid, 4, (0, 255, 0), -1)
            cv2.putText(
                annotated_frame,
                f"ID: {object_id}",
                (centroid[0] - 10, centroid[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

            trajectory = object_data["trajectory"]
            if len(trajectory) > 1:
                for i in range(1, len(trajectory)):
                    cv2.line(annotated_frame, trajectory[i-1], trajectory[i], (0, 255, 0), 2)

            cv2.putText(
                annotated_frame,
                f"Spd: {speed:.1f} Dir: {direction:.0f}°",
                (centroid[0] - 10, centroid[1] + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        for detection in detections:
            x, y, w, h = detection["x"], detection["y"], detection["width"], detection["height"]
            conf = detection["confidence"]

            if conf < 0.4:
                color = (0, 0, 255)
            elif conf < 0.7:
                color = (0, 255, 255)
            else:
                color = (0, 255, 0)

            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                annotated_frame,
                f"Aircraft? {conf:.2f}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        cv2.putText(
            annotated_frame,
            f"Frame: {self.frame_count} | Motion Objects: {len(contours)} | Detections: {len(detections)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        self.prev_gray = gray.copy()
        return annotated_frame, detections


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
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Aircraft Detection System')
    parser.add_argument('--display', action='store_true', help='Display video feed')
    parser.add_argument('--web', action='store_true', help='Enable web interface')
    parser.add_argument('--web-port', type=int, default=8080, help='Web interface port')
    parser.add_argument('--save-detections', action='store_true', help='Save detection images')
    parser.add_argument('--min-area', type=int, default=25, help='Minimum contour area')
    parser.add_argument('--contrast-threshold', type=int, default=50, help='Minimum contrast')
    parser.add_argument('--confidence-threshold', type=float, default=0.6, help='Detection confidence threshold')
    parser.add_argument('--use-opencv', action='store_true',
                        help='Use OpenCV VideoCapture instead of libcamera')
    parser.add_argument('--enable-adsb', action='store_true',
                        help='Enable ADS-B correlation (requires RTL-SDR and dump1090-mutability)')
    parser.add_argument('--adsb-url', default='http://localhost:8080/data/aircraft.json',
                        help='ADS-B JSON API URL')
    parser.add_argument('--camera-lat', type=float, help='Camera latitude for distance calculations')
    parser.add_argument('--camera-lon', type=float, help='Camera longitude for distance calculations')
    args = parser.parse_args()

    # Initialize camera
    camera = Camera(use_opencv=args.use_opencv)
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

    adsb_integration = ADSBIntegration(args.adsb_url)
    if args.camera_lat and args.camera_lon:
        adsb_integration.set_camera_location(args.camera_lat, args.camera_lon)
    
    # Start web interface if requested
    if args.web:
        web = WebInterface(port=args.web_port, camera=camera,
                           adsb_integration=adsb_integration if args.enable_adsb else None)
        web.start()

    web_interface.detection_active = True
    
    try:
        while web_interface.detection_active:
            # Capture frame
            frame = camera.capture_frame()
            if frame is None:
                logger.warning("Failed to capture frame. Retrying...")
                time.sleep(1)
                continue
            
            # Process frame
            annotated_frame, detections = processor.process_frame(frame)
            
            # Update global current frame for web interface
            web_interface.current_frame = annotated_frame
            
            # Record detections in database
            for detection in detections:
                # Save detection image if requested
                image_path = None
                if args.save_detections:
                    image_path = save_detection_image(frame, detection)

                detection_timestamp = datetime.datetime.now().isoformat()

                # Record in database
                detection_id = db.record_detection(
                    detection["x"],
                    detection["y"],
                    detection["width"],
                    detection["height"],
                    detection["contrast"],
                    detection["confidence"],
                    image_path
                )

                if args.enable_adsb and detection_id is not None:
                    adsb_data = adsb_integration.correlate_with_detection(detection_timestamp)
                    if adsb_data["adsb_aircraft_count"] > 0:
                        logger.info(f"Visual detection correlates with {adsb_data['adsb_aircraft_count']} ADS-B aircraft")
                    else:
                        logger.info("Visual detection - no ADS-B correlation found")
                    db.update_detection_with_adsb(detection_id, adsb_data)
            
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
        web_interface.detection_active = False
        camera.release()
        db.close()
        
        if args.display:
            cv2.destroyAllWindows()
        
        logger.info("Aircraft detection system stopped")

if __name__ == "__main__":
    main()