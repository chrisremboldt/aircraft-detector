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

1. Raspberry Pi 4 (8&nbsp;GB recommended)
2. 64MP ArduCam Hawkeye with autofocus
3. MicroSD card and stable power supply

## Quick Start

1. Clone this repository on your Raspberry Pi and install the dependencies listed in [INSTALLATION.md](INSTALLATION.md).
2. Run the detector with video display and the web interface enabled:

```bash
python3 pi-aircraft-detector.py --display --web
```

3. Open a browser to `http://<pi-address>:8080` to view the dashboard.

Use `--help` to see all available options.

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
