# Aircraft Detector

Pi-based system for tracking aircraft using a 64MP ArduCam and OpenCV. The project captures high-resolution frames, detects motion in the sky, and logs confirmed aircraft sightings in a SQLite database. An optional Flask web interface lets you view detections and stream video remotely.

## Features

- Real-time camera feed with autofocus support
- Sky segmentation and motion detection to isolate potential aircraft
- Object tracking across frames with speed and direction estimation
- SQLite database for storing detections and tracking data
- Optional web dashboard for video streaming and system control
- Command line options to adjust detection parameters

## Hardware Requirements

Refer to [INSTALLATION.md](INSTALLATION.md) for a detailed setup guide. In short you will need:

1. Raspberry Pi 5 (8&nbsp;GB recommended)
2. 64MP ArduCam Hawkeye with autofocus
3. MicroSD card (32&nbsp;GB or larger) and the official 27W USB‑C power supply

## Quick Start

1. **Verify Hardware Setup**: Follow [INSTALLATION.md](INSTALLATION.md) for Pi 5 + ArduCam configuration

2. **Test Camera**: Verify your setup before running the detector
   ```bash
   python3 test_camera.py --quick
   ```

   Fix Configuration (if needed):
   ```bash
   sudo python3 validate_config.py --fix --backup
   sudo reboot
   ```

3. **Run Aircraft Detector**:
   ```bash
   python3 pi-aircraft-detector.py --web --save-detections
   ```

4. **Access Web Interface**: Open `http://<pi-address>:8080`

### Troubleshooting

If you encounter issues:

- Run diagnostics: `python3 test_camera.py`
- Check configuration: `python3 validate_config.py`
- View logs: Check console output for specific error messages
- Hardware check: Verify camera cable and connections

For detailed troubleshooting, see [INSTALLATION.md](INSTALLATION.md).

### Command Summary for Users

After cloning the repository, run:

```bash
# 1. Test camera setup
python3 test_camera.py

# 2. Fix any configuration issues
sudo python3 validate_config.py --fix --backup
sudo reboot

# 3. Test again after reboot
python3 test_camera.py --quick

# 4. Run aircraft detector
python3 pi-aircraft-detector.py --web
```

## Project Structure

- `pi-aircraft-detector.py` – main entry point
- `arducam_camera.py` – camera integration layer
- `database.py` – SQLite logging utilities
- `web_interface.py` – optional Flask server
- `templates/` – HTML template for the web dashboard
- `detections/` – saved detection images (if enabled)

## More Information

For installation instructions, troubleshooting tips and advanced features see [INSTALLATION.md](INSTALLATION.md) and [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md).

## License

This project is open source and available under the MIT License.
