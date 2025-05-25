#!/usr/bin/env python3
"""
Raspberry Pi camera interface optimized for libcamera systems.
Compatible with OV5647 and other Pi camera modules using the modern libcamera stack.
"""
import cv2
import logging
import time
import subprocess
import os

logger = logging.getLogger(__name__)

class RPiCamera:
    """Raspberry Pi camera wrapper optimized for libcamera and OV5647."""
    
    def __init__(self, device=0, resolution=(1296, 972), framerate=30, fourcc="MJPG"):
        """
        Initialize camera with OV5647-optimized defaults.
        
        Args:
            device: Camera device index (usually 0)
            resolution: Camera resolution (1296x972 is good balance for OV5647)
            framerate: Target framerate
            fourcc: Video codec (MJPG works well with libcamera)
        """
        self.device = device
        self.resolution = resolution
        self.framerate = framerate
        self.fourcc = fourcc
        self.cap = None
        self.camera_info = None
        
    def _detect_ov5647_modes(self):
        """Detect available OV5647 camera modes from libcamera."""
        try:
            result = subprocess.run(['libcamera-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Parse the output for OV5647 modes
                lines = result.stdout.split('\n')
                modes = []
                for line in lines:
                    if 'fps' in line and 'x' in line:
                        # Extract resolution and fps
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            resolution = parts[0]
                            fps = parts[2]
                            modes.append((resolution, fps))
                logger.info(f"Detected camera modes: {modes}")
                return modes
        except Exception as e:
            logger.warning(f"Could not detect camera modes: {e}")
        return []
        
    def initialize(self):
        """Initialize the camera with libcamera-optimized settings."""
        logger.info(f"Initializing OV5647 camera at {self.resolution}")
        
        # Detect available camera modes
        modes = self._detect_ov5647_modes()
        
        # Try multiple initialization strategies for libcamera compatibility
        strategies = [
            # Strategy 1: Direct V4L2 with MJPG
            (cv2.CAP_V4L2, "MJPG"),
            # Strategy 2: Direct V4L2 with YUYV (uncompressed)
            (cv2.CAP_V4L2, "YUYV"),
            # Strategy 3: Any backend with MJPG
            (cv2.CAP_ANY, "MJPG"),
            # Strategy 4: Any backend with default codec
            (cv2.CAP_ANY, None),
        ]
        
        for backend, codec in strategies:
            logger.info(f"Trying backend: {backend}, codec: {codec}")
            
            try:
                self.cap = cv2.VideoCapture(self.device, backend)
                
                if not self.cap.isOpened():
                    logger.warning(f"Failed to open camera with backend {backend}")
                    continue
                
                # Configure the camera
                success = self._configure_camera(codec)
                
                if success and self._test_frame_capture():
                    logger.info(f"✓ Camera initialized successfully with backend {backend}, codec {codec}")
                    self._log_camera_info()
                    return True
                else:
                    logger.warning(f"Camera opened but frame capture failed with backend {backend}")
                    self.cap.release()
                    
            except Exception as e:
                logger.error(f"Exception with backend {backend}: {e}")
                if self.cap:
                    self.cap.release()
                    
        logger.error("Failed to initialize camera with any strategy")
        return False
        
    def _configure_camera(self, codec=None):
        """Configure camera properties for OV5647."""
        if not self.cap:
            return False
            
        try:
            # Set codec first if specified
            if codec:
                fourcc_val = cv2.VideoWriter_fourcc(*codec)
                self.cap.set(cv2.CAP_PROP_FOURCC, fourcc_val)
                
            # Set resolution - OV5647 supports these native modes:
            # 640x480, 1296x972, 1920x1080, 2592x1944
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            # Set framerate (OV5647 can do up to 46fps at 1296x972)
            target_fps = min(self.framerate, 46) if self.resolution == (1296, 972) else self.framerate
            self.cap.set(cv2.CAP_PROP_FPS, target_fps)
            
            # Optimize for libcamera compatibility
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
            
            # Additional OV5647-specific optimizations
            try:
                # Auto exposure and white balance
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # Enable auto exposure
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # OV5647 is fixed focus
            except:
                pass  # These might not be supported
                
            # Warm-up period for libcamera
            logger.info("Warming up camera...")
            time.sleep(2.0)
            
            # Flush initial frames (libcamera often has stale frames)
            for i in range(10):
                ret, frame = self.cap.read()
                if ret:
                    logger.debug(f"Flushed frame {i+1}")
                time.sleep(0.1)
                
            return True
            
        except Exception as e:
            logger.error(f"Camera configuration failed: {e}")
            return False
            
    def _test_frame_capture(self):
        """Test frame capture with multiple attempts."""
        logger.info("Testing frame capture...")
        
        for attempt in range(5):
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    logger.info(f"✓ Frame capture test passed: {w}x{h}, attempt {attempt+1}")
                    return True
                else:
                    logger.warning(f"Frame capture attempt {attempt+1} failed: ret={ret}, frame={type(frame)}")
                    
            except Exception as e:
                logger.warning(f"Frame capture attempt {attempt+1} exception: {e}")
                
            time.sleep(0.2)  # Wait between attempts
            
        logger.error("All frame capture tests failed")
        return False
        
    def _log_camera_info(self):
        """Log detailed camera information."""
        if not self.cap:
            return
            
        try:
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            backend = self.cap.getBackendName() if hasattr(self.cap, 'getBackendName') else 'Unknown'
            
            self.camera_info = {
                "device": self.device,
                "resolution": f"{actual_width}x{actual_height}",
                "fps": actual_fps,
                "backend": backend,
                "fourcc": self.fourcc
            }
            
            logger.info(f"Camera configured: {actual_width}x{actual_height} @ {actual_fps:.1f}fps via {backend}")
            
        except Exception as e:
            logger.warning(f"Could not retrieve camera info: {e}")
            
    def capture_frame(self):
        """Capture a frame with robust error handling."""
        if not self.cap or not self.cap.isOpened():
            return None
            
        try:
            ret, frame = self.cap.read()
            
            if ret and frame is not None and frame.size > 0:
                return frame
            else:
                # Log detailed failure info for debugging
                logger.debug(f"Frame capture failed: ret={ret}, frame_valid={frame is not None}")
                return None
                
        except Exception as e:
            logger.error(f"Exception during frame capture: {e}")
            return None
            
    def get_camera_info(self):
        """Get camera information."""
        if self.camera_info:
            return self.camera_info
        else:
            return {"error": "Camera not initialized"}
            
    def release(self):
        """Release camera resources."""
        if self.cap:
            self.cap.release()
            self.cap = None
            logger.info("Camera released")

def test_camera():
    """Test camera functionality with OV5647-optimized settings."""
    print("Testing OV5647 camera...")
    
    # Test with OV5647's native 1296x972 mode (good balance of resolution and performance)
    camera = RPiCamera(resolution=(1296, 972), framerate=30)
    
    if not camera.initialize():
        print("❌ Failed to initialize camera")
        return False
        
    print("✅ Camera initialized successfully")
    print("Camera info:", camera.get_camera_info())
    
    # Test frame capture
    print("\nTesting frame capture...")
    success_count = 0
    
    for i in range(10):
        frame = camera.capture_frame()
        if frame is not None:
            h, w = frame.shape[:2]
            print(f"Frame {i+1}: ✅ {w}x{h}")
            success_count += 1
        else:
            print(f"Frame {i+1}: ❌ Failed")
            
        time.sleep(0.1)
        
    print(f"\nSuccess rate: {success_count}/10 frames")
    
    camera.release()
    
    if success_count >= 8:
        print("✅ Camera test PASSED")
        return True
    else:
        print("❌ Camera test FAILED")
        return False

if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    test_camera()
