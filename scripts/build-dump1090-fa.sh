#!/bin/bash

# Build dump1090-fa from source
# This script compiles FlightAware's dump1090 with all SDR support

set -e

echo "🔧 Building dump1090-fa from source..."

# Install build dependencies
echo "📦 Installing build dependencies..."
sudo apt update
sudo apt install -y \
    build-essential \
    autoconf \
    automake \
    libtool \
    pkg-config \
    librtlsdr-dev \
    libusb-1.0-0-dev \
    libbladerf-dev \
    libsoapysdr-dev \
    soapysdr-tools \
    git

# Create build directory
BUILD_DIR="/tmp/dump1090-fa-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Clone FlightAware's dump1090 repository
echo "📡 Cloning FlightAware dump1090 repository..."
git clone https://github.com/flightaware/dump1090.git
cd dump1090

# Build with all SDR support
echo "🏗️ Compiling dump1090-fa..."
make clean
make RTLSDR=yes BLADERF=yes SOAPYSDR=yes

# Install binary
echo "📋 Installing dump1090-fa binary..."
sudo cp dump1090 /usr/local/bin/dump1090-fa
sudo chmod +x /usr/local/bin/dump1090-fa

# Verify installation
echo "✅ Verifying installation..."
/usr/local/bin/dump1090-fa --help | head -5

echo "🎉 dump1090-fa built and installed successfully!"
echo "📍 Binary location: /usr/local/bin/dump1090-fa"
echo ""
echo "Next steps:"
echo "1. Copy systemd service: sudo cp systemd/dump1090-fa.service /etc/systemd/system/"
echo "2. Reload systemd: sudo systemctl daemon-reload"
echo "3. Enable service: sudo systemctl enable dump1090-fa" 