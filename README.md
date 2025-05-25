# Aircraft Detector

Pi-based system for tracking aircraft using a Raspberry Pi camera module and OpenCV. The project captures frames, detects motion in the sky, and logs confirmed aircraft sightings in a SQLite database. An optional Flask web interface lets you view detections and stream video remotely.

## Features

- Real-time camera feed
- Sky segmentation and motion detection to isolate potential aircraft
- Object tracking across frames with speed and direction estimation
- SQLite database for storing detections and tracking data
- Optional web dashboard for video streaming and system control
- Command line options to adjust detection parameters

## Hardware Requirements

Refer to [INSTALLATION.md](INSTALLATION.md) for a detailed setup guide. In short you will need:

1. Raspberry Pi 5 (8&nbsp;GB recommended)
2. Raspberry Pi camera module (rev&nbsp;1.3 or newer)
3. MicroSD card (32&nbsp;GB or larger) and the official 27W USB‑C power supply

## Quick Start

1. **Verify Hardware Setup**: Follow [INSTALLATION.md](INSTALLATION.md) for camera configuration
2. **Run Aircraft Detector**:
   ```bash
   python3 pi-aircraft-detector.py --web --save-detections
   ```

3. **Access Web Interface**: Open `http://<pi-address>:8080`

### Troubleshooting

If you encounter issues, check console output for specific error messages and verify the camera cable connections.

If frames fail to capture even though the camera is detected ("Failed to capture frame" messages), ensure that the V4L2 compatibility driver is loaded and that the camera supports MJPEG output.  The built in `RPiCamera` class now sets the ``MJPG`` format automatically, but older installs may require enabling the legacy camera driver with ``modprobe bcm2835-v4l2``.

For detailed troubleshooting, see [INSTALLATION.md](INSTALLATION.md).

### Command Summary for Users

After cloning the repository, run:

```bash
# Run aircraft detector
python3 pi-aircraft-detector.py --web
```

## Project Structure

- `pi-aircraft-detector.py` – main entry point
- `rpi_camera.py` – camera integration layer
- `database.py` – SQLite logging utilities
- `web_interface.py` – optional Flask server
- `templates/` – HTML template for the web dashboard
- `detections/` – saved detection images (if enabled)

## More Information

For installation instructions, troubleshooting tips and advanced features see [INSTALLATION.md](INSTALLATION.md) and [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md).

## License

This project is open source and available under the MIT License.
