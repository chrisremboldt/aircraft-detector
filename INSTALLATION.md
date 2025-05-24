# Raspberry Pi Aircraft Detection System - Installation and Setup Guide

This guide will walk you through setting up the aircraft detection system using a Raspberry Pi and the 64MP ArduCam with autofocus.

## Hardware Requirements

1. **Raspberry Pi 4** (8GB RAM recommended for optimal performance)
2. **64MP ArduCam with autofocus** ([ArduCam 64MP Hawkeye](https://www.arducam.com/product/arducam-64mp-hawkeye-raspberry-pi-camera-autofocus/))
3. **MicroSD card** (32GB or larger, Class 10)
4. **Power supply** (Official Raspberry Pi power supply recommended)
5. **Weatherproof enclosure** (if installing outdoors)
6. **Tripod or mounting solution** for stable positioning

## Software Setup

### 1. Operating System Installation

1. Download and install the Raspberry Pi Imager from [raspberrypi.org](https://www.raspberrypi.org/software/)
2. Insert your microSD card into your computer
3. Launch Raspberry Pi Imager
4. Choose "Raspberry Pi OS (64-bit)" with desktop
5. Select your microSD card as the destination
6. Click on the gear icon to access advanced options:
   - Set hostname (e.g., `aircraft-detector`)
   - Enable SSH
   - Configure WiFi credentials
   - Set username and password
7. Click "WRITE" to flash the OS
8. Insert the microSD card into your Raspberry Pi and power it on

### 2. Initial Configuration

SSH into your Raspberry Pi:

```bash
ssh username@aircraft-detector.local
```

Update your system:

```bash
sudo apt update
sudo apt upgrade -y
```

### 3. Install Required Dependencies

```bash
# Install system dependencies
sudo apt install -y python3-pip python3-opencv python3-numpy libatlas-base-dev libhdf5-dev libopenjp2-7 libtiff-dev libjpeg-dev libavcodec-dev libavformat-dev libswscale-dev

# Install Python packages
pip3 install opencv-python-headless numpy Flask requests sqlalchemy pillow imutils

# Install ArduCam dependencies
sudo apt install -y build-essential cmake pkg-config libgphoto2-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libopenblas-dev liblapacke-dev
```

### 4. Install ArduCam SDK

```bash
# Clone the ArduCam repository
git clone https://github.com/ArduCAM/MIPI_Camera.git

# Install the SDK
cd MIPI_Camera
make clean && make -j4
sudo make install
```

### 5. Download the Aircraft Detection System

```bash
# Navigate to home directory
cd ~

# Clone the aircraft detection system repository
git clone https://github.com/yourusername/aircraft-detector.git

# Navigate to the project directory
cd aircraft-detector
```

### 6. Configure the Camera

Enable the camera interface:

```bash
sudo raspi-config
```

Navigate to "Interface Options" > "Camera" and enable it, then reboot:

```bash
sudo reboot
```

### 7. Test the Camera

After rebooting, test that your 64MP ArduCam is working:

```bash
cd ~/MIPI_Camera/RPI
python3 arducam_displayer.py
```

If successful, you should see the camera feed displayed.

## Setting Up the Aircraft Detection System

### 1. Create Project Directories

```bash
mkdir -p ~/aircraft-detector/detections
mkdir -p ~/aircraft-detector/templates
```

### 2. Copy Code Files

1. Copy the `pi-aircraft-detector.py` file to `~/aircraft-detector/`
2. Copy the web interface template to `~/aircraft-detector/templates/index.html`

### 3. Make the Script Executable

```bash
chmod +x ~/aircraft-detector/pi-aircraft-detector.py
```

### 4. Configure to Run on Startup (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/aircraft-detector.service
```

Add the following content:

```
[Unit]
Description=Aircraft Detection System
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/aircraft-detector/pi-aircraft-detector.py --web
WorkingDirectory=/home/pi/aircraft-detector
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable aircraft-detector.service
sudo systemctl start aircraft-detector.service
```

## Running the System

### Manual Start

```bash
cd ~/aircraft-detector
python3 pi-aircraft-detector.py --web --display
```

Command-line options:
- `--display`: Show the detection feed on the Raspberry Pi's display
- `--web`: Enable the web interface (accessible at http://aircraft-detector.local:8080)
- `--web-port 8080`: Specify web interface port (default 8080)
- `--save-detections`: Save images of detected aircraft
- `--min-area 25`: Set minimum contour area (default 25)
- `--contrast-threshold 50`: Set minimum contrast threshold (default 50)
- `--confidence-threshold 0.6`: Set detection confidence threshold (default 0.6)

### Access the Web Interface

Open a web browser and navigate to:
```
http://aircraft-detector.local:8080
```

## Mounting and Positioning

For optimal detection:

1. **Position**: Mount the camera with a clear view of the sky
2. **Angle**: Aim slightly above the horizon for maximum range
3. **Stability**: Ensure the camera is stable to reduce false positives from camera movement
4. **Weather Protection**: Use a weatherproof enclosure if mounted outdoors
5. **Power**: Consider a UPS (Uninterruptible Power Supply) for continuous operation

## Troubleshooting

### Camera Not Detected

```bash
# Check if camera is detected
vcgencmd get_camera

# Check I2C devices
i2cdetect -y 1
```

### System Performance Issues

If the system is running slowly:

1. Reduce the resolution in the Camera class initialization
2. Increase the minimum area threshold with `--min-area`
3. Disable the web interface if not needed
4. Consider overclocking your Raspberry Pi (advanced users only)

### Web Interface Not Accessible

1. Check if the service is running:
```bash
sudo systemctl status aircraft-detector.service
```

2. Check firewall settings:
```bash
sudo ufw status
sudo ufw allow 8080/tcp  # If using UFW firewall
```

## Customization

### Adjusting Detection Sensitivity

Edit the following parameters in `pi-aircraft-detector.py` or pass them as command-line arguments:

1. `min_area`: Minimum contour area to consider (higher = fewer false positives)
2. `contrast_threshold`: Minimum contrast difference (higher = fewer false positives)
3. `confidence_threshold`: Detection confidence threshold (higher = fewer false positives)

### Sky Detection Customization

If the sky detection algorithm is not working well in your environment, you can adjust the HSV color thresholds in the `detect_sky` method:

```python
# Adjust these values based on your lighting conditions
lower_blue = np.array([90, 30, 120])  # Hue, Saturation, Value
upper_blue = np.array([140, 255, 255])
```

## Advanced Features

### Adding Notification System

You can extend the system to send notifications when aircraft are detected:

```python
def send_notification(detection):
    # Example using Pushover (install with pip install python-pushover)
    from pushover import Client
    
    client = Client("YOUR_USER_KEY", api_token="YOUR_API_TOKEN")
    client.send_message(f"Aircraft detected with confidence {detection['confidence']:.2f}", 
                        title="Aircraft Detector")
```

Add the function call in the main loop after recording a detection.

### Integrating with Flight Data API

You can enhance the system with flight data APIs like OpenSky Network:

```python
def get_nearby_aircraft():
    import requests
    
    # Your location
    latitude = 51.5074
    longitude = -0.1278
    
    # Define a bounding box (10km radius)
    response = requests.get(f"https://opensky-network.org/api/states/all?lamin={latitude-0.1}&lomin={longitude-0.1}&lamax={latitude+0.1}&lomax={longitude+0.1}")
    
    if response.status_code == 200:
        data = response.json()
        return data["states"]
    else:
        return []
```

## Maintenance

1. **Regular Cleaning**: Keep the camera lens clean
2. **Database Management**: Periodically backup/clear the SQLite database
3. **Updates**: Keep the Raspberry Pi OS and packages updated
4. **Log Rotation**: Implement log rotation to prevent filling up the SD card

## Additional Resources

- [ArduCam Documentation](https://www.arducam.com/docs/raspberry-pi-camera/)
- [OpenCV Documentation](https://docs.opencv.org/4.x/)
- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [Flask Documentation](https://flask.palletsprojects.com/)
