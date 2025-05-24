# Raspberry Pi Aircraft Detection System - Installation and Setup Guide

This guide covers installing the aircraft detection system on a **Raspberry Pi 5** with the **64MP ArduCam Hawkeye** camera.

## Hardware Requirements

1. **Raspberry Pi 5** (8GB RAM recommended)
2. **64MP ArduCam with autofocus** ([ArduCam 64MP Hawkeye](https://www.arducam.com/product/arducam-64mp-hawkeye-raspberry-pi-camera-autofocus/))
3. **MicroSD card** (32GB+ Class 10)
4. **Official Raspberry Pi 5 power supply** (27W USB‑C)
5. **Weatherproof enclosure** if installing outdoors
6. **Tripod or mounting solution**

## Software Setup

### 1. Operating System Installation

1. Install the Raspberry Pi Imager from [raspberrypi.org](https://www.raspberrypi.org/software/)
2. Insert the microSD card
3. Launch the imager and choose **"Raspberry Pi OS (64‑bit)"** with desktop (Bookworm or later)
4. Select the card and open the gear icon to set advanced options (hostname, SSH, WiFi, user credentials)
5. Click **WRITE** and then boot the Pi with the card inserted

### 2. Initial Configuration

SSH into the Pi and update packages:

```bash
ssh username@aircraft-detector.local
sudo apt update
sudo apt upgrade -y
```

### 3. Hardware Connection

The ArduCam 64MP uses the 15‑pin connector. On the Pi 5 the two camera sockets are located between the Ethernet and HDMI ports. Connect the ribbon cable with the silver contacts facing the Ethernet port. Check your ArduCam board for the correct orientation (top-contact vs bottom-contact).

### 4. Camera Configuration

Edit `/boot/firmware/config.txt` and add the following lines:

```
camera_auto_detect=0
# ArduCam 64MP overlay - use cam0 on Pi 5
dtoverlay=arducam-64mp,cam0
dtparam=i2c_vc=on
# GPU memory required for camera
gpu_mem=128
```

Reboot the Pi after saving the file:

```bash
sudo reboot
```

### 5. Install ArduCam Packages

Install the official ArduCam packages that provide the Pi 5 libcamera support:

```bash
wget -O install_pivariety_pkgs.sh https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
chmod +x install_pivariety_pkgs.sh
./install_pivariety_pkgs.sh -p libcamera_dev
./install_pivariety_pkgs.sh -p libcamera_apps
```

### 6. Verify Camera Installation

List cameras and run a quick preview to make sure the ArduCam is detected:

```bash
rpicam-hello --list-cameras
rpicam-hello --timeout 5000
rpicam-still -o test.jpg --timeout 2000
rpicam-vid -t 5000 -o test.h264
```

### 7. Install Required Dependencies

```bash
sudo apt install -y python3-pip python3-opencv python3-numpy python3-picamera2 libatlas-base-dev
pip3 install --break-system-packages opencv-python-headless numpy Flask requests sqlalchemy pillow imutils
```

### 8. Download the Aircraft Detection System

```bash
cd ~
git clone https://github.com/chrisremboldt/aircraft-detector.git
cd aircraft-detector
```

## Camera Integration Methods

The system supports two camera integration options:

1. **rpicam-apps with subprocess** (recommended)
2. **picamera2 library**

The snippet below tests rpicam with OpenCV:

```python
import subprocess, cv2
res = subprocess.run(['rpicam-still', '-o', '/tmp/test.jpg', '--timeout', '1000'], capture_output=True, text=True)
if res.returncode == 0:
    img = cv2.imread('/tmp/test.jpg')
    print('SUCCESS:', img.shape if img is not None else 'Image capture failed')
else:
    print('rpicam-still failed')
```

## Setting Up the Aircraft Detection System

### 1. Create Project Directories

```bash
mkdir -p ~/aircraft-detector/detections
mkdir -p ~/aircraft-detector/templates
mkdir -p ~/aircraft-detector/logs
```

### 2. Copy Code Files

Copy `pi-aircraft-detector.py` to `~/aircraft-detector/` and the web template to `~/aircraft-detector/templates/index.html`.

### 3. Make the Script Executable

```bash
chmod +x ~/aircraft-detector/pi-aircraft-detector.py
```

### 4. Configure to Run on Startup (Optional)

Create `/etc/systemd/system/aircraft-detector.service` with:

```
[Unit]
Description=Aircraft Detection System
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/aircraft-detector/aircraft-detector/pi-aircraft-detector.py --web
WorkingDirectory=/home/aircraft-detector/aircraft-detector
StandardOutput=inherit
StandardError=inherit
Restart=always
User=aircraft-detector
Environment=PATH=/usr/bin:/usr/local/bin

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl enable aircraft-detector.service
sudo systemctl start aircraft-detector.service
```

## Running the System

To start manually:

```bash
cd ~/aircraft-detector
python3 pi-aircraft-detector.py --web --display
```

Useful command-line options:
- `--display` – show the detection feed locally
- `--web` – enable the web interface (default port 8080)
- `--web-port 8080` – specify a different port
- `--save-detections` – store images of detections
- `--resolution 1920x1080` – set camera resolution
- `--fps 30` – set capture frame rate
- `--autofocus` – enable autofocus for ArduCam
- `--min-area 500` – minimum contour area
- `--confidence-threshold 0.3` – detection confidence

Access the web interface at:
```
http://aircraft-detector.local:8080
```

## Troubleshooting

### Camera Not Detected

```bash
rpicam-hello --list-cameras
```

If no cameras are listed, check `/boot/firmware/config.txt` for the parameters above and verify the ribbon cable connection. You can also check I2C detection with:

```bash
sudo i2cdetect -y 10
```

A device should appear at address `1a`. Boot messages can be inspected with:

```bash
dmesg | grep -i "arducam\|camera"
```

### Common Configuration Issues

1. Use `cam0` in the overlay on Pi 5
2. Set `camera_auto_detect=0` to avoid conflicts
3. Edit `/boot/firmware/config.txt` (not `/boot/config.txt`)
4. Ensure `gpu_mem=128` or higher

### System Performance Issues

Lower the resolution or frame rate if the Pi struggles, or disable the web interface.

### Web Interface Not Accessible

Check the service status and firewall rules:

```bash
sudo systemctl status aircraft-detector.service
sudo ufw status
sudo ufw allow 8080/tcp
```

## Pi 5 Specific Optimizations

- Consider increasing `gpu_mem` to 256 for smoother previews
- Use active cooling; monitor temperature with `vcgencmd measure_temp`

## Camera Optimization for Aircraft Detection

- **High accuracy:** `--resolution 3840x2160`
- **Balanced:** `--resolution 1920x1080` *(recommended)*
- **Performance:** `--resolution 1280x720`

Continuous autofocus can be enabled with:

```bash
rpicam-still --autofocus-mode continuous
```

For manual focus at infinity:

```bash
rpicam-still --autofocus-mode manual --lens-position 0
```

## Mounting and Positioning

1. Mount with an unobstructed view of the sky (ideally 270°)
2. Angle 15–30° above the horizon
3. Use a rigid mount to avoid movement
4. Use a weatherproof enclosure outdoors
5. Consider a UPS for continuous power

## Additional Resources

- [ArduCam Pi 5 Documentation](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/64MP-Hawkeye/)
- [Raspberry Pi 5 Camera Guide](https://www.raspberrypi.org/documentation/accessories/camera.html)
- [libcamera/rpicam-apps Documentation](https://www.raspberrypi.org/documentation/computers/camera_software.html)
- [OpenCV Documentation](https://docs.opencv.org/4.x/)

## Version Compatibility

- **Raspberry Pi OS:** Bookworm (2023‑12‑05) or later
- **Python:** 3.11+
- **OpenCV:** 4.5.1+
- **libcamera:** 0.5.0+
