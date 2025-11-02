# Pose Touch Detector Management Command

## Overview

The `pose_touch_detector` management command is a comprehensive system that captures camera streams, recognizes human posture, and determines which objects in an SVG file are being touched by hands in the pose. The touched object IDs are then streamed to a WebSocket channel for real-time visualization and analysis.

## Features

- **Real-time pose detection** using MediaPipe
- **SVG object touch detection** with coordinate transformation
- **ArUco marker-based calibration** for accurate coordinate mapping
- **WebSocket streaming** to existing session channels
- **Fake pose streamer support** for testing without a camera
- **Configurable touch detection thresholds**
- **Comprehensive logging and debugging capabilities**

## Prerequisites

1. **Django project setup** with the climber app
2. **MediaPipe installed** for pose detection
3. **OpenCV installed** for camera handling
4. **Wall with SVG file** configured in the database
5. **Wall calibration** created and associated with the wall
6. **Active session** for WebSocket streaming

## Installation

1. Install required dependencies:
```bash
uv add mediapipe opencv-python loguru
```

2. Ensure the database is migrated:
```bash
uv run python manage.py migrate
```

3. Create a wall with an SVG file and calibration:
   - Use the web interface to create a wall
   - Upload an SVG file with climbing holds
   - Create a calibration using the calibration management interface

## Usage

### Basic Usage

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id <session-uuid>
```

### With Fake Pose Streamer (for testing)

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id <session-uuid> --fake-pose
```

### With Custom Camera Source

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id <session-uuid> --camera-source "http://192.168.1.100:8080/video"
```

### With Debug Output

```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id <session-uuid> --debug
```

## Command Options

- `--wall-id`: (Required) ID of the wall to process
- `--session-id`: (Optional) ID of the session for WebSocket streaming
- `--camera-source`: (Optional) Camera source (default: 0 for default camera, or URL for IP camera)
- `--fake-pose`: (Optional) Use fake pose streamer for testing
- `--touch-threshold`: (Optional) Threshold for determining touch (default: 0.1)
- `--debug`: (Optional) Enable debug output

## How It Works

### 1. Initialization

The command initializes the following components:
- MediaPipe pose and hand detection models
- Wall and calibration data from the database
- SVG parser for extracting object boundaries
- Camera or fake pose streamer
- WebSocket channel layer for streaming

### 2. Pose Detection

For real camera input:
- Captures frames from the camera
- Processes frames with MediaPipe to detect pose landmarks
- Extracts hand and finger positions
- Calculates average hand positions for touch detection

For fake pose input:
- Uses the FakePoseStreamer class to generate realistic climbing poses
- Provides hand positions directly without camera processing

### 3. Coordinate Transformation

The system transforms coordinates between different spaces:
1. **Image coordinates** (pixels) from camera frames
2. **Camera coordinates** using calibration matrix
3. **SVG coordinates** using perspective transformation
4. **Object detection** in SVG space

### 4. Touch Detection

Touch detection works by:
1. Averaging hand and finger landmark positions
2. Transforming positions to SVG coordinate space
3. Checking if positions are inside SVG path objects
4. Collecting IDs of touched objects

### 5. WebSocket Streaming

Touched object IDs are streamed to WebSocket channels:
- Messages include timestamp, wall ID, and touched object IDs
- Only sends updates when touched objects change
- Integrates with existing session WebSocket channels

## Calibration System

The system relies on the calibration system for accurate coordinate mapping:

### Creating a Calibration

1. Navigate to the wall detail page
2. Click "Manage Calibrations"
3. Click "Create New Calibration"
4. Upload an image with ArUco markers
5. Review detected markers and transformation
6. Save the calibration

### Calibration Data

The calibration stores:
- Camera matrix (intrinsics)
- Distortion coefficients
- Perspective transformation matrix
- ArUco marker mappings

## Testing

### Using the Test Script

A test script is provided to verify the system:

```bash
uv run python test_pose_touch_detector.py
```

This script:
- Creates test data (wall, calibration, session)
- Runs the pose touch detector with fake pose streamer
- Displays real-time output

### Manual Testing

1. Create a wall with SVG file
2. Create a calibration for the wall
3. Create an active session
4. Run the command with `--fake-pose` flag
5. Connect to the WebSocket channel to receive touch updates

## WebSocket Message Format

The system sends messages in the following format:

```json
{
  "type": "pose_touch_update",
  "timestamp": "2023-10-20T17:00:00.000Z",
  "wall_id": 1,
  "touched_objects": ["hold_1", "hold_5", "hold_12"]
}
```

## Troubleshooting

### Common Issues

1. **"Wall not found"**: Ensure the wall ID exists
2. **"No calibration found"**: Create a calibration for the wall
3. **"SVG file not found"**: Ensure the wall has an associated SVG file
4. **"Failed to open camera"**: Check camera source and permissions
5. **"WebSocket connection failed"**: Ensure the session exists and is active

### Debug Mode

Enable debug mode for detailed logging:
```bash
uv run python manage.py pose_touch_detector --wall-id 1 --session-id <session-uuid> --debug
```

Debug mode provides:
- Detailed initialization information
- Frame processing statistics
- Touch detection results
- WebSocket communication logs

### Log Files

Logs are written to `logs/pose_touch_detector.log` with:
- Daily rotation
- 1-week retention
- Configurable log levels

## Performance Considerations

- **Camera resolution**: Higher resolution provides better accuracy but requires more processing
- **Frame rate**: 30 FPS is recommended for smooth detection
- **Touch threshold**: Adjust based on testing with your specific setup
- **Calibration quality**: Better calibration results in more accurate touch detection

## Integration with Web Interface

The touch detection system integrates with the web interface through:
1. **Session WebSocket consumers** that receive touch updates
2. **Real-time visualization** of touched holds
3. **Session recording** that can include touch data
4. **Climbing analysis** based on touch patterns

## Future Enhancements

Potential improvements to consider:
1. **Multiple person support** for group climbing sessions
2. **Touch confidence scoring** for more reliable detection
3. **Automatic calibration** without ArUco markers
4. **Machine learning-based touch detection** for improved accuracy
5. **Mobile app integration** for remote monitoring