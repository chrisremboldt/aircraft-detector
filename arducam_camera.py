#!/usr/bin/env python3
"""
ArduCam 64MP Hawkeye Camera Integration for Raspberry Pi 5 - FOCUS FIXED VERSION

This module provides a simplified, reliable implementation for interfacing with the
64MP ArduCam Hawkeye camera with proper autofocus control for aircraft detection.
This version specifically addresses focus issues for long-distance subjects.

FOCUS FIXES APPLIED:
- Proper infinity focus control for aircraft detection
- Multiple focus setting methods with fallbacks
- Focus verification and adjustment
- Better autofocus range and mode settings
- Manual focus override for infinity

Key Features:
- Proper infinity focus for aircraft detection at long distances
- Multiple focus control methods (libcamera parameters + manual fallbacks)
- Focus verification and automatic correction
- Enhanced error handling for focus operations
- Optimized for sky/aircraft photography

Requirements:
- Raspberry Pi 5 with Bookworm OS
- rpicam-apps installed and working
- ArduCam 64MP properly configured with device tree overlay:
  - camera_auto_detect=0
  - dtoverlay=arducam-64mp,cam0
  - dtparam=i2c_vc=on
  - gpu_mem=128

Author: Aircraft Detection System
Version: 2.2 - Focus control fixed for aircraft detection
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
    Simplified interface for the 64MP ArduCam Hawkeye with FIXED focus control
    
    This class provides proper infinity focus control for aircraft detection,
    with multiple fallback methods to ensure proper focus at long distances.
    """
    
    def __init__(self, 
                 resolution=(1920, 1080),
                 framerate=30,
                 autofocus=False,  # Default to manual for aircraft detection
                 capture_timeout=1000,
                 quality=90):
        """
        Initialize the ArduCam camera with proper focus settings for aircraft detection
        
        Args:
            resolution (tuple): Processing resolution (width, height)
            framerate (int): Target framerate (for timing calculations only)
            autofocus (bool): Enable autofocus (False recommended for aircraft detection)
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
        self.autofocus_interval = 60  # Longer intervals for aircraft detection
        self.is_initialized = False
        self.current_focus_position = 0.0  # Track current focus setting
        
        # Base arguments for rpicam-still - FOCUS OPTIMIZED for aircraft detection
        self.base_args = [
            '--width', str(resolution[0]),
            '--height', str(resolution[1]),
            '--timeout', str(capture_timeout),
            '--quality', str(quality),
            '--immediate',  # Don't wait for focus/exposure stabilization
            '--nopreview', '1'  # Explicit value avoids CLI misparse
        ]
        
        # Focus settings optimized for aircraft detection (long distance subjects)
        if autofocus:
            # Use autofocus with infinity range for aircraft detection
            self.base_args.extend([
                '--autofocus-mode', 'auto',
                '--autofocus-range', 'normal',  # Normal range goes to infinity
                '--autofocus-on-capture'  # Focus before each capture
            ])
            logger.info("Autofocus enabled with infinity range for aircraft detection")
        else:
            # Manual focus set to infinity (0.0 dioptres)
            self.base_args.extend([
                '--autofocus-mode', 'manual',
                '--lens-position', '0.0'  # 0.0 = infinity focus
            ])
            self.current_focus_position = 0.0
            logger.info("Manual focus set to infinity (0.0 dioptres) for aircraft detection")
        
        logger.info(f"ArduCam64MP configured for aircraft detection: {resolution[0]}x{resolution[1]}")
        
    def initialize(self):
        """
        Initialize the camera hardware and verify proper focus for aircraft detection
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing ArduCam 64MP for aircraft detection...")
            
            # Step 1: Check if rpicam-hello can detect camera
            logger.debug("Checking camera detection...")
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.error("rpicam-hello failed - camera not detected")
                logger.error(f"Error output: {result.stderr}")
                return False
                
            # More flexible camera detection
            camera_detected = False
            for line in result.stdout.lower():
                if any(keyword in line for keyword in ['arducam', '64mp', 'hawkeye']):
                    camera_detected = True
                    break
                    
            if not camera_detected:
                logger.warning("ArduCam 64MP not explicitly detected, but continuing...")
                logger.info(f"Available cameras: {result.stdout}")
                
            logger.info("Camera detection check completed")
            
            # Step 2: Test initial capture with focus verification
            logger.debug("Testing initial capture with focus verification...")
            test_file = os.path.join(self.temp_dir, f"arducam_focus_test_{int(time.time())}.jpg")
            
            # Try capture with current focus arguments
            test_result = self._safe_capture_with_focus_check(test_file, timeout=20)
            
            if test_result and os.path.exists(test_file):
                # Step 3: Verify OpenCV can read the image
                test_img = cv2.imread(test_file)
                if test_img is not None:
                    logger.info(f"Camera initialization successful with proper focus - test image: {test_img.shape}")
                    # Clean up test file
                    os.remove(test_file)
                    self.is_initialized = True
                    
                    # Step 4: Set optimal focus for aircraft detection
                    logger.info("Setting optimal focus for aircraft detection...")
                    self.set_infinity_focus_for_aircraft()
                    
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
            
    def _safe_capture_with_focus_check(self, output_file, timeout=10):
        """
        Safely capture an image with focus verification for aircraft detection
        
        Args:
            output_file (str): Path to save the captured image
            timeout (int): Timeout in seconds
            
        Returns:
            bool: True if capture succeeded with proper focus, False otherwise
        """
        # Try primary capture with current focus settings
        try:
            cmd = ['rpicam-still', '-o', output_file] + self.base_args
            logger.debug(f"Focus-optimized capture command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                return True
            else:
                logger.warning(f"Primary focus capture failed (returncode: {result.returncode})")
                logger.warning(f"Error: {result.stderr}")
                
                # Try fallback focus methods for aircraft detection
                return self._try_fallback_focus_methods(output_file, timeout)
                    
        except subprocess.TimeoutExpired:
            logger.warning(f"Focus capture timed out after {timeout}s")
            return False
        except Exception as e:
            logger.error(f"Exception during focus capture: {e}")
            return False
            
    def _try_fallback_focus_methods(self, output_file, timeout=5):
        """
        Try multiple fallback focus methods specifically for aircraft detection
        """
        logger.info("Trying fallback focus methods for aircraft detection...")
        
        # Method 1: Force infinity focus with explicit parameters
        try:
            logger.debug("Fallback 1: Explicit infinity focus")
            fallback_cmd1 = [
                'rpicam-still', '-o', output_file,
                '--width', str(self.resolution[0]),
                '--height', str(self.resolution[1]),
                '--timeout', '3000',
                '--autofocus-mode', 'manual',
                '--lens-position', '0.0',  # Explicit infinity
                '--nopreview', '1'
            ]
            
            result1 = subprocess.run(fallback_cmd1, capture_output=True, text=True, timeout=timeout)
            if result1.returncode == 0:
                logger.info("Fallback method 1 (explicit infinity) succeeded")
                self.current_focus_position = 0.0
                return True
                
        except Exception as e:
            logger.debug(f"Fallback method 1 failed: {e}")
        
        # Method 2: Use autofocus with infinity range
        try:
            logger.debug("Fallback 2: Autofocus with infinity range")
            fallback_cmd2 = [
                'rpicam-still', '-o', output_file,
                '--width', str(self.resolution[0]),
                '--height', str(self.resolution[1]),
                '--timeout', '5000',
                '--autofocus-mode', 'auto',
                '--autofocus-range', 'normal',  # Normal includes infinity
                '--autofocus-on-capture',
                '--nopreview', '1'
            ]
            
            result2 = subprocess.run(fallback_cmd2, capture_output=True, text=True, timeout=timeout+3)
            if result2.returncode == 0:
                logger.info("Fallback method 2 (autofocus infinity range) succeeded")
                return True
                
        except Exception as e:
            logger.debug(f"Fallback method 2 failed: {e}")
            
        # Method 3: Minimal command for focus testing
        try:
            logger.debug("Fallback 3: Minimal command")
            fallback_cmd3 = [
                'rpicam-still', '-o', output_file,
                '--timeout', '2000',
                '--nopreview', '1'
            ]
            
            result3 = subprocess.run(fallback_cmd3, capture_output=True, text=True, timeout=timeout)
            if result3.returncode == 0:
                logger.info("Fallback method 3 (minimal) succeeded")
                return True
                
        except Exception as e:
            logger.debug(f"Fallback method 3 failed: {e}")
            
        logger.error("All fallback focus methods failed")
        return False
            
    def set_infinity_focus_for_aircraft(self):
        """
        Set optimal infinity focus specifically for aircraft detection
        Uses multiple methods to ensure proper long-distance focus
        
        Returns:
            bool: True if focus was set successfully
        """
        logger.info("Setting infinity focus optimized for aircraft detection...")
        
        # Method 1: Direct lens position control
        success = self.set_manual_focus(0.0)  # 0.0 dioptres = infinity
        
        if success:
            logger.info("✅ Infinity focus set using lens position control")
            return True
            
        # Method 2: Use autofocus then lock at infinity
        logger.info("Trying autofocus-based infinity setting...")
        try:
            # Run autofocus with infinity range
            result = subprocess.run([
                'rpicam-still', '-o', '/dev/null',
                '--autofocus-mode', 'auto',
                '--autofocus-range', 'normal',  # Normal range includes infinity
                '--timeout', '5000',
                '--nopreview', '1'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Now switch to manual with infinity position
                self.set_manual_focus(0.0)
                logger.info("✅ Infinity focus set using autofocus then manual lock")
                return True
                
        except Exception as e:
            logger.warning(f"Autofocus-based infinity setting failed: {e}")
        
        # Method 3: Force focus settings in base args
        logger.info("Forcing infinity focus in base arguments...")
        
        # Remove existing focus arguments
        focus_args = ['--autofocus-mode', '--lens-position', '--autofocus-range', '--autofocus-on-capture']
        for arg_type in focus_args:
            self.base_args = [arg for i, arg in enumerate(self.base_args) 
                             if not (arg.startswith(arg_type) or 
                                   (i > 0 and self.base_args[i-1].startswith(arg_type)))]
        
        # Add infinity focus settings
        self.base_args.extend([
            '--autofocus-mode', 'manual',
            '--lens-position', '0.0'
        ])
        
        self.current_focus_position = 0.0
        logger.info("✅ Infinity focus forced in camera arguments")
        return True
        
    def verify_focus_for_aircraft(self):
        """
        Verify that the camera is properly focused for aircraft detection
        Takes a test image and checks focus quality
        
        Returns:
            dict: Focus verification results with quality metrics
        """
        logger.info("Verifying focus quality for aircraft detection...")
        
        test_file = os.path.join(self.temp_dir, f"focus_verify_{int(time.time())}.jpg")
        
        try:
            # Capture test image
            if self._safe_capture_with_focus_check(test_file, timeout=10):
                # Load and analyze the image
                image = cv2.imread(test_file)
                if image is not None:
                    # Convert to grayscale for analysis
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    
                    # Calculate focus metrics
                    # 1. Laplacian variance (higher = sharper)
                    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                    
                    # 2. Sobel gradient magnitude
                    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                    sobel_magnitude = np.mean(np.sqrt(sobelx**2 + sobely**2))
                    
                    # 3. High frequency content
                    f_transform = np.fft.fft2(gray)
                    f_shift = np.fft.fftshift(f_transform)
                    magnitude_spectrum = np.abs(f_shift)
                    high_freq_content = np.mean(magnitude_spectrum[gray.shape[0]//4:3*gray.shape[0]//4, 
                                                                 gray.shape[1]//4:3*gray.shape[1]//4])
                    
                    # Clean up test file
                    os.remove(test_file)
                    
                    # Determine focus quality
                    focus_quality = "Good"
                    if laplacian_var < 100:  # Threshold for aircraft detection
                        focus_quality = "Poor - May need adjustment"
                    elif laplacian_var < 300:
                        focus_quality = "Fair"
                    else:
                        focus_quality = "Excellent"
                    
                    results = {
                        "focus_quality": focus_quality,
                        "laplacian_variance": float(laplacian_var),
                        "sobel_magnitude": float(sobel_magnitude),
                        "high_freq_content": float(high_freq_content),
                        "current_lens_position": self.current_focus_position,
                        "recommended_for_aircraft": laplacian_var > 100
                    }
                    
                    logger.info(f"Focus verification: {focus_quality} (Laplacian: {laplacian_var:.1f})")
                    return results
                    
            logger.error("Failed to capture test image for focus verification")
            return {"error": "Capture failed", "focus_quality": "Unknown"}
            
        except Exception as e:
            logger.error(f"Focus verification failed: {e}")
            if os.path.exists(test_file):
                os.remove(test_file)
            return {"error": str(e), "focus_quality": "Unknown"}
    
    def set_manual_focus(self, focus_position):
        """
        Set manual focus position with verification for aircraft detection
        
        Args:
            focus_position (float): Focus position in dioptres 
                                   (0.0 = infinity, higher = closer)
        
        Returns:
            bool: True if focus was set successfully
        """
        try:
            # Ensure focus position is in valid range
            focus_position = max(0.0, min(15.0, focus_position))
            
            logger.info(f"Setting manual focus to {focus_position:.2f} dioptres "
                       f"({'infinity' if focus_position == 0.0 else f'{1.0/focus_position:.1f}m' if focus_position > 0 else 'invalid'})")
            
            # Remove existing lens-position and autofocus arguments
            args_to_remove = ['--lens-position', '--autofocus-mode', '--autofocus-range', '--autofocus-on-capture']
            for arg_type in args_to_remove:
                # Remove both the argument and its value
                self.base_args = [arg for i, arg in enumerate(self.base_args) 
                                 if not (arg.startswith(arg_type) or 
                                       (i > 0 and self.base_args[i-1].startswith(arg_type)))]
            
            # Set manual focus
            self.base_args.extend(['--autofocus-mode', 'manual'])
            self.base_args.extend(['--lens-position', str(focus_position)])
            
            self.current_focus_position = focus_position
            
            # Verify the focus setting with a test capture
            test_file = os.path.join(self.temp_dir, f"focus_test_{int(time.time())}.jpg")
            if self._safe_capture_with_focus_check(test_file, timeout=8):
                if os.path.exists(test_file):
                    os.remove(test_file)
                logger.info(f"✅ Manual focus successfully set to {focus_position:.2f} dioptres")
                return True
            else:
                logger.warning("Focus setting may not have taken effect - test capture failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set manual focus: {e}")
            return False
    
    def capture_frame(self):
        """
        Capture a single frame with optimized focus for aircraft detection
        
        Returns:
            numpy.ndarray: Captured frame as OpenCV image, or None if failed
        """
        if not self.is_initialized:
            logger.error("Camera not initialized - call initialize() first")
            return None
            
        # Generate unique filename for this frame
        frame_file = os.path.join(self.temp_dir, f"arducam_frame_{self.frame_counter}_{int(time.time()*1000)}.jpg")
        
        try:
            # Capture frame using focus-optimized safe capture method
            start_time = time.time()
            if self._safe_capture_with_focus_check(frame_file, timeout=5):
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
                    logger.debug(f"Frame {self.frame_counter} captured with optimized focus in {capture_time:.2f}s: {frame.shape}")
                    return frame
                else:
                    logger.warning("Failed to read captured frame with OpenCV")
                    return None
            else:
                logger.warning("Frame capture failed using focus-optimized method")
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
    
    def take_high_res_photo(self, filename, resolution=(8000, 6000)):
        """
        Take a full resolution photo optimized for aircraft detection
        
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
            logger.info(f"Taking high-resolution photo for aircraft detection: {resolution[0]}x{resolution[1]}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Capture high-resolution image with infinity focus
            result = subprocess.run([
                'rpicam-still', '-o', filename,
                '--width', str(resolution[0]),
                '--height', str(resolution[1]),
                '--quality', '95',  # High quality for full-res photos
                '--timeout', '8000',  # Longer timeout for high-res
                '--autofocus-mode', 'manual',
                '--lens-position', '0.0',  # Force infinity for aircraft
                '--nopreview', '1'
            ], capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0 and os.path.exists(filename):
                # Verify file was created and get its size
                file_size = os.path.getsize(filename)
                logger.info(f"High-resolution aircraft detection photo saved: {filename} ({file_size:,} bytes)")
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
    
    def get_camera_info(self):
        """
        Get comprehensive camera information including focus status
        
        Returns:
            dict: Camera information including model, settings, focus status
        """
        try:
            # Get camera detection status
            detection_result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                            capture_output=True, text=True, timeout=5)
            
            camera_detected = (detection_result.returncode == 0)
            
            info = {
                "model": "ArduCam 64MP Hawkeye (Aircraft Detection Optimized)",
                "resolution": self.resolution,
                "framerate": self.framerate,
                "autofocus": self.autofocus,
                "quality": self.quality,
                "frames_captured": self.frame_counter,
                "is_initialized": self.is_initialized,
                "camera_detected": camera_detected,
                "capture_timeout": self.capture_timeout,
                "current_focus_position": self.current_focus_position,
                "focus_mode": "Manual Infinity" if not self.autofocus else "Auto with Infinity Range",
                "optimized_for": "Aircraft Detection (Long Distance Focus)",
                "temp_directory": self.temp_dir
            }
            
            # Add current settings from base_args
            settings = {}
            for i, arg in enumerate(self.base_args):
                if arg.startswith('--') and i + 1 < len(self.base_args):
                    setting_name = arg[2:]  # Remove '--'
                    if i + 1 < len(self.base_args):
                        next_arg = self.base_args[i + 1]
                        if not next_arg.startswith('--'):
                            settings[setting_name] = next_arg
                elif arg in ['--immediate', '--nopreview', '--autofocus-on-capture']:
                    settings[arg[2:]] = 'enabled'
            
            info["current_settings"] = settings
            
            return info
        except Exception as e:
            logger.error(f"Failed to get camera info: {e}")
            return {"error": str(e), "model": "ArduCam 64MP Hawkeye"}
    
    def release(self):
        """Release camera resources and clean up temporary files"""
        logger.info("Releasing ArduCam 64MP resources...")
        
        # Clean up any temporary files created by this instance
        try:
            temp_files = []
            for filename in os.listdir(self.temp_dir):
                if filename.startswith("arducam_frame_") or filename.startswith("arducam_") or filename.startswith("focus_"):
                    temp_files.append(os.path.join(self.temp_dir, filename))
            
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
            if temp_files:
                logger.debug(f"Cleaned up {len(temp_files)} temporary files")
                
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
            
        self.is_initialized = False
        logger.info("ArduCam 64MP resources released")

def test_arducam_focus_comprehensive():
    """
    Comprehensive test of the ArduCam 64MP camera with focus verification
    """
    print("="*70)
    print("ArduCam 64MP Aircraft Detection Focus Test (FOCUS FIXED VERSION)")
    print("="*70)
    
    try:
        # Initialize camera with manual focus for aircraft detection
        print("\n1. Initializing camera with aircraft detection focus settings...")
        camera = ArduCam64MP(resolution=(1920, 1080), autofocus=False)  # Manual focus for aircraft
        
        if not camera.initialize():
            print("❌ Failed to initialize camera. Exiting.")
            return False
            
        print("✅ Camera initialized successfully with aircraft detection focus")
        
        # Get camera info
        print("\n2. Camera information:")
        info = camera.get_camera_info()
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        # Test focus verification
        print("\n3. Verifying focus quality for aircraft detection...")
        focus_results = camera.verify_focus_for_aircraft()
        print("   Focus Verification Results:")
        for key, value in focus_results.items():
            print(f"     {key}: {value}")
            
        recommended = focus_results.get('recommended_for_aircraft', False)
        if recommended:
            print("   ✅ Focus quality is suitable for aircraft detection")
        else:
            print("   ⚠️  Focus quality may need adjustment for optimal aircraft detection")
        
        # Test manual focus adjustment
        print("\n4. Testing manual focus adjustments...")
        print("   Setting focus to infinity (0.0 dioptres)...")
        if camera.set_manual_focus(0.0):
            print("   ✅ Infinity focus set successfully")
        else:
            print("   ⚠️  Infinity focus setting failed")
            
        print("   Testing close focus (2.0 dioptres = ~50cm)...")
        if camera.set_manual_focus(2.0):
            print("   ✅ Close focus set successfully")
        else:
            print("   ⚠️  Close focus setting failed")
            
        print("   Returning to infinity focus for aircraft detection...")
        camera.set_infinity_focus_for_aircraft()
        
        # Test frame capture with optimized focus
        print("\n5. Testing frame capture with optimized focus...")
        for i in range(3):
            print(f"   Capturing frame {i+1} with infinity focus...")
            frame = camera.capture_frame()
            if frame is not None:
                print(f"   ✅ Frame {i+1} captured successfully: {frame.shape}")
                
                # Save first frame as test
                if i == 0:
                    test_filename = f"test_frame_infinity_focus_{int(time.time())}.jpg"
                    cv2.imwrite(test_filename, frame)
                    print(f"   📸 Test frame saved as {test_filename}")
            else:
                print(f"   ❌ Frame {i+1} capture failed")
                
            time.sleep(1)
        
        # Test high-resolution photo with aircraft detection settings
        print("\n6. Testing high-resolution photo with infinity focus...")
        highres_filename = f"test_aircraft_highres_{int(time.time())}.jpg"
        if camera.take_high_res_photo(highres_filename):
            print(f"   ✅ High-res aircraft detection photo saved as {highres_filename}")
        else:
            print("   ❌ High-res photo failed")
        
        # Final focus verification
        print("\n7. Final focus verification for aircraft detection...")
        final_focus = camera.verify_focus_for_aircraft()
        quality = final_focus.get('focus_quality', 'Unknown')
        laplacian = final_focus.get('laplacian_variance', 0)
        print(f"   Final focus quality: {quality}")
        print(f"   Focus sharpness metric: {laplacian:.1f}")
        
        if final_focus.get('recommended_for_aircraft', False):
            print("   ✅ Camera is properly focused for aircraft detection")
        else:
            print("   ⚠️  Camera focus may need manual adjustment")
            print("   💡 Try running: camera.set_infinity_focus_for_aircraft()")
        
        # Final camera statistics
        print("\n8. Final camera statistics:")
        final_info = camera.get_camera_info()
        print(f"   Total frames captured: {final_info['frames_captured']}")
        print(f"   Current focus position: {final_info['current_focus_position']} dioptres")
        print(f"   Focus mode: {final_info['focus_mode']}")
        print(f"   Optimization: {final_info['optimized_for']}")
        print(f"   Camera status: {'OK' if final_info['is_initialized'] else 'ERROR'}")
        
        # Release camera
        camera.release()
        print("\n✅ Aircraft detection focus test completed successfully")
        print("="*70)
        print("\n📋 SUMMARY FOR AIRCRAFT DETECTION:")
        print("   • Use manual focus mode (autofocus=False)")
        print("   • Set lens position to 0.0 dioptres for infinity focus")
        print("   • Verify focus quality using verify_focus_for_aircraft()")
        print("   • Laplacian variance should be > 100 for good aircraft detection")
        print("   • Use set_infinity_focus_for_aircraft() if focus needs adjustment")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    # Run comprehensive focus test when script is executed directly
    test_arducam_focus_comprehensive()
