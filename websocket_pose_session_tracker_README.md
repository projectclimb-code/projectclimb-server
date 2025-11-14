# WebSocket Pose Session Tracker

A Django management command for tracking climbing sessions with pose transformation and hold detection.

## Features

- Pose transformation using wall calibration
- Extended hand landmarks beyond the palm
- Hold detection using SVG paths from wall
- Configurable output (landmarks and/or SVG paths)
- Session tracking with hold status and timestamps
- Route-based hold filtering

## Usage

```bash
uv run python manage.py websocket_pose_session_tracker \
  --wall-id=1 \
  --input-websocket-url=ws://localhost:8001 \
  --output-websocket-url=ws://localhost:8002 \
  --route-data='{"grade": "6b", "author": "Trinity", "problem": {"holds": [{"id": "59", "type": "start"}, {"id": "74", "type": "start"}, {"id": "87", "type": "normal"}, {"id": "42", "type": "normal"}, {"id": "56", "type": "normal"}, {"id": "53", "type": "normal"}, {"id": "35", "type": "finish"}]}}' \
  --no-stream-landmarks \
  --stream-svg-only \
  --debug
```

## Command Line Arguments

### Required Arguments

- `--wall-id`: ID of wall to use for calibration transformation
- `--input-websocket-url`: WebSocket URL for receiving pose data
- `--output-websocket-url`: WebSocket URL for sending session data

### Optional Arguments

- `--no-stream-landmarks`: Skip streaming transformed landmarks in output
- `--stream-svg-only`: Stream only SVG paths that are touched
- `--route-data`: Route data as JSON string with holds specification
- `--proximity-threshold`: Distance in pixels to consider hand near hold (default: 50.0)
- `--touch-duration`: Time in seconds hand must be near hold to count as touch (default: 2.0)
- `--reconnect-delay`: Delay between reconnection attempts in seconds (default: 5.0)
- `--debug`: Enable debug output

## Route Data Format

The `--route-data` argument expects a JSON string with the following format:

```json
{
  "grade": "6b",
  "author": "Trinity",
  "problem": {
    "holds": [
      {"id": "59", "type": "start"},
      {"id": "74", "type": "start"},
      {"id": "87", "type": "normal"},
      {"id": "42", "type": "normal"},
      {"id": "56", "type": "normal"},
      {"id": "53", "type": "normal"},
      {"id": "35", "type": "finish"}
    ]
  }
}
```

## Output Format

The command outputs JSON in the following format:

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
      // ... other holds
    ],
    "startTime": "2025-10-19T17:44:37.187Z",
    "endTime": null,
    "status": "started"
  },
  "pose": []  // Only included if --no-stream-landmarks is NOT set
}
```

## Hold Types

- `start`: Starting holds for the route
- `normal`: Regular holds
- `finish`: Ending holds for the route

## Hold Status

- `untouched`: Hold has not been touched
- `completed`: Hold has been touched for the required duration

## Implementation Details

The command is based on `websocket_pose_transformer_with_hand_landmarks.py` with additional features:

1. **Pose Transformation**: Uses wall calibration to transform MediaPipe landmarks from camera coordinates to SVG coordinates
2. **Hand Extension**: Calculates extended hand landmarks beyond the palm for better reach detection
3. **Hold Detection**: Detects when hand landmarks are near hold paths in the SVG
4. **Session Tracking**: Tracks climbing session state and hold completion times
5. **Route Filtering**: When route data is provided, only tracks holds specified in the route

## Dependencies

- Django with Wall and WallCalibration models
- MediaPipe pose data input via WebSocket
- SVG file with hold paths
- Wall calibration with perspective transformation matrix

## WebSocket Connections

The command establishes two WebSocket connections:

1. **Input WebSocket**: Receives MediaPipe pose data from phone camera
2. **Output WebSocket**: Sends session data to client applications

Both connections include automatic reconnection with exponential backoff.