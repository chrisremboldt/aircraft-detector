#!/usr/bin/env python3
"""
ArduCam 64MP Hawkeye Camera Integration for Raspberry Pi 5

This module provides the specific implementation for interfacing with the
64MP ArduCam Hawkeye camera with autofocus capabilities using rpicam-apps.
This version is updated for Pi 5 with the modern libcamera/rpicam system.

Requirements:
- rpicam-apps installed and working
- ArduCam 64MP properly configured with device tree overlay

Note: This module is designed specifically for the 64MP ArduCam Hawkeye camera
on Raspberry Pi 5 and integrates with the main aircraft detection system.
"""

import cv2
import numpy as np
import time
import os
import logging
import threading
import subprocess
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArduCam64MP:
    """Interface for the 64MP ArduCam Hawkeye with autofocus using rpicam-apps"""
    
    def __init__(self, 
                 resolution=(1920, 1080),  # Processing resolution
                 framerate=30,
                 autofocus=True,
                 capture_timeout=1000):  # Timeout for rpicam commands
        """
        Initialize the ArduCam camera using rpicam-apps
        
        Args:
            resolution: Processing resolution (tuple of width, height)
            framerate: Target framerate
            autofocus: Enable autofocus mode
            capture_timeout: Timeout for rpicam commands in milliseconds
        """
        self.resolution = resolution
        self.framerate = framerate
        self.autofocus = autofocus
        self.capture_timeout = capture_timeout
        self.frame_buffer = None
        self.capture_thread = None
        self.running = False
        self.last_autofocus_time = 0
        self.autofocus_interval = 30  # Seconds between autofocus operations
        self.temp_dir = tempfile.gettempdir()
        self.frame_counter = 0
        
        # rpicam command base arguments
        self.base_args = [
            '--width', str(resolution[0]),
            '--height', str(resolution[1]),
            '--timeout', str(capture_timeout),
            '--immediate',  # Don't wait for focus/exposure
            '--nopreview'   # No preview window
        ]
        
        if autofocus:
            self.base_args.extend(['--autofocus-mode', 'continuous'])
        
    def initialize(self):
        """Initialize the camera hardware"""
        try:
            # Test if rpicam-hello can detect camera
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.error("rpicam-hello failed - camera not detected")
                return False
                
            if "arducam_64mp" not in result.stdout:
                logger.error("ArduCam 64MP not detected in camera list")
                return False
                
            logger.info("ArduCam 64MP detected successfully")
            
            # Test initial capture
            test_file = os.path.join(self.temp_dir, "arducam_init_test.jpg")
            test_result = subprocess.run([
                'rpicam-still', '-o', test_file,
                '--width', str(self.resolution[0]),
                '--height', str(self.resolution[1]),
                '--timeout', '2000'
            ], capture_output=True, text=True, timeout=15)
            
            if test_result.returncode == 0 and os.path.exists(test_file):
                # Test reading with OpenCV
                test_img = cv2.imread(test_file)
                if test_img is not None:
                    logger.info(f"Camera initialization successful - test image: {test_img.shape}")
                    os.remove(test_file)
                else:
                    logger.error("Failed to read test image with OpenCV")
                    return False
            else:
                logger.error(f"Initial capture test failed: {test_result.stderr}")
                return False
            
            # Start continuous capture thread for video-like operation
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            logger.info(f"ArduCam 64MP initialized at {self.resolution[0]}x{self.resolution[1]}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Camera initialization timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ArduCam 64MP: {e}")
            return False
            
    def release(self):
        """Release the camera resources"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            
        # Clean up any temporary files
        try:
            for filename in os.listdir(self.temp_dir):
                if filename.startswith("arducam_frame_"):
                    os.remove(os.path.join(self.temp_dir, filename))
        except:
            pass
            
        logger.info("ArduCam 64MP resources released")
            
    def _capture_loop(self):
        """Background thread to continuously capture frames"""
        frame_count = 0
        
        while self.running:
            try:
                # Generate unique filename for this frame
                frame_file = os.path.join(self.temp_dir, f"arducam_frame_{frame_count % 3}.jpg")
                
                # Capture frame using rpicam-still
                result = subprocess.run([
                    'rpicam-still', '-o', frame_file
                ] + self.base_args, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and os.path.exists(frame_file):
                    # Read frame with OpenCV
                    frame = cv2.imread(frame_file)
                    if frame is not None:
                        self.frame_buffer = frame
                        self.frame_counter += 1
                        
                        # Check if autofocus should run
                        if self.autofocus:
                            current_time = time.time()
                            if current_time - self.last_autofocus_time > self.autofocus_interval:
                                self._trigger_autofocus()
                                self.last_autofocus_time = current_time
                    
                    # Clean up frame file
                    try:
                        os.remove(frame_file)
                    except:
                        pass
                else:
                    logger.warning(f"Frame capture failed: {result.stderr}")
                    
                frame_count += 1
                
                # Control frame rate
                time.sleep(1.0 / self.framerate)
                
            except subprocess.TimeoutExpired:
                logger.warning("Frame capture timed out")
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
                
    def capture_frame(self):
        """Capture a frame from the camera"""
        if not self.running:
            logger.error("Camera not initialized or stopped")
            return None
            
        # Return the most recent frame from the buffer
        if self.frame_buffer is not None:
            return self.frame_buffer.copy()
        else:
            # If no buffered frame, capture directly
            return self._capture_single_frame()
            
    def _capture_single_frame(self):
        """Capture a single frame directly (blocking)"""
        try:
            frame_file = os.path.join(self.temp_dir, f"arducam_single_{int(time.time())}.jpg")
            
            result = subprocess.run([
                'rpicam-still', '-o', frame_file
            ] + self.base_args, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and os.path.exists(frame_file):
                frame = cv2.imread(frame_file)
                os.remove(frame_file)
                return frame
            else:
                logger.error(f"Single frame capture failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error capturing single frame: {e}")
            return None
            
    def _trigger_autofocus(self):
        """Trigger autofocus operation"""
        try:
            # Use rpicam-still with autofocus trigger
            result = subprocess.run([
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--timeout', '1000'
            ], capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                logger.debug("Autofocus triggered successfully")
            else:
                logger.warning(f"Autofocus trigger failed: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Error triggering autofocus: {e}")
            
    def autofocus(self):
        """Run manual autofocus operation"""
        try:
            logger.info("Running manual autofocus...")
            
            result = subprocess.run([
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--timeout', '2000'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info("Manual autofocus completed successfully")
                return True
            else:
                logger.error(f"Manual autofocus failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Manual autofocus error: {e}")
            return False
            
    def set_autofocus(self, enable=True):
        """Enable or disable autofocus"""
        self.autofocus = enable
        if enable:
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--autofocus-mode')]
            self.base_args.extend(['--autofocus-mode', 'continuous'])
            logger.info("Continuous autofocus enabled")
        else:
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--autofocus-mode')]
            self.base_args.extend(['--autofocus-mode', 'manual'])
            logger.info("Autofocus disabled")
        return True
            
    def set_manual_focus(self, focus_value):
        """Set manual focus value (0.0-1.0 where 0.0 is infinity)"""
        try:
            # Remove existing lens-position arguments
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--lens-position')]
            
            # Add manual focus
            focus_value = max(0.0, min(1.0, focus_value))
            self.base_args.extend(['--lens-position', str(focus_value)])
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--autofocus-mode')]
            self.base_args.extend(['--autofocus-mode', 'manual'])
            
            logger.info(f"Manual focus set to {focus_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to set manual focus: {e}")
            return False
            
    def adjust_exposure(self, sky_brightness):
        """Adjust camera exposure based on sky brightness"""
        try:
            # Remove existing exposure arguments
            args_to_remove = ['--shutter', '--gain', '--ev']
            for arg in args_to_remove:
                self.base_args = [a for a in self.base_args if not a.startswith(arg)]
            
            # Calculate exposure settings based on sky brightness
            if sky_brightness < 50:  # Dark sky
                # Longer exposure for dark conditions
                self.base_args.extend(['--shutter', '100000', '--gain', '2.0'])  # 100ms shutter
            elif sky_brightness < 150:  # Normal sky
                # Auto exposure
                pass  # Let camera auto-adjust
            else:  # Bright sky
                # Shorter exposure for bright conditions
                self.base_args.extend(['--shutter', '10000', '--gain', '1.0'])  # 10ms shutter
                
            logger.info(f"Adjusted exposure for sky brightness: {sky_brightness}")
            return True
        except Exception as e:
            logger.error(f"Failed to adjust exposure: {e}")
            return False
            
    def take_high_res_photo(self, filename):
        """Take a full resolution photo and save it to disk"""
        try:
            # Use maximum resolution for high-res photo
            result = subprocess.run([
                'rpicam-still', '-o', filename,
                '--width', '8000',
                '--height', '6000',
                '--timeout', '3000'
            ] + [arg for arg in self.base_args if not arg.startswith('--width') and not arg.startswith('--height')],
            capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(filename):
                logger.info(f"High-resolution photo saved to {filename}")
                return True
            else:
                logger.error(f"Failed to take high-res photo: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error taking high-res photo: {e}")
            return False
            
    def set_zoom(self, zoom_factor):
        """Set digital zoom factor (1.0-5.0)"""
        try:
            # Remove existing zoom arguments
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--roi')]
            
            # Ensure zoom factor is within valid range
            zoom_factor = max(1.0, min(5.0, zoom_factor))
            
            if zoom_factor > 1.0:
                # Calculate ROI for digital zoom
                # Center crop with zoom factor
                crop_factor = 1.0 / zoom_factor
                x_offset = (1.0 - crop_factor) / 2.0
                y_offset = (1.0 - crop_factor) / 2.0
                
                roi = f"{x_offset},{y_offset},{crop_factor},{crop_factor}"
                self.base_args.extend(['--roi', roi])
                
            logger.info(f"Digital zoom set to {zoom_factor}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set zoom: {e}")
            return False
            
    def get_camera_info(self):
        """Get camera information"""
        try:
            # Get camera list
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=5)
            
            info = {
                "model": "ArduCam 64MP Hawkeye",
                "resolution": self.resolution,
                "framerate": self.framerate,
                "autofocus": self.autofocus,
                "frames_captured": self.frame_counter,
                "camera_detected": "arducam_64mp" in result.stdout if result.returncode == 0 else False
            }
            
            return info
        except Exception as e:
            logger.error(f"Failed to get camera info: {e}")
            return {"error": str(e)}

def test_arducam():
    """Test the ArduCam 64MP camera"""
    try:
        print("Testing ArduCam 64MP with rpicam-apps...")
        
        # Initialize camera
        camera = ArduCam64MP(resolution=(1920, 1080), framerate=15)
        if not camera.initialize():
            print("Failed to initialize camera. Exiting.")
            return False
            
        print("Camera initialized successfully")
        
        # Wait for camera to stabilize
        time.sleep(3)
        
        # Capture test frames
        for i in range(5):
            print(f"Capturing frame {i+1}...")
            frame = camera.capture_frame()
            if frame is not None:
                print(f"Frame {i+1} captured: {frame.shape}")
                
                # Save a test image
                if i == 2:
                    test_filename = f"arducam_test_{int(time.time())}.jpg"
                    cv2.imwrite(test_filename, frame)
                    print(f"Test image saved as {test_filename}")
            else:
                print(f"Frame {i+1} capture failed")
                
            time.sleep(1)
            
        # Test autofocus
        print("Testing autofocus...")
        if camera.autofocus():
            print("Autofocus test successful")
        else:
            print("Autofocus test failed")
        
        # Test high-res photo
        print("Taking high-resolution photo...")
        highres_filename = f"arducam_highres_{int(time.time())}.jpg"
        if camera.take_high_res_photo(highres_filename):
            print(f"High-res photo saved as {highres_filename}")
        else:
            print("High-res photo failed")
        
        # Get camera info
        info = camera.get_camera_info()
        print(f"Camera info: {info}")
        
        # Release camera
        camera.release()
        print("Camera released")
        
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    test_arducam()
