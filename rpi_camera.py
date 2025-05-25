#!/usr/bin/env python3
"""Simple Raspberry Pi camera interface using OpenCV.

This minimal class captures frames from any Raspberry Pi compatible
camera via the standard V4L2 interface. It avoids Arducam specific
requirements and should work with the official camera module and most
USB webcams.

The initial implementation used ``cv2.VideoCapture`` with default
settings.  On some Pi models this results in repeated ``read`` failures
even though ``VideoCapture`` reports it opened successfully.  The camera
often requires an explicit FOURCC setting (``MJPG``) when accessed via
the V4L2 compatibility layer provided by ``libcamera``.  Without this the
driver may deliver frames in an unsupported raw format and OpenCV will
return ``ret=False``.

This module now allows specifying a ``fourcc`` code and applies it during
initialisation to improve compatibility with ``libcamera`` devices.
"""

import cv2
import logging
import subprocess
import time


class RPiCamera:
    """Lightweight camera wrapper for V4L2/``libcamera`` devices."""

    def __init__(self, device=0, resolution=(1920, 1080), framerate=30,
                 fourcc="MJPG", use_libcamera=False,
                 loopback_device="/dev/video10"):
        self.device = device
        self.resolution = resolution
        self.framerate = framerate
        self.fourcc = fourcc
        self.cap = None
        self.use_libcamera = use_libcamera
        self.loopback_device = loopback_device
        self.bridge_process = None

    def _start_libcamera_bridge(self):
        """Spawn libcamera-vid to pipe frames to a v4l2loopback device."""
        cmd = [
            "libcamera-vid",
            "-n",
            "--width", str(self.resolution[0]),
            "--height", str(self.resolution[1]),
            "--framerate", str(self.framerate),
            "--codec", "mjpeg",
            "-t", "0",
            "-o", self.loopback_device,
        ]
        try:
            self.bridge_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            # Give libcamera time to create the stream
            time.sleep(1)
        except FileNotFoundError:
            logging.error("libcamera-vid not found. Is it installed?")

    def initialize(self):
        """Initialise the camera and apply configuration."""

        capture_device = self.device
        if self.use_libcamera:
            self._start_libcamera_bridge()
            capture_device = self.loopback_device

        self.cap = cv2.VideoCapture(capture_device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            return False

        # Configure stream properties.  Not all properties are honoured by the
        # driver but failures here are non-fatal.
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
        try:
            fourcc_val = cv2.VideoWriter_fourcc(*self.fourcc)
            self.cap.set(cv2.CAP_PROP_FOURCC, fourcc_val)
        except Exception:
            pass

        # Give the camera a moment to warm up without requiring a GUI
        time.sleep(0.1)
        return True

    def capture_frame(self):
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        if not ret:
            logging.warning("Frame capture failed")
            return None
        return frame

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.bridge_process:
            self.bridge_process.terminate()
            try:
                self.bridge_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.bridge_process.kill()
            self.bridge_process = None
