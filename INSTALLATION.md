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
   sudo apt install -y python3-opencv python3-flask python3-numpy python3-picamera2
   ```
4. Enable the camera interface using `raspi-config` if it is not already enabled.
5. Verify the camera works with `libcamera-hello` before running the detector.


## Running the Detector

Clone this repository and run:

```bash
python3 pi-aircraft-detector.py --web
```

Open `http://<pi-address>:8080` in your browser to view the web interface.
