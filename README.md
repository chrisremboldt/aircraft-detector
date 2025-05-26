# Aircraft Detector

Pi-based system for tracking aircraft using a Raspberry Pi camera module. Frames
are captured via the libcamera stack (Picamera2) and processed with OpenCV. The
project detects motion and contrast anywhere in the frame and logs confirmed aircraft sightings in a
SQLite database. An optional Flask web interface lets you view detections and
stream video remotely.

## Features

- Real-time camera feed
- Motion and contrast detection to isolate potential aircraft
- Object tracking across frames with speed and direction estimation
- ADS-B correlation with visual detections (requires RTL-SDR dongle)
- SQLite database for storing detections and tracking data
- Optional web dashboard for video streaming and system control
- Command line options to adjust detection parameters

## Hardware Requirements

Refer to [INSTALLATION.md](INSTALLATION.md) for a detailed setup guide. In short you will need:

1. Raspberry Pi 5 (8&nbsp;GB recommended)
2. Raspberry Pi camera module (rev&nbsp;1.3 or newer)
3. MicroSD card (32&nbsp;GB or larger) and the official 27W USB‑C power supply
4. RTL-SDR dongle (RTL-SDR Blog V4 recommended) - for ADS-B integration
5. 1090MHz ADS-B antenna (optional, improves reception range)

## Quick Start

### Automated Setup (Recommended)

For a complete installation from GitHub:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/aircraft-detector.git
cd aircraft-detector

# Run automated setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:
- Install all system and Python dependencies
- Configure RTL-SDR permissions
- Set up dump1090-mutability with your coordinates
- Optionally build dump1090-fa from source
- Install systemd services
- Create the aircraft-detector user

### Manual Setup

1. **Verify Hardware Setup**: Follow [INSTALLATION.md](INSTALLATION.md) for camera configuration
2. **Install Dependencies**:
   ```bash
   sudo apt install -y python3-opencv python3-flask python3-numpy python3-picamera2
   pip3 install -r requirements.txt
   ```
3. **Run Aircraft Detector**:
   ```bash
   # Camera-only detection
   python3 pi-aircraft-detector.py --web --web-port 8081 --save-detections
   
   # With ADS-B integration (requires setup from INSTALLATION.md)
   python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON --save-detections
   ```

4. **Access Web Interface**: Open `http://<pi-address>:8081`

### Troubleshooting

If you encounter issues, check console output for specific error messages and verify the camera cable connections.

If frames fail to capture, verify that the `python3-picamera2` package is installed
and that the camera is enabled in `raspi-config`. The detector uses Picamera2 by
default and falls back to OpenCV only when the `--use-opencv` flag is supplied.

For detailed troubleshooting, see [INSTALLATION.md](INSTALLATION.md).

## Quick Reference Commands

### SSH Connection & Remote Execution

```bash
# Connect to Raspberry Pi
ssh aircraft-detector@192.168.1.243

# Run aircraft detector remotely with ADS-B (Nashville coordinates)
ssh aircraft-detector@192.168.1.243 "cd /home/aircraft-detector && python3 pi-aircraft-detector.py --web --enable-adsb --adsb-json-dir /run/dump1090-mutability --camera-lat 36.02316650611701 --camera-lon -86.70226195080218 --save-detections --port 8081"

# Run with dump1090-fa decoder
ssh aircraft-detector@192.168.1.243 "cd /home/aircraft-detector && python3 pi-aircraft-detector.py --web --enable-adsb --adsb-json-dir /run/dump1090-fa --camera-lat 36.02316650611701 --camera-lon -86.70226195080218 --save-detections --port 8081"

# Copy files to/from Pi
scp file.txt aircraft-detector@192.168.1.243:/home/aircraft-detector/
scp aircraft-detector@192.168.1.243:/home/aircraft-detector/file.txt ./
```

### Running Aircraft Detector

```bash
# Basic camera-only detection
python3 pi-aircraft-detector.py --web --web-port 8081 --save-detections

# Full ADS-B integration (dump1090-mutability)
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-mutability --camera-lat 36.02316650611701 --camera-lon -86.70226195080218 --save-detections

# Full ADS-B integration (dump1090-fa)
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-fa --camera-lat 36.02316650611701 --camera-lon -86.70226195080218 --save-detections

# Run in background (detached)
nohup python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-mutability --camera-lat 36.02316650611701 --camera-lon -86.70226195080218 --save-detections > detector.log 2>&1 &
```

### ADS-B Decoder Management

```bash
# Check decoder status
./scripts/switch-adsb-decoder.sh status
systemctl is-active dump1090-mutability dump1090-fa

# Switch to dump1090-fa
./scripts/switch-adsb-decoder.sh fa

# Switch to dump1090-mutability
./scripts/switch-adsb-decoder.sh mutability

# Manual service control
sudo systemctl start dump1090-mutability
sudo systemctl stop dump1090-mutability
sudo systemctl restart dump1090-mutability
sudo systemctl enable dump1090-mutability
sudo systemctl disable dump1090-mutability

# Same commands for dump1090-fa
sudo systemctl start dump1090-fa
sudo systemctl stop dump1090-fa
sudo systemctl restart dump1090-fa
```

### System Status & Monitoring

```bash
# Check all services
sudo systemctl status dump1090-mutability
sudo systemctl status dump1090-fa
sudo systemctl status aircraft-detector

# Check service logs
sudo journalctl -u dump1090-mutability -f
sudo journalctl -u dump1090-fa -f
sudo journalctl -u aircraft-detector -f

# Monitor system resources
htop
top
free -h
df -h

# Check RTL-SDR device
lsusb | grep -i rtl
rtl_test -t

# Monitor network ports
netstat -tlnp | grep ':3000'
netstat -tlnp | grep ':8080'
netstat -tlnp | grep ':8081'
```

### Data Verification

```bash
# Check ADS-B JSON data
ls -la /run/dump1090-mutability/
cat /run/dump1090-mutability/aircraft.json
ls -la /run/dump1090-fa/
cat /run/dump1090-fa/aircraft.json

# Check detection images
ls -la detections/
ls -la detections/ | tail -10

# Database queries
sqlite3 aircraft_detections.db "SELECT COUNT(*) FROM detections;"
sqlite3 aircraft_detections.db "SELECT * FROM detections ORDER BY timestamp DESC LIMIT 10;"

# Check disk usage
du -sh detections/
du -sh aircraft_detections.db
```

### Web Interface Access

```bash
# Direct URLs (replace with your Pi's IP)
http://192.168.1.243:8081          # Aircraft detector web interface
http://192.168.1.243:8080          # dump1090-mutability map interface
http://192.168.1.243:8080/data/aircraft.json  # ADS-B JSON data

# Using hostname (if mDNS configured)
http://aircraft-detector.local:8081
http://aircraft-detector.local:8080

# Test web endpoints
curl http://192.168.1.243:8081
curl http://192.168.1.243:8080/data/aircraft.json
```

### Troubleshooting Commands

```bash
# Check camera
libcamera-hello --timeout 5000
vcgencmd get_camera

# Check RTL-SDR permissions
groups $USER
groups dump1090
ls -la /dev/bus/usb/*/*

# Check configuration files
cat /etc/default/dump1090-mutability
cat /etc/systemd/system/dump1090-fa.service
cat /etc/systemd/system/aircraft-detector.service

# System information
uname -a
cat /etc/os-release
vcgencmd measure_temp
vcgencmd get_throttled

# Process monitoring
ps aux | grep dump1090
ps aux | grep python3
pgrep -f aircraft-detector
```

### Maintenance Commands

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Restart all services
sudo systemctl restart dump1090-mutability aircraft-detector

# Clean up old detection images (older than 30 days)
find detections/ -name "*.jpg" -mtime +30 -delete

# Backup database
cp aircraft_detections.db aircraft_detections_backup_$(date +%Y%m%d).db

# Check for system errors
sudo dmesg | tail -20
sudo journalctl -p err --since today
```

### Quick Coordinates Reference

```bash
# Nashville area coordinates (update for your location)
--camera-lat 36.02316650611701 --camera-lon -86.70226195080218

# Example for other locations:
# New York: --camera-lat 40.7128 --camera-lon -74.0060
# Los Angeles: --camera-lat 34.0522 --camera-lon -118.2437
# Chicago: --camera-lat 41.8781 --camera-lon -87.6298
```

### Command Summary for Users

After cloning the repository and following [INSTALLATION.md](INSTALLATION.md), run:

```bash
# Run aircraft detector (camera only)
python3 pi-aircraft-detector.py --web --web-port 8081

# Run with ADS-B integration
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON
```

## Running the System with ADS-B Integration

After completing the ADS-B setup from [INSTALLATION.md](INSTALLATION.md):

```bash
cd ~/aircraft-detector
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON
```

Important command-line options for ADS-B:
- `--enable-adsb`: Enable ADS-B correlation features
- `--adsb-url http://localhost:8080/data/aircraft.json`: URL for ADS-B data
- `--camera-lat` and `--camera-lon`: Camera coordinates for distance filtering
- `--web-port 8081`: Use port 8081 (port 8080 is used by dump1090-mutability)

### ADS-B Decoder Options

This system supports two ADS-B decoders that you can switch between:

#### Option 1: dump1090-mutability (Default)
- **Pros**: Package-managed, proven stable, includes web interface
- **JSON Data**: `/run/dump1090-mutability/aircraft.json`
- **Command**: `--adsb-json-dir /run/dump1090-mutability`

#### Option 2: dump1090-fa (FlightAware)
- **Pros**: Latest optimizations, better performance, ARM64 SIMD support  
- **JSON Data**: `/run/dump1090-fa/aircraft.json`
- **Command**: `--adsb-json-dir /run/dump1090-fa`

#### Switching Between Decoders

**To switch to dump1090-fa:**
```bash
sudo systemctl stop dump1090-mutability
sudo systemctl disable dump1090-mutability
sudo systemctl start dump1090-fa
sudo systemctl enable dump1090-fa

# Update aircraft detector command
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-fa --camera-lat YOUR_LAT --camera-lon YOUR_LON
```

**To switch back to dump1090-mutability:**
```bash
sudo systemctl stop dump1090-fa
sudo systemctl disable dump1090-fa
sudo systemctl start dump1090-mutability
sudo systemctl enable dump1090-mutability

# Update aircraft detector command  
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-json-dir /run/dump1090-mutability --camera-lat YOUR_LAT --camera-lon YOUR_LON
```

For detailed information about each decoder, see [INSTALLATION.md](INSTALLATION.md) and [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md).

#### Quick Switching Script

For convenience, use the included switching script:

```bash
# Check current decoder status
./switch-adsb-decoder.sh status

# Switch to dump1090-fa
./switch-adsb-decoder.sh fa

# Switch to dump1090-mutability  
./switch-adsb-decoder.sh mutability

# Show help
./switch-adsb-decoder.sh --help
```

The script automatically handles stopping/starting services and provides the correct command syntax for the aircraft detector.

## Project Structure

- `pi-aircraft-detector.py` – main entry point
- `rpi_camera.py` – camera integration layer
- `database.py` – SQLite logging utilities
- `web_interface.py` – optional Flask server
- `templates/` – HTML template for the web dashboard
- `detections/` – saved detection images (if enabled)

## Access Interfaces

After installation, you can access:
- **Aircraft Detection System**: `http://aircraft-detector.local:8081`
- **ADS-B Map Interface**: `http://aircraft-detector.local:8080` (if ADS-B configured)
- **ADS-B JSON API**: Files in `/run/dump1090-mutability/` or via `http://aircraft-detector.local:8080/data/aircraft.json`

## More Information

For installation instructions, troubleshooting tips and advanced features see [INSTALLATION.md](INSTALLATION.md) and [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md).

## License

This project is open source and available under the MIT License.
