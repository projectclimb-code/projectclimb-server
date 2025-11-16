# WebSocket Pose Detector

A Node.js script that connects to WebSocket endpoints to detect when left or right palms (from MediaPipe pose data) are within SVG path elements representing climbing holds. The script tracks hold touch timing and outputs session data to another WebSocket endpoint.

## Features

- Connects to input WebSocket to receive MediaPipe pose data
- Parses SVG files to extract climbing hold paths
- Detects when left/right wrists (landmarks 15 and 16) are within hold boundaries
- Tracks hold touch timing (requires 1 second of continuous touch)
- Outputs session data with hold status to another WebSocket endpoint
- Automatic reconnection on WebSocket disconnects
- Graceful shutdown handling

## Requirements

- Node.js (v12 or higher)
- npm package manager

## Installation

1. Install dependencies:
```bash
npm install
```

## Usage

### Command Line

```bash
node websocket_pose_detector.js <input_ws_url> <output_ws_url> <svg_file_path> <session_file_path>
```

**Example:**
```bash
node websocket_pose_detector.js ws://localhost:8080/input ws://localhost:8081/output ./wall.svg ./session.json
```

### Parameters

- `input_ws_url`: WebSocket URL to receive pose data (e.g., `ws://localhost:8080/input`)
- `output_ws_url`: WebSocket URL to send session data (e.g., `ws://localhost:8081/output`)
- `svg_file_path`: Path to SVG file containing climbing hold paths
- `session_file_path`: Path to JSON file containing session configuration

## Input Format

The script expects JSON pose data in the following format:

```json
{
    "type": "pose",
    "timestamp": 1763062977059,
    "width": 480,
    "height": 640,
    "landmarks": [
        {
            "x": 0.5062769651412964,
            "y": 0.3540618419647217,
            "z": 0.09309239685535431,
            "visibility": 0.999888002872467
        },
        // ... (33 landmarks total)
    ]
}
```

### MediaPipe Landmark Indices

- **Left wrist**: landmark 15
- **Right wrist**: landmark 16

## Output Format

The script outputs session data in the following format:

```json
{
    "session": {
        "holds": [
            {
                "id": "hold_0",
                "type": "normal",
                "status": "touched",
                "time": "2025-11-15T20:07:57.876496Z"
            }
            // ... more holds
        ],
        "startTime": "2025-11-15T20:07:57.876496Z",
        "endTime": null,
        "status": "started"
    },
    "pose": [
        // ... current pose landmarks
    ]
}
```

## Session File Format

The session file should contain climbing problem configuration:

```json
{
    "grade": "6a",
    "author": "Trinity",
    "problem": {
        "holds": [
            {
                "id": "3",
                "type": "start"
            },
            {
                "id": "101",
                "type": "finish"
            }
            // ... more holds
        ]
    }
}
```

## SVG File Format

The SVG file should contain path elements with `id` attributes that match hold IDs from the session file:

```xml
<svg width="480" height="640" xmlns="http://www.w3.org/2000/svg">
    <path id="hold_3" d="M 100 100 L 150 100 L 150 150 L 100 150 Z" fill="red" opacity="0.5"/>
    <path id="hold_101" d="M 200 200 L 250 200 L 250 250 L 200 250 Z" fill="blue" opacity="0.5"/>
</svg>
```

## Testing

Run the test suite:

```bash
npm test
```

This will:
1. Create mock WebSocket servers
2. Generate test SVG and session files
3. Send sample pose data
4. Verify output format and hold detection

## Configuration

### Touch Timing

The script requires a continuous touch for 1 second before marking a hold as "touched". This can be adjusted by modifying the `requiredTouchTime` constant in the script.

### Logging

The script provides console logging for:
- Connection status
- Hold touch events
- Error conditions
- Initialization progress

## Error Handling

- Automatic WebSocket reconnection with 5-second delay
- Graceful handling of malformed JSON data
- File reading error handling
- Invalid pose data validation

## License

MIT