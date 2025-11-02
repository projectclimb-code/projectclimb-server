# Pose Skeleton Visualization

This page provides a real-time visualization of human pose skeletons from MediaPipe pose data received via WebSocket.

## Features

- Real-time pose skeleton rendering on HTML5 canvas
- WebSocket connection to receive pose data
- Configurable WebSocket URL
- FPS counter and landmark statistics
- Visual connection status indicator
- Support for MediaPipe pose format (33 landmarks)

## Access

The pose skeleton visualization page is available at:
```
http://localhost:8000/pose-skeleton/
```

You can also specify a custom WebSocket URL:
```
http://localhost:8000/pose-skeleton/?ws_url=ws://your-server:port/endpoint/
```

## WebSocket Data Format

The page expects MediaPipe pose data in the following JSON format:

```json
{
  "landmarks": [
    {
      "x": 0.5,
      "y": 0.3,
      "z": 0.0,
      "visibility": 0.9
    },
    ...
  ],
  "frame_number": 123,
  "timestamp": 1234567890
}
```

- `landmarks`: Array of 33 pose landmarks (MediaPipe Pose format)
- `x`, `y`: Normalized coordinates (0.0 to 1.0)
- `z`: Depth coordinate (optional)
- `visibility`: Visibility confidence (0.0 to 1.0)
- `frame_number`: Sequential frame number (optional)
- `timestamp`: Unix timestamp (optional)

## Testing

### Using the Test Script

A test script is provided to send fake pose data for testing:

```bash
cd code
uv run python test_pose_skeleton.py
```

This will connect to `ws://localhost:8000/ws/pose/` and send animated pose data.

### Using the Pose Streamer

You can also use the existing pose streamer with a camera or video file:

```bash
cd code
uv run python pose_streamer.py --source 0
```

Or with a video file:
```bash
cd code
uv run python pose_streamer.py --file data/bolder2.mov
```

## Visualization Details

- **Green dots**: Individual pose landmarks
- **White lines**: Connections between landmarks (skeleton)
- **Landmark indices**: Small numbers next to each landmark for debugging
- **Visibility filtering**: Only landmarks with visibility > 0.5 are rendered

## Pose Connections

The visualization uses the standard MediaPipe Pose connections:

```
[0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8],
[9, 10], [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
[12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [11, 23], [12, 24],
[23, 24], [23, 25], [24, 26], [25, 27], [26, 28], [27, 29], [28, 30],
[29, 31], [30, 32], [27, 31], [28, 32]
```

## Browser Compatibility

- Modern browsers with WebSocket support
- HTML5 Canvas support
- JavaScript ES6+ support

## Troubleshooting

1. **WebSocket connection fails**: Ensure the Django server is running and the WebSocket endpoint is accessible
2. **No pose data visible**: Check that the data format matches the expected MediaPipe format
3. **Performance issues**: The visualization is optimized for 30 FPS; higher rates may impact performance

## Integration with Existing WebSocket Endpoints

The pose skeleton visualization can work with existing WebSocket consumers:

- `/ws/pose/` - Main pose streaming endpoint
- `/ws/test_pose/` - Test pose endpoint
- Custom endpoints can be used by specifying the URL in the connection settings