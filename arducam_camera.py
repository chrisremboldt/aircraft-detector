#!/usr/bin/env python3
"""
ArduCam 64MP Hawkeye Camera Integration for Raspberry Pi

This module provides the specific implementation for interfacing with the
64MP ArduCam Hawkeye camera with autofocus capabilities. This code replaces
the generic Camera class in the main aircraft detection system.

Requirements:
- ArduCam Python SDK installed (from MIPI_Camera repository)
- libcamera-dev and libcamera-apps installed

Note: This module is designed specifically for the 64MP ArduCam Hawkeye camera
and should be integrated with the main aircraft detection system.
"""

import cv2
import numpy as np
import time
import os
import logging
import threading
from arducam_camera import ArduCam

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArduCam64MP:
    """Interface for the 64MP ArduCam Hawkeye with autofocus"""
    
    def __init__(self, 
                 resolution=(4624, 3472),  # Native resolution of 64MP ArduCam
                 framerate=15,
                 config_file="/home/pi/MIPI_Camera/RPI/config/camera_config.json",
                 processing_resolution=(1920, 1080)):  # Lower resolution for processing
        """
        Initialize the ArduCam camera
        
        Args:
            resolution: Native capture resolution (tuple of width, height)
            framerate: Target framerate
            config_file: Path to ArduCam config file
            processing_resolution: Resolution for image processing (downsampled)
        """
        self.native_resolution = resolution
        self.processing_resolution = processing_resolution
        self.framerate = framerate
        self.config_file = config_file
        self.camera = None
        self.frame_buffer = None
        self.capture_thread = None
        self.running = False
        self.last_autofocus_time = 0
        self.autofocus_interval = 60  # Seconds between autofocus operations
        
    def initialize(self):
        """Initialize the camera hardware"""
        try:
            # Initialize ArduCam with config file
            if not os.path.exists(self.config_file):
                logger.error(f"Config file not found: {self.config_file}")
                return False
                
            # Initialize ArduCam with configuration
            self.camera = ArduCam()
            self.camera.init_camera(self.config_file)
            
            # Configure camera
            self.camera.set_resolution(*self.native_resolution)
            self.camera.set_control(ArduCam.CTRL_FRAME_RATE, self.framerate)
            
            # Initialize frame buffer
            self.frame_buffer = None
            
            # Start capture thread
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            # Allow camera to initialize
            time.sleep(2)
            
            # Initial autofocus
            self.autofocus()
            
            logger.info(f"64MP ArduCam initialized at resolution {self.native_resolution}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize 64MP ArduCam: {e}")
            return False
            
    def release(self):
        """Release the camera resources"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
            
        if self.camera:
            self.camera.close_camera()
            logger.info("64MP ArduCam resources released")
            
    def _capture_loop(self):
        """Background thread to continuously capture frames"""
        while self.running:
            try:
                # Capture frame
                frame = self.camera.capture_frame()
                if frame is not None:
                    # Convert to OpenCV format
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Resize for processing
                    if self.processing_resolution != self.native_resolution:
                        frame = cv2.resize(frame, self.processing_resolution)
                    
                    # Update frame buffer
                    self.frame_buffer = frame
                    
                    # Check if autofocus should run
                    current_time = time.time()
                    if current_time - self.last_autofocus_time > self.autofocus_interval:
                        self.autofocus()
                        self.last_autofocus_time = current_time
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
                
    def capture_frame(self):
        """Capture a frame from the camera"""
        if not self.camera:
            logger.error("64MP ArduCam not initialized")
            return None
            
        # Return the most recent frame from the buffer
        return self.frame_buffer.copy() if self.frame_buffer is not None else None
            
    def autofocus(self):
        """Run autofocus operation"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            logger.info("Running autofocus...")
            
            # Start autofocus operation
            self.camera.start_autofocus()
            
            # Wait for autofocus to complete
            # This can be improved with a callback mechanism if ArduCam SDK supports it
            time.sleep(2)
            
            logger.info("Autofocus completed")
            return True
        except Exception as e:
            logger.error(f"Autofocus failed: {e}")
            return False
            
    def set_autofocus(self, enable=True):
        """Enable or disable autofocus"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            if enable:
                # Enable continuous autofocus
                self.camera.set_control(ArduCam.CTRL_AF_MODE, ArduCam.AF_MODE_CONTINUOUS)
                logger.info("Continuous autofocus enabled")
            else:
                # Disable continuous autofocus
                self.camera.set_control(ArduCam.CTRL_AF_MODE, ArduCam.AF_MODE_OFF)
                logger.info("Autofocus disabled")
                
            return True
        except Exception as e:
            logger.error(f"Failed to set autofocus mode: {e}")
            return False
            
    def set_manual_focus(self, focus_value):
        """Set manual focus value (0-255)"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            # Set focus to manual mode
            self.camera.set_control(ArduCam.CTRL_AF_MODE, ArduCam.AF_MODE_OFF)
            
            # Set focus value
            focus_value = max(0, min(255, focus_value))
            self.camera.set_control(ArduCam.CTRL_FOCUS_ABSOLUTE, focus_value)
            
            logger.info(f"Manual focus set to {focus_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to set manual focus: {e}")
            return False
            
    def adjust_exposure(self, sky_brightness):
        """Adjust camera exposure based on sky brightness"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            # Calculate exposure value based on sky brightness
            # This is an example formula that should be tuned based on testing
            if sky_brightness < 50:  # Dark sky
                exposure_value = 200  # Longer exposure
            elif sky_brightness < 150:  # Normal sky
                exposure_value = 100  # Medium exposure
            else:  # Bright sky
                exposure_value = 50  # Shorter exposure
                
            # Set exposure value
            self.camera.set_control(ArduCam.CTRL_EXPOSURE, exposure_value)
            
            logger.info(f"Adjusted exposure to {exposure_value} for sky brightness: {sky_brightness}")
            return True
        except Exception as e:
            logger.error(f"Failed to adjust exposure: {e}")
            return False
            
    def take_high_res_photo(self, filename):
        """Take a full resolution photo and save it to disk"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            # Temporarily switch to full resolution
            current_resolution = self.processing_resolution
            
            # Capture high-resolution frame
            frame = self.camera.capture_frame()
            if frame is None:
                logger.error("Failed to capture high-res frame")
                return False
                
            # Convert to OpenCV format
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Save image
            cv2.imwrite(filename, frame)
            
            logger.info(f"High-resolution photo saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to take high-res photo: {e}")
            return False
            
    def set_zoom(self, zoom_factor):
        """Set digital zoom factor (1.0-5.0)"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
                
            # Ensure zoom factor is within valid range
            zoom_factor = max(1.0, min(5.0, zoom_factor))
            
            # Set digital zoom
            self.camera.set_control(ArduCam.CTRL_ZOOM_ABSOLUTE, int(zoom_factor * 100))
            
            logger.info(f"Digital zoom set to {zoom_factor}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set zoom: {e}")
            return False
            
    def get_camera_info(self):
        """Get camera information"""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return {}
                
            # Get camera information
            info = {
                "model": "ArduCam 64MP Hawkeye",
                "resolution": self.native_resolution,
                "processing_resolution": self.processing_resolution,
                "framerate": self.framerate,
            }
            
            return info
        except Exception as e:
            logger.error(f"Failed to get camera info: {e}")
            return {}

def test_arducam():
    """Test the ArduCam 64MP camera"""
    try:
        # Initialize camera
        camera = ArduCam64MP(processing_resolution=(1920, 1080))
        if not camera.initialize():
            print("Failed to initialize camera. Exiting.")
            return False
            
        print("Camera initialized successfully")
        
        # Wait for camera to initialize
        time.sleep(2)
        
        # Capture test frames
        for i in range(10):
            frame = camera.capture_frame()
            if frame is not None:
                print(f"Frame {i+1} captured: {frame.shape}")
                
                # Save a test image
                if i == 5:
                    cv2.imwrite("arducam_test.jpg", frame)
                    print("Test image saved as arducam_test.jpg")
            else:
                print(f"Frame {i+1} capture failed")
                
            time.sleep(0.5)
            
        # Test autofocus
        print("Testing autofocus...")
        camera.autofocus()
        
        # Test high-res photo
        print("Taking high-resolution photo...")
        camera.take_high_res_photo("arducam_highres.jpg")
        
        # Release camera
        camera.release()
        print("Camera released")
        
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    test_arducam()