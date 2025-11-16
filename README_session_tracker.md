# WebSocket Pose Session Tracker (JavaScript)

A JavaScript implementation of the WebSocket-based pose session tracker for climbing walls. This script connects to an input WebSocket to receive MediaPipe pose data, transforms the landmarks using wall calibration, detects hold touches based on hand proximity to SVG paths, and outputs session data in JSON format.

## Features

- Pose transformation using wall calibration
- Extended hand landmarks beyond the palm
- Hold detection using SVG paths
- Configurable output (landmarks and/or SVG paths)
- Session tracking with hold status and timestamps
- Command-line interface with SVG and calibration data support

## Installation

1. Install the required dependencies:

```bash
npm install
```

2. Make the script executable:

```bash
chmod +x websocket_pose_session_tracker.js
```

## Usage

### Basic Usage

```bash
node websocket_pose_session_tracker.js --svg path/to/wall.svg
```

### With Calibration Data

From file:
```bash
node websocket_pose_session_tracker.js \
  --svg path/to/wall.svg \
  --calibration path/to/calibration.json
```

From URL:
```bash
node websocket_pose_session_tracker.js \
  --svg path/to/wall.svg \
  --calibration http://10.211.117.4:8012/api/wall-calibrations/11/
```

### With Custom WebSocket URLs

```bash
node websocket_pose_session_tracker.js \
  --svg path/to/wall.svg \
  --calibration path/to/calibration.json \
  --input-websocket-url ws://localhost:8080 \
  --output-websocket-url ws://localhost:8081
```

### With Route Data

As JSON string:
```bash
node websocket_pose_session_tracker.js \
  --svg path/to/wall.svg \
  --route-data '{"grade":"5.10a","author":"John Doe","problem":{"holds":[{"id":"hold_1","type":"start"},{"id":"hold_2","type":"normal"},{"id":"hold_3","type":"finish"}]}}'
```

Or from JSON file:
```bash
node websocket_pose_session_tracker.js \
  --svg path/to/wall.svg \
  --route-data path/to/route.json
```

## Command Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--svg <path>` | Yes | - | Path to SVG file containing climbing wall holds |
| `--calibration <path>` | No | - | Path to calibration JSON file or URL to fetch calibration data |
| `--input-websocket-url <url>` | No | `ws://localhost:8080` | WebSocket URL for receiving pose data |
| `--output-websocket-url <url>` | No | `ws://localhost:8081` | WebSocket URL for sending session data |
| `--no-stream-landmarks` | No | false | Skip streaming transformed landmarks in output |
| `--stream-svg-only` | No | false | Stream only SVG paths that are touched |
| `--route-data <path>` | No | - | Route data as JSON string or path to JSON file with holds specification |
| `--proximity-threshold <number>` | No | `50.0` | Distance in pixels to consider hand near hold |
| `--touch-duration <number>` | No | `2.0` | Time in seconds hand must be near hold to count as touch |
| `--reconnect-delay <number>` | No | `5.0` | Delay between reconnection attempts in seconds |
| `--debug` | No | false | Enable debug output |

## Calibration Data Format

The calibration JSON file should contain:

```json
{
  "name": "Wall Calibration Name",
  "created": "2025-11-16T19:00:00Z",
  "is_active": true,
  "perspective_transform": [
    [1.2, 0.1, -50],
    [0.05, 1.3, -30],
    [0.0001, 0.0002, 1]
  ],
  "hand_extension_percent": 20.0,
  "wall_dimensions": {
    "width": 1200,
    "height": 2400
  },
  "calibration_points": [
    {"image": [100, 100], "wall": [0, 0]},
    {"image": [1100, 100], "wall": [1200, 0]},
    {"image": [1100, 2300], "wall": [1200, 2400]},
    {"image": [100, 2300], "wall": [0, 2400]}
  ]
}
```

## Route Data Format

The route data JSON should contain:

```json
{
  "grade": "5.10a",
  "author": "John Doe",
  "problem": {
    "holds": [
      {"id": "hold_1", "type": "start"},
      {"id": "hold_2", "type": "normal"},
      {"id": "hold_3", "type": "finish"}
    ]
  }
}
```

## Input Pose Data Format

The input WebSocket should receive pose data in this format:

```json
{
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

## Output Session Data Format

The output WebSocket sends session data in this format:

```json
{
  "session": {
    "holds": [
      {
        "id": "hold_1",
        "type": "start",
        "status": "touched",
        "time": "2025-11-16T19:30:45.123Z"
      },
      ...
    ],
    "startTime": "2025-11-16T19:30:00.000Z",
    "endTime": null,
    "status": "started"
  },
  "pose": [
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

## Testing

A test script is provided to demonstrate the functionality:

```bash
node test_session_tracker.js \
  --svg ./code/data/wall.svg \
  --calibration ./sample_calibration.json \
  --test-data ./in.json \
  --debug
```

The test script will:
1. Start a WebSocket server to send test pose data
2. Start a WebSocket server to receive session data
3. Launch the session tracker
4. Run for 30 seconds collecting data
5. Display a summary of the session

## NPM Scripts

The following NPM scripts are available:

```bash
# Run the original pose detector
npm start

# Run the session tracker
npm run session-tracker -- --svg path/to/wall.svg --calibration path/to/calibration.json

# Run the test
npm test
```

## Implementation Details

### Classes

- **InputWebSocketClient**: Handles WebSocket connections for receiving pose data
- **OutputWebSocketClient**: Handles WebSocket connections for sending session data
- **SVGParser**: Parses SVG files to extract climbing hold information
- **SVGHoldDetector**: Detects hold touches based on hand proximity to SVG paths
- **SessionTracker**: Tracks climbing session state and hold progress
- **WebSocketPoseSessionTracker**: Main class that orchestrates all components

### Key Features

1. **Automatic Reconnection**: Both WebSocket clients automatically reconnect with exponential backoff
2. **Pose Transformation**: Applies perspective transformation using calibration matrix
3. **Hand Extension**: Calculates extended hand landmarks beyond the palm
4. **Hold Detection**: Uses proximity-based detection with configurable thresholds
5. **Route Filtering**: Can filter holds based on route specification
6. **Session Tracking**: Maintains session state with timestamps and hold status

## Dependencies

- `ws`: WebSocket library for Node.js
- `commander`: Command-line interface framework
- `fast-xml-parser`: Fast XML parser for SVG files
- `mathjs`: Math library for matrix operations

## License

MIT