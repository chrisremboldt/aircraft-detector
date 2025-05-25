#!/usr/bin/env python3
"""Simple Raspberry Pi camera interface using OpenCV.

This minimal class captures frames from any Raspberry Pi compatible
camera via the standard V4L2 interface. It avoids Arducam specific
requirements and should work with the official camera module and most
USB webcams.
"""

import cv2


class RPiCamera:
    """Lightweight camera wrapper."""

    def __init__(self, device=0, resolution=(1920, 1080), framerate=30):
        self.device = device
        self.resolution = resolution
        self.framerate = framerate
        self.cap = None

    def initialize(self):
        self.cap = cv2.VideoCapture(self.device)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
        return True

    def capture_frame(self):
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None
