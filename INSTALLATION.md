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
```bash
sudo apt install -y rtl-sdr librtlsdr-dev

rtl_test

sudo apt install -y readsb

sudo nano /etc/default/readsb
```
Add this configuration to the file:
```bash
RECEIVER_OPTIONS="--device-index 0 --gain -10 --ppm 0"
DECODER_OPTIONS="--max-range 300"
NET_OPTIONS="--net --net-heartbeat 60 --net-ro-size 1280 --net-ro-interval 0.2 --net-http-port 8080 --net-bind-address 127.0.0.1"
JSON_OPTIONS="--write-json /var/cache/readsb"
```
Enable and start readsb service
```bash
sudo systemctl enable readsb
sudo systemctl start readsb
```
5. Enable the camera interface using `raspi-config` if it is not already enabled.
6. Verify the camera works with `libcamera-hello` before running the detector.


## Running the Detector

Clone this repository and run:

```bash
python3 pi-aircraft-detector.py --web
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
4. Verify integration in aircraft detector logs
