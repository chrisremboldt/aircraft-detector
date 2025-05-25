#!/usr/bin/env python3
"""
Flask Application for Aircraft Detection System Web Interface

This module implements the web interface for the Raspberry Pi Aircraft Detection System.
It provides API endpoints for system control, detection data access, and video streaming.

The web interface allows remote monitoring and control of the aircraft detection system.
"""

from flask import Flask, Response, render_template, request, jsonify, send_file
import cv2
import time
import os
import json
import datetime
import threading
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import shared global variables from main application
# In a real implementation, these would be imported from the main module
# or managed through a proper application context
current_frame = None
detection_active = True
db_path = "aircraft_detections.db"

# Import Database class from main application
# In a real implementation, this would be imported from the main module
from database import Database

class WebInterface:
    """Web interface for the aircraft detection system"""

    def __init__(self, host='0.0.0.0', port=8080, snapshot_dir="snapshots", camera=None, adsb_integration=None):
        """
        Initialize the web interface
        
        Args:
            host: Host address to bind to
            port: Port to listen on
            snapshot_dir: Directory to save snapshots
        """
        self.host = host
        self.port = port
        self.snapshot_dir = snapshot_dir
        self.camera = camera
        self.adsb_integration = adsb_integration
        self.app = Flask(__name__)
        
        # Create snapshot directory if it doesn't exist
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)
            
        # Setup routes
        self.setup_routes()
        
        # Thread for the web server
        self.server_thread = None
        
    def setup_routes(self):
        """Set up Flask routes"""
        
        @self.app.route('/')
        def index():
            """Render the main page"""
            return render_template('index.html')
            
        @self.app.route('/video_feed')
        def video_feed():
            """Stream the processed video feed"""
            return Response(self.generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
                           
        @self.app.route('/detections')
        def get_detections():
            """Get recent aircraft detections"""
            try:
                db = Database(db_path)
                db.initialize()
                
                # Get limit parameter, default to 100
                limit = request.args.get('limit', default=100, type=int)
                
                # Get recent detections
                detections = db.get_recent_detections(limit)
                db.close()
                
                return jsonify(detections)
            except Exception as e:
                logger.error(f"Error getting detections: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/adsb-status')
        def adsb_status():
            aircraft = []
            if self.adsb_integration:
                aircraft = self.adsb_integration.get_nearby_aircraft()
            return jsonify({
                'aircraft_count': len(aircraft),
                'aircraft': aircraft,
                'last_update': datetime.datetime.now().isoformat()
            })
                
        @self.app.route('/toggle_detection', methods=['POST'])
        def toggle_detection():
            """Toggle detection on/off"""
            global detection_active
            
            try:
                detection_active = not detection_active
                return jsonify({"active": detection_active})
            except Exception as e:
                logger.error(f"Error toggling detection: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/save_snapshot', methods=['POST'])
        def save_snapshot():
            """Save a snapshot of the current frame"""
            global current_frame
            
            try:
                if current_frame is None:
                    return jsonify({"error": "No frame available"}), 400
                    
                # Generate filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{self.snapshot_dir}/snapshot_{timestamp}.jpg"
                
                # Save image
                cv2.imwrite(filename, current_frame)
                
                return jsonify({"filename": filename})
            except Exception as e:
                logger.error(f"Error saving snapshot: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/clear_tracks', methods=['POST'])
        def clear_tracks():
            """Clear all tracking data"""
            try:
                # This would typically reset the tracker in the main application
                # For this example, we'll just return success
                return jsonify({"success": True})
            except Exception as e:
                logger.error(f"Error clearing tracks: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/update_settings', methods=['POST'])
        def update_settings():
            """Update detection settings"""
            try:
                # Get settings from request
                settings = request.json
                
                # This would typically update settings in the main application
                # For this example, we'll just log and return the settings
                logger.info(f"Updated settings: {settings}")
                
                return jsonify({"success": True, "settings": settings})
            except Exception as e:
                logger.error(f"Error updating settings: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/system_status')
        def system_status():
            """Get system status information"""
            try:
                # Collect system information
                status = {
                    "cpu_temp": self.get_cpu_temperature(),
                    "cpu_usage": self.get_cpu_usage(),
                    "memory_usage": self.get_memory_usage(),
                    "disk_usage": self.get_disk_usage(),
                    "uptime": self.get_uptime(),
                    "detection_active": detection_active
                }
                
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting system status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/snapshots')
        def list_snapshots():
            """List all available snapshots"""
            try:
                snapshots = []
                
                # Get all files in snapshot directory
                for filename in os.listdir(self.snapshot_dir):
                    if filename.endswith('.jpg'):
                        # Get file creation time
                        filepath = os.path.join(self.snapshot_dir, filename)
                        creation_time = os.path.getctime(filepath)
                        
                        # Add to list
                        snapshots.append({
                            "filename": filename,
                            "path": filepath,
                            "created": datetime.datetime.fromtimestamp(creation_time).isoformat()
                        })
                
                # Sort by creation time, newest first
                snapshots.sort(key=lambda x: x["created"], reverse=True)
                
                return jsonify(snapshots)
            except Exception as e:
                logger.error(f"Error listing snapshots: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/snapshots/<filename>')
        def get_snapshot(filename):
            """Get a specific snapshot"""
            try:
                filepath = os.path.join(self.snapshot_dir, filename)
                
                # Check if file exists
                if not os.path.exists(filepath):
                    return jsonify({"error": "Snapshot not found"}), 404
                    
                # Return the file
                return send_file(filepath, mimetype='image/jpeg')
            except Exception as e:
                logger.error(f"Error getting snapshot: {e}")
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/camera_info')
        def camera_info():
            """Get camera information"""
            try:
                if self.camera and hasattr(self.camera, 'get_camera_info'):
                    info = self.camera.get_camera_info()
                else:
                    info = {
                        "model": "Unknown",
                        "resolution": "N/A",
                        "framerate": "N/A",
                        "autofocus": "Unknown"
                    }

                return jsonify(info)
            except Exception as e:
                logger.error(f"Error getting camera info: {e}")
                return jsonify({"error": str(e)}), 500
    
    def get_cpu_temperature(self):
        """Get CPU temperature"""
        try:
            # Read CPU temperature from system file
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
            return round(temp, 1)
        except Exception as e:
            logger.error(f"Error reading CPU temperature: {e}")
            return 0
            
    def get_cpu_usage(self):
        """Get CPU usage percentage"""
        try:
            import psutil
            return round(psutil.cpu_percent(), 1)
        except Exception as e:
            logger.error(f"Error reading CPU usage: {e}")
            return 0
            
    def get_memory_usage(self):
        """Get memory usage percentage"""
        try:
            import psutil
            return round(psutil.virtual_memory().percent, 1)
        except Exception as e:
            logger.error(f"Error reading memory usage: {e}")
            return 0
            
    def get_disk_usage(self):
        """Get disk usage percentage"""
        try:
            import psutil
            return round(psutil.disk_usage('/').percent, 1)
        except Exception as e:
            logger.error(f"Error reading disk usage: {e}")
            return 0
            
    def get_uptime(self):
        """Get system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            return round(uptime_seconds)
        except Exception as e:
            logger.error(f"Error reading uptime: {e}")
            return 0
            
    def generate_frames(self):
        """Generate video frames for streaming"""
        while True:
            # Wait until a frame is available
            if current_frame is not None:
                try:
                    # Encode frame as JPEG
                    ret, buffer = cv2.imencode('.jpg', current_frame)
                    if not ret:
                        continue
                        
                    # Yield the frame in the correct format for Flask
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + 
                          buffer.tobytes() + b'\r\n')
                except Exception as e:
                    logger.error(f"Error generating frame: {e}")
            
            # Add a small delay to reduce CPU usage
            time.sleep(0.1)
            
    def start(self):
        """Start the web server in a separate thread"""
        def run_server():
            self.app.run(host=self.host, port=self.port, threaded=True)
            
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info(f"Web interface started at http://{self.host}:{self.port}")
        
    def stop(self):
        """Stop the web server"""
        # Flask doesn't provide a clean way to stop the server from another thread
        # In a production environment, you would use a more robust WSGI server like Gunicorn
        logger.info("Web interface stopping...")

def main():
    """Main function for testing the web interface"""
    global current_frame
    
    # Create a test image
    width, height = 640, 480
    test_frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Draw some text
    cv2.putText(test_frame, "Aircraft Detector", (50, 50),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(test_frame, "Web Interface Test", (50, 100),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Set as current frame
    current_frame = test_frame
    
    # Start web interface
    web = WebInterface(port=8080)
    web.start()
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        web.stop()

if __name__ == "__main__":
    import numpy as np
    main()