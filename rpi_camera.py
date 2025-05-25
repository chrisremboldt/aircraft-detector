#!/usr/bin/env python3
"""Camera interface using libcamera via Picamera2.

This module provides a minimal wrapper around the Picamera2 library so the rest
of the project can capture frames without depending on OpenCV's VideoCapture.
A fallback to OpenCV is kept for platforms where Picamera2 is unavailable.
"""

import logging
import time
from typing import Optional

import cv2

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except Exception:  # pragma: no cover - library may not be installed in tests
    PICAMERA_AVAILABLE = False

logger = logging.getLogger(__name__)


class RPiCamera:
    """Camera wrapper that prefers libcamera via Picamera2."""

    def __init__(self, resolution=(1296, 972), framerate=30, use_opencv=False, device=0):
        self.resolution = resolution
        self.framerate = framerate
        self.use_opencv = use_opencv or not PICAMERA_AVAILABLE
        self.device = device
        self.picam2: Optional[Picamera2] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_info = None

    def initialize(self):
        """Initialize the camera."""
        if not self.use_opencv:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_video_configuration(
                    main={"size": self.resolution, "format": "RGB888"},
                    controls={"FrameRate": self.framerate},
                )
                self.picam2.configure(config)
                self.picam2.start()
                time.sleep(1)  # warm up
                self.camera_info = {
                    "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                    "fps": self.framerate,
                    "backend": "libcamera",
                }
                logger.info("Camera initialized using Picamera2")
                return True
            except Exception as e:  # pragma: no cover - runtime check
                logger.error(f"Picamera2 initialization failed: {e}")
                self.use_opencv = True

        # Fallback to OpenCV VideoCapture
        logger.info("Falling back to OpenCV VideoCapture")
        self.cap = cv2.VideoCapture(self.device)
        if not self.cap.isOpened():
            logger.error("Failed to open camera with OpenCV")
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
        time.sleep(1)
        backend = (
            self.cap.getBackendName()
            if hasattr(self.cap, "getBackendName")
            else "OpenCV"
        )
        self.camera_info = {
            "resolution": f"{int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
            "backend": backend,
        }
        logger.info(f"Camera initialized using {backend}")
        return True

    def capture_frame(self):
        """Capture a single frame as a NumPy array in BGR format."""
        if self.use_opencv:
            if not self.cap or not self.cap.isOpened():
                return None
            ret, frame = self.cap.read()
            return frame if ret else None
        else:
            if not self.picam2:
                return None
            try:
                frame = self.picam2.capture_array()
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception as e:  # pragma: no cover - runtime check
                logger.error(f"Picamera2 capture failed: {e}")
                return None

    def get_camera_info(self):
        return self.camera_info or {"error": "Camera not initialized"}

    def release(self):
        if self.use_opencv and self.cap:
            self.cap.release()
            self.cap = None
        if not self.use_opencv and self.picam2:
            try:
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None
        logger.info("Camera released")


def test_camera():
    """Basic standalone camera test."""
    logging.basicConfig(level=logging.INFO)
    cam = RPiCamera()
    if not cam.initialize():
        print("Camera initialization failed")
        return
    frame = cam.capture_frame()
    if frame is not None:
        h, w = frame.shape[:2]
        print(f"Captured {w}x{h} frame")
    else:
        print("Failed to capture frame")
    cam.release()


if __name__ == "__main__":
    test_camera()
