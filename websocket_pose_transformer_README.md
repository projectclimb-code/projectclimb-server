# WebSocket Pose Transformer

## Overview

The WebSocket Pose Transformer is a Django management command that receives MediaPipe pose data via WebSocket, transforms the coordinates using a wall's perspective transformation matrix, and sends the transformed coordinates to an output WebSocket.

This command is useful when you need to:
- Transform pose coordinates from camera space to wall coordinate space
- Send transformed pose data to other applications or visualizations
- Process pose data without touch detection

## Key Differences from Pose Touch Detector

The WebSocket Pose Transformer is similar to the WebSocket Pose Touch Detector but with these key differences:

1. **No Touch Detection**: It only transforms coordinates without detecting hold touches
2. **All Landmarks**: It processes all visible pose landmarks, not just hands
3. **Simpler Output**: Sends transformed pose data instead of touch events
4. **No SVG Parsing**: Doesn't need to parse SVG files or check intersections

## Installation

The command is located at:
```
code/climber/management/commands/websocket_pose_transformer.py
```

## Usage

### Basic Usage

```bash
cd code
uv run python manage.py websocket_pose_transformer \
    --wall-id 1 \
    --input-websocket-url ws://localhost:8765 \
    --output-websocket-url ws://localhost:8766
```

### With Debug Output

```bash
uv run python manage.py websocket_pose_transformer \
    --wall-id 1 \
    --input-websocket-url ws://localhost:8765 \
    --output-websocket-url ws://localhost:8766 \
    --debug
```

### Custom Reconnect Delay

```bash
uv run python manage.py websocket_pose_transformer \
    --wall-id 1 \
    --input-websocket-url ws://localhost:8765 \
    --output-websocket-url ws://localhost:8766 \
    --reconnect-delay 10.0
```

## Command Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `--wall-id` | int | Yes | - | ID of the wall to use for transformation |
| `--input-websocket-url` | str | Yes | - | WebSocket URL for receiving MediaPipe pose data |
| `--output-websocket-url` | str | Yes | - | WebSocket URL for sending transformed pose data |
| `--reconnect-delay` | float | No | 5.0 | Delay between reconnection attempts (seconds) |
| `--debug` | flag | No | False | Enable debug output |

## Input Data Format

The command expects MediaPipe pose data in this format:

```json
{
  "landmarks": [
    {
      "x": 0.5,
      "y": 0.5,
      "z": 0.0,
      "visibility": 0.9
    },
    ...
  ],
  "timestamp": 1634567890.123
}
```

## Output Data Format

The command sends transformed pose data in this format:

```json
{
  "type": "transformed_pose",
  "wall_id": 1,
  "timestamp": 1634567890.123,
  "landmarks": [
    {
      "index": 0,
      "x": 150.5,
      "y": 200.3,
      "z": 0.0,
      "visibility": 0.9
    },
    ...
  ],
  "original_landmark_count": 33,
  "transformed_landmark_count": 25
}
```

## Coordinate Transformation

The command performs these transformations:

1. **Normalized to Image Coordinates**: Converts normalized coordinates (0-1) to image coordinates (pixels)
2. **Perspective Transformation**: Applies the wall's perspective transformation matrix
3. **Filtering**: Only includes landmarks with visibility > 0.5

## Testing

A test script is provided to verify the transformer functionality:

```bash
python test_websocket_pose_transformer.py
```

The test script:
1. Starts test WebSocket servers
2. Sends fake pose data to the input server
3. Verifies the transformer processes the data
4. Checks output for transformed coordinates

## Logging

The command logs to:
- Console output (INFO level by default)
- Log file: `logs/websocket_pose_transformer.log`

Log levels:
- `INFO`: Normal operation
- `DEBUG`: Detailed debugging information (use `--debug` flag)

## Error Handling

The command includes robust error handling:
- Automatic WebSocket reconnection with exponential backoff
- Input data validation
- Graceful handling of missing or invalid calibration data
- Message queuing for output WebSocket to prevent data loss

## Requirements

- Django project with `climber` app
- Wall with calibration data in database
- `websockets` Python package
- `numpy` Python package
- `loguru` Python package

## Example Integration

### 1. Set up a wall with calibration

```python
from climber.models import Wall, WallCalibration

# Create or get a wall
wall = Wall.objects.get(id=1)

# Ensure it has calibration data
calibration = WallCalibration.objects.filter(wall=wall).latest('created')
```

### 2. Start the transformer

```bash
uv run python manage.py websocket_pose_transformer \
    --wall-id 1 \
    --input-websocket-url ws://pose-source:8765 \
    --output-websocket-url ws://pose-consumer:8766
```

### 3. Send pose data to input WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8765');

// Send MediaPipe pose data
ws.send(JSON.stringify({
  landmarks: poseLandmarks,
  timestamp: Date.now() / 1000
}));
```

### 4. Receive transformed data from output WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8766');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'transformed_pose') {
    console.log('Transformed landmarks:', data.landmarks);
    // Use transformed coordinates for visualization or processing
  }
};
```

## Troubleshooting

### Common Issues

1. **Wall not found**: Check that the wall ID exists in the database
2. **No calibration found**: Ensure the wall has calibration data
3. **WebSocket connection failed**: Verify URLs are accessible and firewalls allow connections
4. **Invalid pose data**: Check that input data matches the expected format

### Debug Mode

Use the `--debug` flag to get detailed logging:

```bash
uv run python manage.py websocket_pose_transformer \
    --wall-id 1 \
    --input-websocket-url ws://localhost:8765 \
    --output-websocket-url ws://localhost:8766 \
    --debug
```

## Performance Considerations

- The command processes all visible landmarks (not just hands)
- Transformation is performed for each landmark
- Output WebSocket uses message queuing to handle temporary disconnections
- Memory usage is proportional to the number of landmarks and message queue size

## Related Commands

- `websocket_pose_touch_detector`: Similar command with touch detection
- `pose_touch_detector`: File-based pose touch detector