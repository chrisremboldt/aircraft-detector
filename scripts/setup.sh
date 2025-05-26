#!/bin/bash

# Aircraft Detection System - Complete Setup Script
# Automates installation from GitHub repository

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "🚁 Aircraft Detection System Setup"
echo "=================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This setup is designed for Raspberry Pi"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
sudo apt install -y python3-pip python3-opencv python3-flask python3-numpy python3-picamera2
pip3 install -r requirements.txt

# Install RTL-SDR tools
echo "📡 Installing RTL-SDR tools..."
sudo apt install -y rtl-sdr librtlsdr-dev

# Install dump1090-mutability
echo "🛩️ Installing dump1090-mutability..."
sudo apt install -y dump1090-mutability

# Create aircraft-detector user if it doesn't exist
if ! id "aircraft-detector" &>/dev/null; then
    echo "👤 Creating aircraft-detector user..."
    sudo useradd --system --create-home --shell /bin/bash aircraft-detector
    sudo usermod -a -G plugdev aircraft-detector
fi

# Set up RTL-SDR permissions
echo "🔐 Setting up RTL-SDR permissions..."
sudo usermod -a -G plugdev $USER
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0664"' | sudo tee /etc/udev/rules.d/20-rtlsdr.rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Build dump1090-fa (optional)
read -p "🔨 Build dump1090-fa from source? (Y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    ./scripts/build-dump1090-fa.sh
fi

# Install systemd services
echo "⚙️ Installing systemd services..."
sudo cp systemd/aircraft-detector.service /etc/systemd/system/
sudo cp systemd/dump1090-fa.service /etc/systemd/system/
sudo systemctl daemon-reload

# Configure dump1090-mutability
echo "📝 Configuring dump1090-mutability..."
read -p "Enter your latitude (e.g., 36.0): " LATITUDE
read -p "Enter your longitude (e.g., -86.7): " LONGITUDE

sudo tee /etc/default/dump1090-mutability > /dev/null <<EOF
START_DUMP1090="yes"
DUMP1090_USER="dump1090"
LOGFILE="/var/log/dump1090-mutability.log"

DEVICE="0"
GAIN="-10"
PPM="0"

FIX_CRC="yes"
LAT="$LATITUDE"
LON="$LONGITUDE"
MAX_RANGE="300"

RAW_INPUT_PORT="30001"
RAW_OUTPUT_PORT="30002"
SBS_OUTPUT_PORT="30003"
BEAST_INPUT_PORT="30004,30104"
BEAST_OUTPUT_PORT="30005"
NET_HEARTBEAT="60"
NET_OUTPUT_SIZE="500"
NET_OUTPUT_INTERVAL="1"
NET_BUFFER="262144"
NET_BIND_ADDRESS="0.0.0.0"

STATS_INTERVAL="3600"
JSON_DIR="/run/dump1090-mutability"
JSON_INTERVAL="1"
JSON_LOCATION_ACCURACY="approximate"
LOG_DECODED_MESSAGES="no"

EXTRA_ARGS=""
EOF

# Create project directory and set permissions
echo "📁 Setting up project directory..."
sudo mkdir -p /home/aircraft-detector/aircraft-detector
sudo cp -r * /home/aircraft-detector/aircraft-detector/
sudo chown -R aircraft-detector:aircraft-detector /home/aircraft-detector/aircraft-detector
sudo chmod +x /home/aircraft-detector/aircraft-detector/scripts/*.sh

# Enable services
echo "🔄 Enabling services..."
sudo systemctl enable dump1090-mutability
sudo systemctl start dump1090-mutability

# Wait for dump1090 to start
echo "⏳ Waiting for dump1090-mutability to start..."
sleep 5

# Test RTL-SDR
echo "🧪 Testing RTL-SDR device..."
timeout 5 rtl_test -t || echo "⚠️  RTL-SDR test failed - check device connection"

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "📍 Your coordinates: $LATITUDE, $LONGITUDE"
echo "📂 Project location: /home/aircraft-detector/aircraft-detector"
echo ""
echo "🚀 Start the aircraft detector:"
echo "cd /home/aircraft-detector/aircraft-detector"
echo "python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat $LATITUDE --camera-lon $LONGITUDE --save-detections"
echo ""
echo "🌐 Access interfaces:"
echo "• Aircraft Detector: http://$(hostname -I | awk '{print $1}'):8081"
echo "• ADS-B Map: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "📋 Next steps:"
echo "1. Reboot to ensure all permissions take effect: sudo reboot"
echo "2. Test camera: libcamera-hello --timeout 5000"
echo "3. Check services: sudo systemctl status dump1090-mutability"
echo "4. Run aircraft detector with the command above" 