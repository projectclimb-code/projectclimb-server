# WebSocket Pose Receiver Management Command

## Overview

The `websocket_pose_receiver` management command connects to an input WebSocket to receive MediaPipe pose landmarks from `phone_camera.html`, transforms them according to wall calibration, and sends the transformed data to an output WebSocket for further processing.

## Features

- Receives pose data from phone camera WebSocket
- Transforms landmarks from image coordinates to SVG wall coordinates
- Sends transformed data to output WebSocket
- Automatic reconnection with exponential backoff
- Comprehensive logging and debugging support
- Validates incoming pose data format

## Usage

### Basic Usage

```bash
uv run python manage.py websocket_pose_receiver \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/pose/
```

### With Debug Output

```bash
uv run python manage.py websocket_pose_receiver \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/pose/ \
    --debug
```

### Custom Reconnection Delay

```bash
uv run python manage.py websocket_pose_receiver \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/pose/ \
    --reconnect-delay=10.0
```

## Command Line Arguments

- `--wall-id`: (Required) ID of the wall to use for calibration transformation
- `--input-websocket-url`: (Required) WebSocket URL for receiving pose data from phone camera
- `--output-websocket-url`: (Required) WebSocket URL for sending transformed pose data
- `--reconnect-delay`: (Optional) Delay between reconnection attempts in seconds (default: 5.0)
- `--debug`: (Optional) Enable debug output

## Input Message Format

The command expects pose data in the following format (from `phone_camera.html`):

```json
{
  "type": "pose",
  "timestamp": 1234567890,
  "width": 1280,
  "height": 720,
  "landmarks": [
    {
      "x": 0.5,
      "y": 0.3,
      "z": 0.1,
      "visibility": 0.9
    },
    ...
  ]
}
```

## Output Message Format

The command sends transformed pose data in this format:

```json
{
  "type": "transformed_pose",
  "wall_id": 1,
  "timestamp": 1234567890,
  "landmarks": [
    {
      "index": 0,
      "x": 250.5,
      "y": 180.3,
      "z": 0.1,
      "visibility": 0.9
    },
    ...
  ],
  "original_landmark_count": 33,
  "transformed_landmark_count": 33,
  "image_width": 1280,
  "image_height": 720
}
```

## Testing

### Using the Test Script

A test script is provided to generate fake pose data and test the command:

```bash
# Test with fake pose data
uv run python test_websocket_pose_receiver.py \
    --input-url=ws://localhost:8080 \
    --output-url=ws://localhost:8000/ws/pose/ \
    --duration=30
```

### Manual Testing

1. Start the pose receiver command:
   ```bash
   uv run python manage.py websocket_pose_receiver \
       --wall-id=1 \
       --input-websocket-url=ws://localhost:8080 \
       --output-websocket-url=ws://localhost:8000/ws/pose/
   ```

2. Open `phone_camera.html` in a browser and connect to `ws://localhost:8080`

3. The command will receive pose data, transform it, and send to the output WebSocket

## Dependencies

- Django
- channels
- websockets
- numpy
- loguru
- opencv-python (for calibration utilities)

## Logging

Logs are written to:
- Console output
- `logs/websocket_pose_receiver.log` (rotated daily, retained for 1 week)

## Error Handling

The command includes comprehensive error handling:
- WebSocket connection failures with automatic reconnection
- Invalid pose data validation
- Missing wall or calibration detection
- Transformation matrix errors

## Integration with Existing System

The command integrates with:
- Wall calibration system (`WallCalibration` model)
- Calibration utilities (`CalibrationUtils` class)
- Existing WebSocket infrastructure
- Django management command framework

## Troubleshooting

### Common Issues

1. **Wall not found**: Ensure the wall ID exists in the database
2. **No calibration found**: Ensure the wall has an active calibration
3. **WebSocket connection failed**: Check the WebSocket URLs are accessible
4. **Invalid pose data**: Ensure the input follows the expected format

### Debug Mode

Enable debug mode for detailed logging:
```bash
uv run python manage.py websocket_pose_receiver \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/pose/ \
    --debug