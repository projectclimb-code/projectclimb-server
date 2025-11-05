# Pose Detector to WebSocket

This script captures video from a camera or file, detects pose using MediaPipe, and streams the pose data in MediaPipe JSON format to a WebSocket.

## Features

- Real-time pose detection using MediaPipe
- Support for camera input or video files
- WebSocket streaming of pose data
- Automatic reconnection on WebSocket failures
- Configurable frame rate
- Video looping option for file input
- Comprehensive logging

## Installation

Make sure you have the required dependencies installed:

```bash
uv sync
```

The script requires the following key packages:
- `opencv-python` - For video capture
- `mediapipe` - For pose detection
- `websockets` - For WebSocket communication
- `numpy` - For array operations

## Usage

### Basic Usage

Run with default settings (camera 0, default WebSocket URL):

```bash
uv run python code/pose_detector_to_websocket.py
```

### Custom WebSocket URL

Specify a custom WebSocket URL:

```bash
uv run python code/pose_detector_to_websocket.py --websocket-url wss://your-server.com/ws/pose/
```

### Video File Input

Use a video file as input:

```bash
uv run python code/pose_detector_to_websocket.py --video-source path/to/video.mp4
```

### Loop Video File

Loop a video file indefinitely:

```bash
uv run python code/pose_detector_to_websocket.py --video-source path/to/video.mp4 --loop
```

### Custom Camera

Use a specific camera index:

```bash
uv run python code/pose_detector_to_websocket.py --video-source 1
```

### Adjust Frame Rate

Set a custom frame rate:

```bash
uv run python code/pose_detector_to_websocket.py --fps 15
```

### Debug Mode

Enable debug logging:

```bash
uv run python code/pose_detector_to_websocket.py --debug
```

### Dry Run Mode

Test pose detection without connecting to WebSocket:

```bash
uv run python code/pose_detector_to_websocket.py --dry-run
```

This is useful for testing pose detection functionality when you don't have a WebSocket server running or when you want to verify that the video source and pose detection are working correctly.

## Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--websocket-url` | `wss://climber.dev.maptnh.net:443/ws/pose/` | WebSocket URL to stream pose data to |
| `--video-source` | `0` | Video source (camera index or file path) |
| `--loop` | `False` | Loop video files indefinitely |
| `--fps` | `30` | Target frame rate for processing |
| `--debug` | `False` | Enable debug logging |
| `--dry-run` | `False` | Run without WebSocket connection (just log pose data) |

## Output Format

The script streams pose data in MediaPipe JSON format with the following structure:

```json
{
  "landmarks": [
    {
      "x": 0.5,
      "y": 0.5,
      "z": 0.0,
      "visibility": 0.9
    }
  ],
  "world_landmarks": [
    {
      "x": 0.5,
      "y": 0.5,
      "z": 0.0,
      "visibility": 0.9
    }
  ],
  "pose_landmarks": [...],
  "pose_world_landmarks": [...],
  "frame_number": 123,
  "timestamp": 12.34
}
```

### Fields Description

- `landmarks`: Array of normalized pose landmarks (0-1 range)
- `world_landmarks`: Array of world-space pose landmarks (in meters)
- `pose_landmarks`: Same as landmarks (for compatibility)
- `pose_world_landmarks`: Same as world_landmarks (for compatibility)
- `frame_number`: Sequential frame counter
- `timestamp`: Time elapsed since start in seconds

## Testing

Use the provided test script to verify the functionality:

```bash
# Test with camera
uv run python code/test_pose_detector_to_websocket.py --video-source 0

# Test with video file
uv run python code/test_pose_detector_to_websocket.py --video-source path/to/video.mp4

# Test with custom WebSocket URL
uv run python code/test_pose_detector_to_websocket.py --websocket-url ws://localhost:8000/ws/pose/
```

## Examples

### Example 1: Stream from webcam to default server

```bash
uv run python code/pose_detector_to_websocket.py
```

### Example 2: Stream from video file with looping

```bash
uv run python code/pose_detector_to_websocket.py --video-source ./data/IMG_2568.mp4 --loop
```

### Example 3: Stream from webcam to local server with debug

```bash
uv run python code/pose_detector_to_websocket.py --websocket-url ws://localhost:8000/ws/pose/ --debug
```

### Example 4: Stream from external camera at 15 FPS

```bash
uv run python code/pose_detector_to_websocket.py --video-source 1 --fps 15
```

### Example 5: Test pose detection with video file (dry run)

```bash
uv run python code/pose_detector_to_websocket.py --video-source path/to/video.mp4 --dry-run --debug
```

### Example 6: Test pose detection with camera (dry run)

```bash
uv run python code/pose_detector_to_websocket.py --video-source 0 --dry-run --fps 10
```

## Troubleshooting

### Camera Not Found

If you get an error about camera not found, try different camera indices:

```bash
# Try camera index 1
uv run python code/pose_detector_to_websocket.py --video-source 1

# Try camera index 2
uv run python code/pose_detector_to_websocket.py --video-source 2
```

### WebSocket Connection Issues

If you can't connect to the WebSocket:

1. Check that the WebSocket URL is correct
2. Verify the server is running and accessible
3. Check for firewall issues
4. Try with a local WebSocket server first

### Performance Issues

If the script is running slowly:

1. Reduce the target FPS with `--fps`
2. Try a lower MediaPipe model complexity (modify the script)
3. Ensure you have sufficient CPU/GPU resources

### No Pose Detected

If no pose is being detected:

1. Ensure there's a person clearly visible in the video
2. Check lighting conditions
3. Enable debug mode with `--debug` to see detailed logs
4. Try with a different video source

## Integration with Django

This script is designed to work with the Django WebSocket consumers in the project. The default WebSocket URL (`wss://climber.dev.maptnh.net:443/ws/pose/`) corresponds to the pose WebSocket endpoint in the Django application.

To use with a local Django development server:

```bash
uv run python code/pose_detector_to_websocket.py --websocket-url ws://localhost:8000/ws/pose/
```

Make sure your Django server is running with WebSocket support enabled:

```bash
uv run python code/manage.py runserver
```

### Testing Without WebSocket Server

If you don't have a WebSocket server running, use dry-run mode to test pose detection:

```bash
# Test with camera
uv run python code/pose_detector_to_websocket.py --dry-run --debug

# Test with video file
uv run python code/pose_detector_to_websocket.py --video-source path/to/video.mp4 --dry-run --debug
```

## License

This script is part of the ProjectClimb project and follows the same license terms.