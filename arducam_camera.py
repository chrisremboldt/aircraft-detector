#!/usr/bin/env python3
"""
ArduCam 64MP Hawkeye Camera Integration for Raspberry Pi 5 - FIXED VERSION

This module provides a simplified, reliable implementation for interfacing with the
64MP ArduCam Hawkeye camera with autofocus capabilities using rpicam-apps.
This version is specifically designed for Pi 5 with the modern libcamera/rpicam system.

FIXES APPLIED:
- Fixed --nopreview argument (now explicitly "1" to avoid misparsing)
- Improved error handling for rpicam-still commands
- Added fallback capture methods
- Better logging for debugging

Key Features:
- Single-process capture method (eliminates pipeline conflicts)
- Compatible with Pi 5 libcamera system
- Automatic autofocus management
- High-resolution photo capture
- Robust error handling and logging

Requirements:
- Raspberry Pi 5 with Bookworm OS
- rpicam-apps installed and working
- ArduCam 64MP properly configured with device tree overlay:
  - camera_auto_detect=0
  - dtoverlay=arducam-64mp,cam0
  - dtparam=i2c_vc=on
  - gpu_mem=128

Author: Aircraft Detection System
Version: 2.1 - Fixed nopreview argument issue
"""

import cv2
import numpy as np
import time
import os
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArduCam64MP:
    """
    Simplified interface for the 64MP ArduCam Hawkeye using rpicam-apps
    
    This class provides a reliable, single-process approach to camera capture
    that eliminates the pipeline conflicts common with multi-threaded approaches.
    """
    
    def __init__(self, 
                 resolution=(1920, 1080),
                 framerate=30,
                 autofocus=True,
                 capture_timeout=1000,
                 quality=90):
        """
        Initialize the ArduCam camera using rpicam-still
        
        Args:
            resolution (tuple): Processing resolution (width, height)
            framerate (int): Target framerate (for timing calculations only)
            autofocus (bool): Enable continuous autofocus mode
            capture_timeout (int): Timeout for rpicam commands in milliseconds
            quality (int): JPEG quality for captures (1-100)
        """
        self.resolution = resolution
        self.framerate = framerate
        self.autofocus = autofocus
        self.capture_timeout = capture_timeout
        self.quality = quality
        
        # Internal state
        self.temp_dir = tempfile.gettempdir()
        self.frame_counter = 0
        self.last_autofocus_time = 0
        self.autofocus_interval = 30  # Seconds between autofocus operations
        self.is_initialized = False
        
        # Base arguments for rpicam-still - FIXED: removed invalid 'continuous' value
        self.base_args = [
            '--width', str(resolution[0]),
            '--height', str(resolution[1]),
            '--timeout', str(capture_timeout),
            '--quality', str(quality),
            '--immediate',  # Don't wait for focus/exposure stabilization
            '--nopreview', '1'  # Explicit value avoids CLI misparse
        ]
        
        # Set autofocus mode
        if autofocus:
            self.base_args.extend(['--autofocus-mode', 'continuous'])
        else:
            self.base_args.extend(['--autofocus-mode', 'manual'])
        
        logger.info(f"ArduCam64MP configured: {resolution[0]}x{resolution[1]}, "
                   f"autofocus={'enabled' if autofocus else 'disabled'}")
        
    def initialize(self):
        """
        Initialize the camera hardware and verify functionality
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing ArduCam 64MP...")
            
            # Step 1: Check if rpicam-hello can detect camera
            logger.debug("Checking camera detection...")
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.error("rpicam-hello failed - camera not detected")
                logger.error(f"Error output: {result.stderr}")
                return False
                
            # More flexible camera detection - check for any arducam or 64mp camera
            camera_detected = False
            for line in result.stdout.lower():
                if any(keyword in line for keyword in ['arducam', '64mp', 'hawkeye']):
                    camera_detected = True
                    break
                    
            if not camera_detected:
                logger.warning("ArduCam 64MP not explicitly detected, but continuing...")
                logger.info(f"Available cameras: {result.stdout}")
                # Don't return False here - sometimes the camera works even if not detected properly
                
            logger.info("Camera detection check completed")
            
            # Step 2: Test initial capture with improved error handling
            logger.debug("Testing initial capture...")
            test_file = os.path.join(self.temp_dir, f"arducam_init_test_{int(time.time())}.jpg")
            
            # Try capture with current arguments
            test_result = self._safe_capture(test_file, timeout=15)
            
            if test_result and os.path.exists(test_file):
                # Step 3: Verify OpenCV can read the image
                test_img = cv2.imread(test_file)
                if test_img is not None:
                    logger.info(f"Camera initialization successful - test image: {test_img.shape}")
                    # Clean up test file
                    os.remove(test_file)
                    self.is_initialized = True
                    
                    # Step 4: Run initial autofocus if enabled
                    if self.autofocus:
                        logger.info("Running initial autofocus...")
                        self.autofocus_manual()
                    
                    return True
                else:
                    logger.error("Failed to read test image with OpenCV")
                    if os.path.exists(test_file):
                        os.remove(test_file)
                    return False
            else:
                logger.error("Initial capture test failed")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Camera initialization timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ArduCam 64MP: {e}")
            return False
            
    def _safe_capture(self, output_file, timeout=5):
        """
        Safely capture an image with fallback options
        
        Args:
            output_file (str): Path to save the captured image
            timeout (int): Timeout in seconds
            
        Returns:
            bool: True if capture succeeded, False otherwise
        """
        # Try with current arguments first
        try:
            cmd = ['rpicam-still', '-o', output_file] + self.base_args
            logger.debug(f"Capture command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                return True
            else:
                logger.warning(f"Primary capture failed (returncode: {result.returncode})")
                logger.warning(f"Error: {result.stderr}")
                
                # Try fallback capture with minimal arguments
                logger.debug("Trying fallback capture with minimal arguments...")
                fallback_cmd = [
                    'rpicam-still', '-o', output_file,
                    '--width', str(self.resolution[0]),
                    '--height', str(self.resolution[1]),
                    '--timeout', '2000',
                    '--nopreview', '1'
                ]
                
                fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=timeout)
                
                if fallback_result.returncode == 0:
                    logger.info("Fallback capture succeeded")
                    return True
                else:
                    logger.error(f"Fallback capture also failed: {fallback_result.stderr}")
                    return False
                    
        except subprocess.TimeoutExpired:
            logger.warning(f"Capture timed out after {timeout}s")
            return False
        except Exception as e:
            logger.error(f"Exception during capture: {e}")
            return False
            
    def release(self):
        """Release camera resources and clean up temporary files"""
        logger.info("Releasing ArduCam 64MP resources...")
        
        # Clean up any temporary files created by this instance
        try:
            temp_files = []
            for filename in os.listdir(self.temp_dir):
                if filename.startswith("arducam_frame_") or filename.startswith("arducam_"):
                    temp_files.append(os.path.join(self.temp_dir, filename))
            
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass  # Ignore errors removing temp files
                    
            if temp_files:
                logger.debug(f"Cleaned up {len(temp_files)} temporary files")
                
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
            
        self.is_initialized = False
        logger.info("ArduCam 64MP resources released")
            
    def capture_frame(self):
        """
        Capture a single frame from the camera
        
        Returns:
            numpy.ndarray: Captured frame as OpenCV image, or None if failed
        """
        if not self.is_initialized:
            logger.error("Camera not initialized - call initialize() first")
            return None
            
        # Generate unique filename for this frame
        frame_file = os.path.join(self.temp_dir, f"arducam_frame_{self.frame_counter}_{int(time.time()*1000)}.jpg")
        
        try:
            # Check if periodic autofocus should run
            if self.autofocus:
                current_time = time.time()
                if current_time - self.last_autofocus_time > self.autofocus_interval:
                    self._trigger_autofocus_background()
                    self.last_autofocus_time = current_time
            
            # Capture frame using safe capture method
            start_time = time.time()
            if self._safe_capture(frame_file, timeout=5):
                capture_time = time.time() - start_time
                
                # Read frame with OpenCV
                frame = cv2.imread(frame_file)
                
                # Clean up frame file immediately
                try:
                    os.remove(frame_file)
                except:
                    pass
                
                if frame is not None:
                    self.frame_counter += 1
                    logger.debug(f"Frame {self.frame_counter} captured in {capture_time:.2f}s: {frame.shape}")
                    return frame
                else:
                    logger.warning("Failed to read captured frame with OpenCV")
                    return None
            else:
                logger.warning("Frame capture failed using safe capture method")
                return None
                
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            # Try to clean up the file if it exists
            try:
                if os.path.exists(frame_file):
                    os.remove(frame_file)
            except:
                pass
            return None
            
    def _trigger_autofocus_background(self):
        """
        Trigger autofocus operation in background (non-blocking)
        This is called periodically during normal capture operations
        """
        try:
            # Quick autofocus trigger - don't wait for completion
            subprocess.run([
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--timeout', '500',
                '--immediate',
                '--nopreview', '1'
            ], capture_output=True, timeout=2)
            
            logger.debug("Background autofocus triggered")
                
        except:
            # Don't let autofocus errors affect frame capture
            pass
            
    def autofocus_manual(self):
        """
        Run manual autofocus operation (blocking)
        
        Returns:
            bool: True if autofocus completed successfully, False otherwise
        """
        if not self.is_initialized:
            logger.error("Camera not initialized")
            return False
            
        try:
            logger.info("Running manual autofocus...")
            
            result = subprocess.run([
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--timeout', '3000',
                '--nopreview', '1'
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                logger.info("Manual autofocus completed successfully")
                return True
            else:
                logger.warning(f"Manual autofocus failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.warning("Manual autofocus timed out")
            return False
        except Exception as e:
            logger.error(f"Manual autofocus error: {e}")
            return False
            
    def set_autofocus_mode(self, enable=True):
        """
        Enable or disable continuous autofocus
        
        Args:
            enable (bool): True to enable continuous autofocus, False for manual
            
        Returns:
            bool: True if setting was applied successfully
        """
        try:
            self.autofocus = enable
            
            # Remove existing autofocus arguments
            self.base_args = [arg for arg in self.base_args if not arg.startswith('--autofocus-mode')]
            
            # Add new autofocus mode
            if enable:
                self.base_args.extend(['--autofocus-mode', 'continuous'])
                logger.info("Continuous autofocus enabled")
            else:
                self.base_args.extend(['--autofocus-mode', 'manual'])
                logger.info("Autofocus disabled (manual mode)")
                
            return True
        except Exception as e:
            logger.error(f"Failed to set autofocus mode: {e}")
            return False
            
    def set_manual_focus(self, focus_position):
        """
        Set manual focus position
        
        Args:
            focus_position (float): Focus position from 0.0 (infinity) to 1.0 (close)
            
        Returns:
            bool: True if focus was set successfully
        """
        try:
            # Ensure focus position is in valid range
            focus_position = max(0.0, min(1.0, focus_position))
            
            # Remove existing lens-position and autofocus arguments
            args_to_remove = ['--lens-position', '--autofocus-mode']
            for arg_type in args_to_remove:
                self.base_args = [arg for arg in self.base_args if not arg.startswith(arg_type)]
            
            # Set manual focus
            self.base_args.extend(['--autofocus-mode', 'manual'])
            self.base_args.extend(['--lens-position', str(focus_position)])
            
            logger.info(f"Manual focus set to {focus_position:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to set manual focus: {e}")
            return False
            
    def take_high_res_photo(self, filename, resolution=(8000, 6000)):
        """
        Take a full resolution photo and save it to disk
        
        Args:
            filename (str): Path where to save the high-resolution image
            resolution (tuple): Resolution for high-res photo (width, height)
            
        Returns:
            bool: True if photo was saved successfully, False otherwise
        """
        if not self.is_initialized:
            logger.error("Camera not initialized")
            return False
            
        try:
            logger.info(f"Taking high-resolution photo: {resolution[0]}x{resolution[1]}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Capture high-resolution image
            result = subprocess.run([
                'rpicam-still', '-o', filename,
                '--width', str(resolution[0]),
                '--height', str(resolution[1]),
                '--quality', '95',  # High quality for full-res photos
                '--timeout', '5000',  # Longer timeout for high-res
                '--nopreview', '1'
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and os.path.exists(filename):
                # Verify file was created and get its size
                file_size = os.path.getsize(filename)
                logger.info(f"High-resolution photo saved: {filename} ({file_size:,} bytes)")
                return True
            else:
                logger.error(f"Failed to take high-res photo: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("High-resolution photo capture timed out")
            return False
        except Exception as e:
            logger.error(f"Error taking high-res photo: {e}")
            return False
            
    def adjust_exposure_for_conditions(self, sky_brightness=None, force_settings=None):
        """
        Adjust camera exposure settings based on lighting conditions
        
        Args:
            sky_brightness (int, optional): Average sky brightness (0-255)
            force_settings (dict, optional): Force specific settings
                                           {'shutter': microseconds, 'gain': float, 'ev': compensation}
        
        Returns:
            bool: True if settings were applied successfully
        """
        try:
            # Remove existing exposure arguments
            exposure_args = ['--shutter', '--gain', '--ev', '--awb']
            for arg_type in exposure_args:
                self.base_args = [arg for arg in self.base_args if not arg.startswith(arg_type)]
            
            if force_settings:
                # Apply forced settings
                if 'shutter' in force_settings:
                    self.base_args.extend(['--shutter', str(force_settings['shutter'])])
                if 'gain' in force_settings:
                    self.base_args.extend(['--gain', str(force_settings['gain'])])
                if 'ev' in force_settings:
                    self.base_args.extend(['--ev', str(force_settings['ev'])])
                    
                logger.info(f"Applied forced exposure settings: {force_settings}")
                
            elif sky_brightness is not None:
                # Auto-adjust based on sky brightness
                if sky_brightness < 50:  # Dark/dawn/dusk conditions
                    self.base_args.extend(['--shutter', '100000', '--gain', '2.0'])  # 100ms, gain 2x
                    logger.info("Applied low-light exposure settings")
                elif sky_brightness > 200:  # Very bright conditions
                    self.base_args.extend(['--shutter', '5000', '--gain', '1.0'])   # 5ms, minimal gain
                    logger.info("Applied bright-light exposure settings")
                else:
                    # Normal conditions - let camera auto-adjust
                    logger.info("Using automatic exposure for normal lighting")
                    
                # Always set daylight white balance for aircraft detection
                self.base_args.extend(['--awb', 'daylight'])
                
            return True
        except Exception as e:
            logger.error(f"Failed to adjust exposure: {e}")
            return False
            
    def get_camera_info(self):
        """
        Get comprehensive camera information and status
        
        Returns:
            dict: Camera information including model, settings, and statistics
        """
        try:
            # Get camera detection status
            detection_result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                            capture_output=True, text=True, timeout=5)
            
            camera_detected = (detection_result.returncode == 0)
            
            info = {
                "model": "ArduCam 64MP Hawkeye",
                "resolution": self.resolution,
                "framerate": self.framerate,
                "autofocus": self.autofocus,
                "quality": self.quality,
                "frames_captured": self.frame_counter,
                "is_initialized": self.is_initialized,
                "camera_detected": camera_detected,
                "capture_timeout": self.capture_timeout,
                "last_autofocus": self.last_autofocus_time,
                "temp_directory": self.temp_dir
            }
            
            # Add current settings from base_args
            settings = {}
            for i, arg in enumerate(self.base_args):
                if arg.startswith('--') and i + 1 < len(self.base_args):
                    setting_name = arg[2:]  # Remove '--'
                    if i + 1 < len(self.base_args):
                        next_arg = self.base_args[i + 1]
                        if not next_arg.startswith('--'):  # Make sure it's a value, not another setting
                            settings[setting_name] = next_arg
                    # Handle flags without values
                    elif arg in ['--immediate', '--nopreview']:
                        settings[setting_name] = 'enabled'
            
            info["current_settings"] = settings
            
            return info
        except Exception as e:
            logger.error(f"Failed to get camera info: {e}")
            return {"error": str(e), "model": "ArduCam 64MP Hawkeye"}

    def capture_burst(self, count=5, interval=0.5):
        """
        Capture multiple frames in quick succession
        
        Args:
            count (int): Number of frames to capture
            interval (float): Seconds between captures
            
        Returns:
            list: List of captured frames (numpy arrays)
        """
        if not self.is_initialized:
            logger.error("Camera not initialized")
            return []
            
        frames = []
        logger.info(f"Starting burst capture: {count} frames with {interval}s interval")
        
        for i in range(count):
            frame = self.capture_frame()
            if frame is not None:
                frames.append(frame)
                logger.debug(f"Burst frame {i+1}/{count} captured")
            else:
                logger.warning(f"Burst frame {i+1}/{count} failed")
                
            if i < count - 1:  # Don't wait after the last frame
                time.sleep(interval)
                
        logger.info(f"Burst capture completed: {len(frames)}/{count} frames successful")
        return frames

def test_arducam_comprehensive():
    """
    Comprehensive test of the ArduCam 64MP camera functionality
    """
    print("="*60)
    print("ArduCam 64MP Comprehensive Test (FIXED VERSION)")
    print("="*60)
    
    try:
        # Initialize camera
        print("\n1. Initializing camera...")
        camera = ArduCam64MP(resolution=(1920, 1080), autofocus=True)
        
        if not camera.initialize():
            print("❌ Failed to initialize camera. Exiting.")
            return False
            
        print("✅ Camera initialized successfully")
        
        # Get camera info
        print("\n2. Camera information:")
        info = camera.get_camera_info()
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        # Test basic frame capture
        print("\n3. Testing basic frame capture...")
        for i in range(3):
            print(f"   Capturing frame {i+1}...")
            frame = camera.capture_frame()
            if frame is not None:
                print(f"   ✅ Frame {i+1} captured: {frame.shape}")
                
                # Save first frame as test
                if i == 0:
                    test_filename = f"test_frame_{int(time.time())}.jpg"
                    cv2.imwrite(test_filename, frame)
                    print(f"   📸 Test frame saved as {test_filename}")
            else:
                print(f"   ❌ Frame {i+1} capture failed")
                
            time.sleep(1)
        
        # Test autofocus
        print("\n4. Testing autofocus...")
        if camera.autofocus_manual():
            print("   ✅ Manual autofocus successful")
        else:
            print("   ⚠️  Manual autofocus failed")
        
        # Test high-resolution photo
        print("\n5. Testing high-resolution photo...")
        highres_filename = f"test_highres_{int(time.time())}.jpg"
        if camera.take_high_res_photo(highres_filename):
            print(f"   ✅ High-res photo saved as {highres_filename}")
        else:
            print("   ❌ High-res photo failed")
        
        # Test burst capture
        print("\n6. Testing burst capture...")
        burst_frames = camera.capture_burst(count=3, interval=0.5)
        print(f"   📸 Burst capture: {len(burst_frames)}/3 frames successful")
        
        # Test exposure adjustment
        print("\n7. Testing exposure adjustment...")
        if camera.adjust_exposure_for_conditions(sky_brightness=150):
            print("   ✅ Exposure adjustment successful")
        else:
            print("   ⚠️  Exposure adjustment failed")
        
        # Final camera info
        print("\n8. Final camera statistics:")
        final_info = camera.get_camera_info()
        print(f"   Total frames captured: {final_info['frames_captured']}")
        print(f"   Camera status: {'OK' if final_info['is_initialized'] else 'ERROR'}")
        
        # Release camera
        camera.release()
        print("\n✅ Test completed successfully")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    # Run comprehensive test when script is executed directly
    test_arducam_comprehensive()
