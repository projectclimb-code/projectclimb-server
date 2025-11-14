# Pose Replayer Script

## Overview

The `pose_replayer.py` script reads pose data from a JSONS file (JSON Lines format) and replays it to a WebSocket endpoint with proper timing based on timestamps in the data. The script loops indefinitely when reaching the end of the file.

## Features

- Reads JSONS files (one JSON object per line)
- Maintains original timing based on timestamps
- WebSocket client with automatic reconnection
- Configurable timestamp field
- Infinite looping option
- Debug logging
- Error handling and recovery

## Requirements

The script uses only existing dependencies from the project:
- `websockets` (WebSocket client)
- `loguru` (Logging)
- `asyncio` (Async programming)
- Standard library modules

## Installation

No additional installation required - all dependencies are already in the project's requirements.txt.

## Usage

### Basic Usage

```bash
uv run python pose_replayer.py \
  --file 2025-11-13_pleza.jsons \
  --websocket ws://localhost:8000/ws/pose/
```

### With Custom Options

```bash
uv run python pose_replayer.py \
  --file 2025-11-13_pleza.jsons \
  --websocket ws://localhost:8000/ws/pose/ \
  --timestamp-field timestamp \
  --loop \
  --reconnect-delay 5.0 \
  --debug
```

### Single Playback (No Loop)

```bash
uv run python pose_replayer.py \
  --file session.jsons \
  --websocket ws://localhost:8000/ws/pose/ \
  --no-loop
```

## Command Line Arguments

| Argument | Type | Required | Default | Description |
|----------|-------|----------|-------------|
| `--file` | string | Yes | - | Path to the input JSONS file |
| `--websocket` | string | Yes | - | WebSocket endpoint URL |
| `--timestamp-field` | string | No | `timestamp` | Field name containing timestamp |
| `--no-loop` | flag | No | False | Disable looping (play once) |
| `--reconnect-delay` | float | No | 5.0 | Delay between reconnection attempts (seconds) |
| `--debug` | flag | No | False | Enable debug logging |

## JSON Data Format

The script is flexible and can handle various JSON data formats. Each line should contain a valid JSON object with a timestamp field.

### Example Formats

#### Simple Format
```json
{"timestamp": 1699876543.123, "data": "message1"}
{"timestamp": 1699876545.456, "data": "message2"}
```

#### Pose Data Format
```json
{
  "timestamp": 1699876543.123,
  "landmarks": [
    {"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.9},
    {"x": 0.6, "y": 0.4, "z": 0.1, "visibility": 0.8}
  ]
}
```

#### Session Format
```json
{
  "session": {
    "holds": [...],
    "startTime": "2025-01-01T12:00:00Z",
    "status": "started"
  },
  "pose": [...],
  "timestamp": "2025-01-01T12:00:00Z"
}
```

### Timestamp Formats Supported

1. **Unix timestamp (float)**: `1699876543.123`
2. **ISO 8601 string**: `"2025-01-01T12:00:00Z"`
3. **Custom field names**: Use `--timestamp-field` to specify

## How It Works

1. **File Loading**: Reads all JSON lines from the input file
2. **Timestamp Extraction**: Extracts timestamps from each JSON object
3. **Delay Calculation**: Calculates relative delays between consecutive messages
4. **WebSocket Connection**: Connects to the specified WebSocket endpoint
5. **Replay Loop**: Sends first message immediately, then waits for calculated delays
6. **Looping**: Restarts from beginning when reaching the end (if enabled)

## Error Handling

- **File Errors**: Handles missing files, invalid JSON, empty files
- **WebSocket Errors**: Automatic reconnection with exponential backoff
- **Timestamp Errors**: Fallback to index if timestamp missing/invalid
- **Network Issues**: Queues messages during disconnections

## Logging

The script uses `loguru` for logging with two levels:

- **INFO**: Normal operation messages
- **DEBUG**: Detailed message information (enabled with `--debug`)
  - Shows when waiting between messages with exact timing

Example output:
```
2025-11-13 21:48:53 | INFO     | Loaded 3 JSON objects from data.jsons
2025-11-13 21:48:53 | INFO     | Setup complete with 3 messages
2025-11-13 21:48:53 | INFO     | Connecting to WebSocket: ws://localhost:8000/ws/pose/
2025-11-13 21:48:53 | INFO     | Successfully connected to WebSocket
2025-11-13 21:48:53 | INFO     | Starting replay cycle
```

## Testing

Run the included test script to verify functionality:

```bash
uv run python simple_test.py
```

This will test:
- File reading and JSON parsing
- Timestamp extraction (float and ISO formats)
- Delay calculation
- Replayer setup

## Integration with Existing Codebase

The script follows patterns established in:
- `websocket_pose_session_tracker.py` for WebSocket implementation
- Uses `loguru` for logging (already in requirements)
- Follows the project's async/await patterns
- Uses similar error handling approaches

## Performance Considerations

- **Memory**: Loads entire file into memory (suitable for most pose recordings)
- **Timing**: Uses `asyncio.sleep()` for accurate timing
- **Network**: Queues messages to handle temporary disconnections

## Troubleshooting

### Common Issues

1. **"File not found"**: Check file path and permissions
2. **"Invalid WebSocket URL"**: Ensure URL starts with `ws://` or `wss://`
3. **"Connection refused"**: Check if WebSocket server is running
4. **"No timestamp found"**: Use `--timestamp-field` to specify correct field

### Debug Mode

Enable debug mode for detailed information:

```bash
uv run python pose_replayer.py --debug --file data.jsons --websocket ws://localhost:8000/ws/pose/
```

## Examples

### Replay to Local Development Server
```bash
uv run python pose_replayer.py \
  --file recordings/session.jsons \
  --websocket ws://localhost:8000/ws/pose/
```

### Replay to Remote Server with Custom Timestamp Field
```bash
uv run python pose_replayer.py \
  --file recordings/production.jsons \
  --websocket wss://api.example.com/ws/pose/ \
  --timestamp-field created_at \
  --reconnect-delay 10.0
```

### Single Playback for Testing
```bash
uv run python pose_replayer.py \
  --file test_data.jsons \
  --websocket ws://localhost:8000/ws/pose/ \
  --no-loop \
  --debug
```

## Future Enhancements

Potential future features:
- Speed control (replay faster/slower)
- Interactive controls (start/stop/pause)
- Progress reporting
- Multiple output endpoints
- GUI interface
- Live monitoring dashboard