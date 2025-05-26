# Raspberry Pi Aircraft Detection System - Installation Guide

This guide covers installing the aircraft detection system on a Raspberry Pi with the official camera module.

## Hardware Requirements

- Raspberry Pi 5 (other models may work)
- Raspberry Pi camera module rev 1.3 or newer
- MicroSD card (32GB or larger)
- Official Raspberry Pi power supply
- RTL-SDR dongle (RTL-SDR Blog V4 recommended)
- 1090MHz ADS-B antenna (optional, improves reception range)

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

## 4. Install ADS-B Reception Tools

### Install RTL-SDR Tools
```bash
sudo apt install -y rtl-sdr librtlsdr-dev
```

Test your RTL-SDR device:
```bash
rtl_test
```
You should see output showing your RTL-SDR device is detected and working.

### Install readsb (ADS-B Decoder)

Since readsb isn't available as a package, we'll compile it from source:

```bash
# Install build dependencies
sudo apt install -y git build-essential pkg-config libusb-1.0-0-dev librtlsdr-dev libncurses5-dev zlib1g-dev

# Clone and build readsb
git clone https://github.com/wiedehopf/readsb.git
cd readsb
make

# Install the binary
sudo cp readsb /usr/local/bin/
sudo chmod +x /usr/local/bin/readsb
```

### Configure readsb Service

Create a readsb user and directories:
```bash
# Create readsb user
sudo useradd --system --no-create-home --shell /bin/false readsb

# Create runtime directory
sudo mkdir -p /var/run/readsb
sudo chown readsb:readsb /var/run/readsb

# Add readsb user to plugdev group (for RTL-SDR access)
sudo usermod -a -G plugdev readsb
```

Create the systemd service file:
```bash
sudo nano /etc/systemd/system/readsb.service
```

Add this content (replace YOUR_LATITUDE and YOUR_LONGITUDE with your actual coordinates):
```ini
[Unit]
Description=readsb ADS-B decoder
After=network.target

[Service]
Type=simple
User=readsb
Group=readsb
ExecStart=/usr/local/bin/readsb --device-type rtlsdr --gain -10 --lat YOUR_LATITUDE --lon YOUR_LONGITUDE --write-json /var/run/readsb --write-json-every 1 --json-location-accuracy 2 --net --net-http-port 8080 --quiet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Example coordinates format:** For Nashville, TN use:
- `--lat 36.0200 --lon -86.7000`

Enable and start readsb service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable readsb
sudo systemctl start readsb
```

5. Enable the camera interface using `raspi-config` if it is not already enabled.
6. Verify the camera works with `libcamera-hello` before running the detector.


## Running the Detector

Clone this repository and run:

```bash
# Basic operation
python3 pi-aircraft-detector.py --web

# With ADS-B integration (replace with your coordinates)
python3 pi-aircraft-detector.py --web --enable-adsb --camera-lat 36.02316650611701 --camera-lon -86.70226195080218
```

Open `http://<pi-address>:8080` in your browser to view the web interface.

## systemd Service Configuration

An example service file is provided at `systemd/aircraft-detector.service`.
It runs the detector on boot and depends on `readsb.service`.
Copy it to `/etc/systemd/system/` and enable:

```bash
sudo cp systemd/aircraft-detector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aircraft-detector
sudo systemctl start aircraft-detector
```

## Testing ADS-B Integration

1. Verify RTL-SDR detection:
   ```bash
   rtl_test
   ```
2. Check readsb service:
   ```bash
   sudo systemctl status readsb
   ```
3. Test ADS-B data reception:
   ```bash
   curl http://localhost:8080/data/aircraft.json
   ```
   You should see JSON data with nearby aircraft if any are transmitting ADS-B signals.

4. Verify integration in aircraft detector logs:
   ```bash
   python3 pi-aircraft-detector.py --enable-adsb --camera-lat YOUR_LAT --camera-lon YOUR_LON
   ```
   Look for log messages about ADS-B correlation with visual detections.
