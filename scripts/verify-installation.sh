#!/bin/bash

# Aircraft Detection System - Installation Verification
# Checks if all components are properly installed and configured

echo "🔍 Aircraft Detection System - Installation Verification"
echo "========================================================"
echo ""

ERRORS=0

# Check if running on Raspberry Pi
echo "🖥️  System Check:"
if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "   ✅ Running on Raspberry Pi"
    PI_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
    echo "   📋 Model: $PI_MODEL"
else
    echo "   ⚠️  Not running on Raspberry Pi"
fi
echo ""

# Check Python dependencies
echo "🐍 Python Dependencies:"
PYTHON_DEPS=("opencv-python" "numpy" "flask" "picamera2" "requests")
for dep in "${PYTHON_DEPS[@]}"; do
    if python3 -c "import ${dep//opencv-python/cv2}" 2>/dev/null; then
        echo "   ✅ $dep"
    else
        echo "   ❌ $dep - MISSING"
        ((ERRORS++))
    fi
done
echo ""

# Check camera
echo "📷 Camera Check:"
if libcamera-hello --list-cameras 2>/dev/null | grep -q "Available cameras"; then
    echo "   ✅ Camera detected"
    CAMERA_COUNT=$(libcamera-hello --list-cameras 2>/dev/null | grep -c "^\[")
    echo "   📋 Found $CAMERA_COUNT camera(s)"
else
    echo "   ❌ Camera not detected or not enabled"
    ((ERRORS++))
fi
echo ""

# Check RTL-SDR
echo "📡 RTL-SDR Check:"
if lsusb | grep -q "RTL"; then
    echo "   ✅ RTL-SDR device detected"
    RTL_DEVICE=$(lsusb | grep RTL)
    echo "   📋 Device: $RTL_DEVICE"
    
    # Test RTL-SDR functionality
    if timeout 3 rtl_test -t 2>/dev/null | grep -q "No errors"; then
        echo "   ✅ RTL-SDR device working"
    else
        echo "   ⚠️  RTL-SDR device may have issues"
    fi
else
    echo "   ❌ RTL-SDR device not detected"
    ((ERRORS++))
fi
echo ""

# Check services
echo "⚙️  Service Status:"
SERVICES=("dump1090-mutability" "dump1090-fa")
for service in "${SERVICES[@]}"; do
    if systemctl is-installed "$service" &>/dev/null; then
        if systemctl is-active --quiet "$service"; then
            echo "   ✅ $service - ACTIVE"
        else
            echo "   ⭕ $service - installed but inactive"
        fi
    else
        echo "   ❌ $service - not installed"
        if [[ "$service" == "dump1090-mutability" ]]; then
            ((ERRORS++))
        fi
    fi
done
echo ""

# Check data directories
echo "📁 Data Directories:"
DATA_DIRS=("/run/dump1090-mutability" "/run/dump1090-fa")
for dir in "${DATA_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "   ✅ $dir exists"
        if [[ -f "$dir/aircraft.json" ]]; then
            echo "   ✅ $dir/aircraft.json present"
        else
            echo "   ⚠️  $dir/aircraft.json not found (service may not be running)"
        fi
    else
        echo "   ⭕ $dir does not exist (service not running)"
    fi
done
echo ""

# Check network ports
echo "🌐 Network Ports:"
PORTS=("8080" "8081" "30001" "30002" "30003")
for port in "${PORTS[@]}"; do
    if netstat -tln 2>/dev/null | grep -q ":$port "; then
        echo "   ✅ Port $port is listening"
    else
        echo "   ⭕ Port $port not listening"
    fi
done
echo ""

# Check project files
echo "📋 Project Files:"
PROJECT_FILES=("pi-aircraft-detector.py" "web_interface.py" "database.py" "rpi_camera.py" "requirements.txt")
for file in "${PROJECT_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file - MISSING"
        ((ERRORS++))
    fi
done
echo ""

# Summary
echo "📊 Verification Summary:"
echo "======================="
if [[ $ERRORS -eq 0 ]]; then
    echo "🎉 All critical components verified successfully!"
    echo ""
    echo "🚀 Ready to run aircraft detector:"
    echo "python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-mutability --camera-lat YOUR_LAT --camera-lon YOUR_LON --save-detections"
else
    echo "❌ Found $ERRORS critical issues that need to be resolved"
    echo ""
    echo "📝 Common solutions:"
    echo "• Install missing dependencies: pip3 install -r requirements.txt"
    echo "• Enable camera: sudo raspi-config -> Interface Options -> Camera"
    echo "• Install dump1090-mutability: sudo apt install dump1090-mutability"
    echo "• Check RTL-SDR connection and permissions"
fi 