# WebSocket Pose Touch Detector

## Overview
The WebSocket Pose Touch Detector is a Django management command that connects to a WebSocket to receive MediaPipe pose data, transforms coordinates according to wall calibration, detects when hands touch holds in the wall's SVG file, and sends hold touch events to another WebSocket when holds are touched for a predefined duration.

## Features

- **Dual WebSocket Architecture**: Separate connections for input pose data and output hold events
- **Configurable Touch Duration**: Set how long a hand must touch a hold before sending an event
- **Automatic Reconnection**: Robust reconnection logic with exponential backoff
- **Coordinate Transformation**: Uses wall calibration to transform pose coordinates to SVG coordinate system
- **Real-time Processing**: Handles high-frequency pose data (30+ FPS)
- **Comprehensive Logging**: Structured logging with debug options

## Installation

### Dependencies
The command requires the following Python packages:
- `websockets`: WebSocket client implementation
- `numpy`: Numerical operations and coordinate transformations
- `loguru`: Structured logging
- `django`: Django management command framework

Install dependencies using:
```bash
cd code
uv add websockets numpy loguru
```

## Usage

### Basic Usage
```bash
cd code
uv run python manage.py websocket_pose_touch_detector \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8001/pose \
    --output-websocket-url=ws://localhost:8002/hold-events
```

### With Custom Options
```bash
uv run python manage.py websocket_pose_touch_detector \
    --wall-id=1 \
    --input-websocket-url=ws://pose-server.example.com/pose \
    --output-websocket-url=ws://event-server.example.com/hold-events \
    --touch-duration=2.0 \
    --reconnect-delay=10.0 \
    --debug
```

### Command Line Arguments

- `--wall-id` (required): ID of the wall to process
- `--input-websocket-url` (required): WebSocket URL for receiving MediaPipe pose data
- `--output-websocket-url` (required): WebSocket URL for sending hold touch events
- `--touch-duration` (optional): Minimum duration (seconds) hand must touch hold before sending event (default: 1.0)
- `--reconnect-delay` (optional): Delay between reconnection attempts (default: 5.0)
- `--debug` (optional): Enable debug output

## Data Formats

### Input Pose Data Format
The command expects JSON messages with the following format:

```json
{
  "landmarks": [
    {"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.9},
    {"x": 0.51, "y": 0.31, "z": 0.01, "visibility": 0.85},
    ...
  ],
  "timestamp": 1234567890.123
}
```

**Landmark Details**:
- `x`, `y`, `z`: Normalized coordinates (0.0 to 1.0)
- `visibility`: Confidence score (0.0 to 1.0)
- The command uses MediaPipe pose landmark indices:
  - Left hand: 15 (elbow), 17 (wrist), 19 (index finger), 21 (pinky)
  - Right hand: 16 (elbow), 18 (wrist), 20 (index finger), 22 (pinky)

### Output Hold Touch Event Format
The command sends JSON messages with the following format:

```json
{
  "type": "hold_touch",
  "hold_id": "hold_123",
  "wall_id": 1,
  "timestamp": 1234567890.123,
  "touch_duration": 1.0
}
```

**Event Details**:
- `type`: Always "hold_touch"
- `hold_id`: ID of the hold that was touched (from SVG path ID)
- `wall_id`: ID of the wall being processed
- `timestamp`: Unix timestamp when the event was sent
- `touch_duration`: Actual duration the hold was touched

## Setup Requirements

### Database Setup
1. Ensure you have a wall configured in the database:
   ```python
   from climber.models import Wall, WallCalibration
   
   wall = Wall.objects.create(
       name="Climbing Wall",
       venue=your_venue,
       svg_file="wall.svg",
       width_mm=2500.0,
       height_mm=3330.0
   )
   ```

2. Create a calibration for the wall:
   ```python
   calibration = WallCalibration.objects.create(
       wall=wall,
       name="Wall Calibration",
       calibration_type="manual_points",
       perspective_transform=[
           [1.0, 0.0, 0.0],
           [0.0, 1.0, 0.0],
           [0.0, 0.0, 1.0]
       ],
       is_active=True
   )
   ```

### SVG File Setup
1. Upload an SVG file to the wall's `svg_file` field
2. Ensure SVG paths have meaningful IDs that will be used as hold IDs
3. SVG paths should represent the shape of climbing holds

### WebSocket Servers
1. Set up a WebSocket server that provides MediaPipe pose data
2. Set up a WebSocket server to receive hold touch events
3. Ensure both servers are accessible from the command

## Testing

### Running Tests
A test script is provided to verify the command works correctly:

```bash
python test_websocket_pose_touch_detector.py
```

This script:
1. Tests individual components (pose validation, hand extraction, touch tracking)
2. Starts mock WebSocket servers for pose data and events
3. Runs the detector with mocked components
4. Verifies events are sent correctly

### Test with Mock Data
You can test the command with mock WebSocket servers:

```bash
# Terminal 1: Start mock pose server
python -c "
import asyncio
import websockets
import json
import time

async def pose_server():
    async def handler(websocket, path):
        while True:
            pose_data = {
                'landmarks': [
                    {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}
                ],
                'timestamp': time.time()
            }
            await websocket.send(json.dumps(pose_data))
            await asyncio.sleep(0.1)
    
    server = await websockets.serve(handler, 'localhost', 8001)
    await server.wait_closed()

asyncio.run(pose_server())
"

# Terminal 2: Start mock event server
python -c "
import asyncio
import websockets
import json

async def event_server():
    async def handler(websocket, path):
        async for message in websocket:
            event = json.loads(message)
            print(f'Received event: {event}')
    
    server = await websockets.serve(handler, 'localhost', 8002)
    await server.wait_closed()

asyncio.run(event_server())
"

# Terminal 3: Run the detector
cd code
uv run python manage.py websocket_pose_touch_detector \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8001 \
    --output-websocket-url=ws://localhost:8002 \
    --touch-duration=0.5 \
    --debug
```

## Troubleshooting

### Common Issues

1. **Wall Not Found**
   ```
   ERROR: Wall with ID X not found
   ```
   - Verify the wall ID exists in the database
   - Check the wall is not marked as deleted

2. **No Calibration Found**
   ```
   ERROR: No calibration found for wall Wall Name
   ```
   - Ensure the wall has at least one calibration
   - Check the calibration is marked as active

3. **SVG File Not Found**
   ```
   ERROR: SVG file not found: /path/to/svg/file.svg
   ```
   - Verify the SVG file path in the wall record
   - Check the file exists in the media directory

4. **WebSocket Connection Failed**
   ```
   ERROR: Input WebSocket connection error: [Errno 111] Connection refused
   ```
   - Verify the WebSocket server is running
   - Check the URL and port are correct
   - Ensure firewall allows the connection

5. **Invalid Pose Data**
   ```
   WARNING: Invalid pose data: Missing 'landmarks' field
   ```
   - Verify the pose data format matches the expected schema
   - Check the WebSocket server is sending valid JSON

### Debug Mode
Enable debug mode for detailed logging:

```bash
uv run python manage.py websocket_pose_touch_detector \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8001/pose \
    --output-websocket-url=ws://localhost:8002/hold-events \
    --debug
```

Debug mode provides:
- Detailed logging of all processing steps
- Information about touched holds
- WebSocket connection status
- Error stack traces

### Log Files
Logs are written to:
- `logs/websocket_pose_touch_detector.log` (rotated daily, kept for 1 week)

## Performance Considerations

### System Requirements
- **CPU**: Moderate (for coordinate transformations and intersection detection)
- **Memory**: Low (minimal memory footprint for long-running processes)
- **Network**: Stable WebSocket connections required

### Optimization Tips
1. **SVG Complexity**: Simplify SVG paths for better performance
2. **Touch Duration**: Increase touch duration to reduce event frequency
3. **Network Latency**: Use WebSocket servers with low latency
4. **Processing Rate**: Monitor CPU usage at high pose data rates

## Architecture

### Component Overview
```
WebSocketPoseTouchDetector
├── InputWebSocketClient (receives pose data)
├── OutputWebSocketClient (sends hold events)
├── TouchTracker (manages touch durations)
├── SVGParser (parses wall SVG)
└── CalibrationUtils (transforms coordinates)
```

### Data Flow
1. Input WebSocket receives MediaPipe pose data
2. Hand positions are extracted from pose landmarks
3. Coordinates are transformed using wall calibration
4. Hold intersections are detected using SVG paths
5. Touch durations are tracked for each hold
6. Events are sent when touch duration threshold is met

## Contributing

### Code Structure
- Main command: `code/climber/management/commands/websocket_pose_touch_detector.py`
- Test script: `test_websocket_pose_touch_detector.py`
- Documentation: `websocket_pose_touch_detector_README.md`

### Adding Features
1. Modify the `WebSocketPoseTouchDetector` class for new functionality
2. Update the command line arguments in the `Command` class
3. Add tests for new features
4. Update documentation

## License

This code is part of the ProjectClimb climbing wall system.