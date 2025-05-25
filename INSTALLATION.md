# Raspberry Pi Aircraft Detection System - Installation Guide

This guide covers installing the aircraft detection system on a Raspberry Pi with the official camera module.

## Hardware Requirements

- Raspberry Pi 5 (other models may work)
- Raspberry Pi camera module rev 1.3 or newer
- MicroSD card (32GB or larger)
- Official Raspberry Pi power supply

## Software Setup

1. Install Raspberry Pi OS (64-bit) using the Raspberry Pi Imager.
2. Boot the Pi and update packages:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```
3. Install dependencies:
   ```bash
   sudo apt install -y python3-opencv python3-flask python3-numpy
   ```
4. Enable the camera interface using `raspi-config` if it is not already enabled.
5. If using the libcamera stack (default on recent Raspberry Pi OS releases),
   ensure the V4L2 compatibility driver is loaded:
   ```bash
   sudo modprobe bcm2835-v4l2
   ```
6. If OpenCV cannot read frames, install the v4l2loopback module and create a
   virtual camera device for bridging:
   ```bash
   sudo apt install v4l2loopback-dkms
   sudo modprobe v4l2loopback video_nr=10 card_label="camera-bridge" exclusive_caps=1
   ```

## Running the Detector

Clone this repository and run:

```bash
python3 pi-aircraft-detector.py --web [--libcamera-bridge]
```

Open `http://<pi-address>:8080` in your browser to view the web interface.
