# WebSocket Session Tracker Management Command

## Overview

The `websocket_session_tracker` management command connects to an input WebSocket to receive MediaPipe pose landmarks from `phone_camera.html`, transforms them according to wall calibration, detects hold touches based on hand proximity, and outputs session data in the specified JSON format.

## Features

- Receives pose data from phone camera WebSocket
- Transforms landmarks from image coordinates to SVG wall coordinates
- Detects hold touches based on hand proximity to hold paths
- Tracks climbing session state (start/end times, hold status)
- Outputs session data in specified JSON format
- Automatic reconnection with exponential backoff
- Comprehensive logging and debugging support
- Configurable proximity detection and timing parameters

## Usage

### Basic Usage

```bash
uv run python manage.py websocket_session_tracker \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/session/
```

### With Custom Proximity Settings

```bash
uv run python manage.py websocket_session_tracker \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/session/ \
    --proximity-threshold=30.0 \
    --touch-duration=1.5
```

### With Debug Output

```bash
uv run python manage.py websocket_session_tracker \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/session/ \
    --debug
```

## Command Line Arguments

- `--wall-id`: (Required) ID of wall to use for hold detection
- `--input-websocket-url`: (Required) WebSocket URL for receiving pose data from phone camera
- `--output-websocket-url`: (Required) WebSocket URL for sending session data
- `--proximity-threshold`: (Optional) Distance in pixels to consider hand near hold (default: 50.0)
- `--touch-duration`: (Optional) Time in seconds hand must be near hold to count as touch (default: 2.0)
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

The command sends session data in the specified JSON format:

```json
{
  "session": {
    "holds": [
      { 
        "id": "17", 
        "type": "start", 
        "status": "completed", 
        "time": "2025-01-01T12:00:02.000Z" 
      },
      { 
        "id": "91", 
        "type": "start", 
        "status": "completed", 
        "time": "2025-01-01T12:00:23.000Z" 
      },
      { 
        "id": "6",  
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:33.000Z" 
      },
      { 
        "id": "101",
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:43.000Z" 
      },
      { 
        "id": "55", 
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:53.000Z" 
      },
      { 
        "id": "133",
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "89", 
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "41", 
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "72", 
        "type": "finish", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "11", 
        "type": "finish", 
        "status": "untouched", 
        "time": null 
      }
    ],
    "startTime": "2025-10-19T17:44:37.187Z",
    "endTime":  null,
    "status": "started"
  },
  "pose": [
    {
      "index": 0,
      "x": 250.5,
      "y": 180.3,
      "z": 0.1,
      "visibility": 0.9
    },
    ...
  ]
}
```

## Hold Detection Logic

The command detects hold touches using the following logic:

1. **Hand Tracking**: Uses MediaPipe landmarks for left hand (19, 20, 21) and right hand (22, 23, 24)
2. **Proximity Detection**: Calculates distance between hand positions and hold centers
3. **Touch Duration**: Requires hand to be near hold for specified duration (default: 2.0 seconds)
4. **Status Updates**: Updates hold status from 'untouched' to 'completed' when touch duration is met

### Hold Types

- `start`: Holds with IDs starting with 'start_'
- `finish`: Holds with IDs starting with 'finish_'
- `normal`: All other holds

## Testing

### Using Test Script

A test script is provided to generate fake pose data and test the command:

```bash
# Test with fake pose data
uv run python test_websocket_session_tracker.py \
    --input-url=ws://localhost:8080 \
    --output-url=ws://localhost:8000/ws/session/ \
    --duration=30
```

### Manual Testing

1. Start session tracker command:
   ```bash
   uv run python manage.py websocket_session_tracker \
       --wall-id=1 \
       --input-websocket-url=ws://localhost:8080 \
       --output-websocket-url=ws://localhost:8000/ws/session/
   ```

2. Open `phone_camera.html` in a browser and connect to `ws://localhost:8080`

3. The command will receive pose data, transform it, detect holds, and send session data to output WebSocket

## Dependencies

- Django
- channels
- websockets
- numpy
- loguru
- opencv-python (for calibration utilities)
- matplotlib (for SVG path processing)

## Logging

Logs are written to:
- Console output
- `logs/websocket_session_tracker.log` (rotated daily, retained for 1 week)

## Error Handling

The command includes comprehensive error handling:
- WebSocket connection failures with automatic reconnection
- Invalid pose data validation
- Missing wall or calibration detection
- Transformation matrix errors
- Hold loading errors from SVG or database

## Integration with Existing System

The command integrates with:
- Wall calibration system (`WallCalibration` model)
- Calibration utilities (`CalibrationUtils` class)
- SVG utilities (`SVGParser` class)
- Hold models (`Hold` model)
- Existing WebSocket infrastructure
- Django management command framework

## Configuration Parameters

### Proximity Threshold

- **Default**: 50.0 pixels
- **Purpose**: Maximum distance for hand to be considered "near" a hold
- **Adjustment**: Lower values require more precise hand positioning

### Touch Duration

- **Default**: 2.0 seconds
- **Purpose**: Minimum time hand must be near hold to count as touch
- **Adjustment**: Lower values make holds easier to "touch", higher values require sustained contact

## Troubleshooting

### Common Issues

1. **Wall not found**: Ensure the wall ID exists in the database
2. **No calibration found**: Ensure the wall has an active calibration
3. **No holds detected**: Check if SVG file exists or holds are defined in the database
4. **WebSocket connection failed**: Check WebSocket URLs are accessible
5. **Invalid pose data**: Ensure input follows the expected format

### Debug Mode

Enable debug mode for detailed logging:
```bash
uv run python manage.py websocket_session_tracker \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/session/ \
    --debug
```

### Performance Optimization

- Adjust proximity threshold based on wall size and calibration accuracy
- Modify touch duration based on climbing style and difficulty
- Use debug mode to monitor hand detection accuracy