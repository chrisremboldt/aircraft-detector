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

### Install dump1090-mutability (ADS-B Decoder)

Install dump1090-mutability, which has proven RTL-SDR support:

```bash
sudo apt install -y dump1090-mutability
```

### Alternative: dump1090-fa (FlightAware Version)

**Note:** This system also includes dump1090-fa (FlightAware version) compiled from source as an alternative to dump1090-mutability. Both provide similar functionality but may have different performance characteristics.

The dump1090-fa binary is already installed at `/usr/local/bin/dump1090-fa` and has a systemd service configured.

### Choosing Between ADS-B Decoders

You can switch between the two ADS-B decoders depending on your needs:

#### Option 1: dump1090-mutability (Default)
- **Pros**: Package-managed, proven stable, includes web interface
- **Cons**: Older codebase, potentially less optimized
- **Data Location**: `/run/dump1090-mutability/aircraft.json`

#### Option 2: dump1090-fa (FlightAware)
- **Pros**: Latest FlightAware optimizations, potentially better performance
- **Cons**: Compiled from source, requires manual updates
- **Data Location**: `/run/dump1090-fa/aircraft.json`

### Switching Between ADS-B Decoders

To switch from dump1090-mutability to dump1090-fa:

```bash
# Stop current service
sudo systemctl stop dump1090-mutability
sudo systemctl disable dump1090-mutability

# Start dump1090-fa
sudo systemctl enable dump1090-fa
sudo systemctl start dump1090-fa
```

To switch back to dump1090-mutability:

```bash
# Stop dump1090-fa
sudo systemctl stop dump1090-fa
sudo systemctl disable dump1090-fa

# Start dump1090-mutability
sudo systemctl enable dump1090-mutability
sudo systemctl start dump1090-mutability
```

**Important:** When switching between decoders, you'll also need to update the aircraft detector's ADS-B URL:
- **dump1090-mutability**: `--adsb-json-dir /run/dump1090-mutability`
- **dump1090-fa**: `--adsb-json-dir /run/dump1090-fa`

#### Quick Switching Script

For convenience, a switching script is included:

```bash
# Copy the script to your Pi (done during setup)
./switch-adsb-decoder.sh status      # Check current decoder
./switch-adsb-decoder.sh fa          # Switch to dump1090-fa  
./switch-adsb-decoder.sh mutability  # Switch to dump1090-mutability
```

The script automatically handles service management and provides the correct command syntax.

### Configure dump1090-mutability Service

Create the dump1090 user (if it doesn't exist):
```bash
sudo useradd --system --no-create-home --shell /bin/false dump1090
```

Configure RTL-SDR permissions:
```bash
# Add dump1090 user to plugdev group
sudo usermod -a -G plugdev dump1090

# Also add your user to plugdev group
sudo usermod -a -G plugdev $USER

# Create udev rules for RTL-SDR access
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0664"' | sudo tee /etc/udev/rules.d/20-rtlsdr.rules

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Configure dump1090-mutability:
```bash
sudo nano /etc/default/dump1090-mutability
```

Update the configuration file with your coordinates (replace with your actual latitude/longitude):
```bash
START_DUMP1090="yes"
DUMP1090_USER="dump1090"
LOGFILE="/var/log/dump1090-mutability.log"

DEVICE="0"
GAIN="-10"
PPM="0"

FIX_CRC="yes"
LAT="36.0"
LON="-86.7"
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
```

**Important:** Replace the LAT and LON values with your actual coordinates. For example:
- Nashville, TN: `LAT="36.0"` and `LON="-86.7"`

Enable and start dump1090-mutability service:
```bash
sudo systemctl enable dump1090-mutability
sudo systemctl start dump1090-mutability
```

**Note:** You may need to reboot after RTL-SDR permission changes:
```bash
sudo reboot
```

5. Enable the camera interface using `raspi-config` if it is not already enabled.
6. Verify the camera works with `libcamera-hello` before running the detector.


## Running the Detector

Clone this repository and run:

```bash
# Basic operation (camera only)
python3 pi-aircraft-detector.py --web --web-port 8081

# With ADS-B integration (replace with your coordinates)
python3 pi-aircraft-detector.py --web --web-port 8081 --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat 36.0 --camera-lon -86.7
```

**Note:** We use port 8081 for the aircraft detector because dump1090-mutability uses port 8080 for its web interface.

Open `http://<pi-address>:8081` in your browser to view the aircraft detection interface.
Open `http://<pi-address>:8080` in your browser to view the ADS-B map interface.

## systemd Service Configuration

An example service file is provided at `systemd/aircraft-detector.service`.
It runs the detector on boot and depends on `dump1090-mutability.service`.

**Important:** Before copying the service file, edit it to update the coordinates to match your location:
```bash
nano systemd/aircraft-detector.service
```
Replace `--camera-lat 36.0 --camera-lon -86.7` with your actual coordinates.

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

2. Check dump1090-mutability service:
   ```bash
   sudo systemctl status dump1090-mutability
   ```

3. Verify JSON data is being generated:
   ```bash
   ls -la /run/dump1090-mutability/
   cat /run/dump1090-mutability/aircraft.json
   ```

4. Check network ports are listening:
   ```bash
   netstat -tlnp | grep ':3000'
   ```
   You should see ports 30001-30005 listening.

5. Test ADS-B integration in aircraft detector:
   ```bash
   python3 pi-aircraft-detector.py --enable-adsb --adsb-url http://localhost:8080/data/aircraft.json --camera-lat YOUR_LAT --camera-lon YOUR_LON
   ```
   Look for log messages about ADS-B data being read and correlated with visual detections.

## Access Points

After successful installation:
- **Aircraft Detection System**: `http://<pi-address>:8081`
- **ADS-B Map Interface**: `http://<pi-address>:8080` 
- **ADS-B JSON Data**: `http://<pi-address>:8080/data/aircraft.json` (via dump1090 web server)
- **Direct JSON Files**: `/run/dump1090-mutability/aircraft.json` (filesystem access)

## Troubleshooting ADS-B

- **RTL-SDR permission errors**: Ensure udev rules are created and reboot after adding users to plugdev group
- **No aircraft showing**: This is normal if no aircraft are in range transmitting ADS-B
- **Service won't start**: Check logs with `sudo journalctl -u dump1090-mutability -f`
- **Port conflicts**: Make sure aircraft detector uses port 8081, not 8080
