# Pose Visualizer for Climbing Sessions

This standalone script connects to a WebSocket streaming climbing session data and provides a real-time visualization of:
- The climbing wall with holds (from SVG file)
- The climber's skeleton based on pose landmarks
- Hold status updates (untouched/touched/completed)

## Features

- Real-time visualization of climbing sessions
- SVG-based wall rendering with hold status indicators
- MediaPipe pose skeleton overlay
- Session information display
- Configurable window size and frame rate
- Color-coded hold status (gray=untouched, green=touched, red=completed)

## Requirements

Install the required packages:

```bash
pip install pygame websockets numpy
```

## Usage

### 1. With Mock Test Server (Recommended for Testing)

First, run the mock WebSocket server:

```bash
python test_pose_visualizer.py --port 8765 --frame-rate 10
```

Then, in another terminal, run the visualizer:

```bash
python pose_visualizer.py --websocket-url ws://localhost:8765 --wall-svg code/data/wall_bbox.svg
```

### 2. With Real WebSocket Session Tracker

If you have the Django session tracker running, connect to its WebSocket output:

```bash
# Option 1: Using python directly
python pose_visualizer.py --websocket-url ws://localhost:8000 --wall-svg path/to/your/wall.svg

# Option 2: Using uv (recommended for this project)
uv run python pose_visualizer.py --websocket-url ws://localhost:8000 --wall-svg path/to/your/wall.svg
```

## Command Line Options

### pose_visualizer.py

- `--websocket-url`: WebSocket URL to connect to (required)
- `--wall-svg`: Path to wall SVG file (required)
- `--window-width`: Window width in pixels (default: 1200)
- `--window-height`: Window height in pixels (default: 800)
- `--fps`: Target FPS for visualization (default: 30)

### test_pose_visualizer.py

- `--port`: Port to run mock server on (default: 8765)
- `--frame-rate`: Frame rate for sending data (default: 10)

## Controls

- **ESC**: Exit the visualizer
- **SPACE**: Print current session information to console
- **Close Window**: Exit the visualizer

## WebSocket Message Format

The visualizer expects WebSocket messages in this format:

```json
{
  "session": {
    "holds": [
      {
        "id": "hold_0",
        "type": "start|normal|finish",
        "status": "untouched|touched|completed",
        "time": "ISO_timestamp_or_null"
      }
    ],
    "startTime": "ISO_timestamp",
    "endTime": "ISO_timestamp_or_null",
    "status": "started|completed"
  },
  "pose": [
    {
      "x": 1250.5,
      "y": 800.3,
      "z": -0.2,
      "visibility": 0.95
    }
  ]
}
```

## SVG File Requirements

The SVG file should contain:
- Rectangle elements with `class="hold"`
- Hold IDs in the format `hold_N` (e.g., `hold_0`, `hold_1`)
- Proper width and height attributes for the SVG element

Example hold element:
```xml
<rect class="hold" id="hold_0" x="1178.6" y="340.9" width="147.3" height="146.4" />
```

## Color Coding

- **Gray holds**: Untouched
- **Green holds**: Currently being touched
- **Red holds**: Completed
- **Blue skeleton**: Body connections
- **Orange dots**: Landmarks
- **Red dots**: Hands/wrists
- **Light red dots**: Fingers

## Integration with websocket_pose_session_tracker.py

This visualizer is designed to work with the output from `websocket_pose_session_tracker.py`. 

To use with the session tracker:

1. Start the session tracker with appropriate output WebSocket URL
2. Connect this visualizer to the same WebSocket URL
3. The visualizer will display real-time climbing session data

Example session tracker command:
```bash
uv run python manage.py websocket_pose_session_tracker \
    --wall-id 1 \
    --input-websocket-url ws://localhost:9000 \
    --output-websocket-url ws://localhost:8000
```

Then connect the visualizer:
```bash
# Option 1: Using python directly
python pose_visualizer.py --websocket-url ws://localhost:8000 --wall-svg path/to/wall.svg

# Option 2: Using uv (recommended for this project)
uv run python pose_visualizer.py --websocket-url ws://localhost:8000 --wall-svg path/to/wall.svg
```

## Troubleshooting

### Connection Issues
- Ensure the WebSocket server is running
- Check the WebSocket URL format (ws:// or wss://)
- Verify firewall settings aren't blocking the connection

### SVG Display Issues
- Ensure the SVG file contains properly formatted hold elements
- Check that the SVG has valid width/height attributes
- Verify the file path is correct

### Performance Issues
- Reduce the FPS setting if the visualization is laggy
- Use a smaller window size
- Close other applications to free up resources

### SVG Path Element Support

The visualizer now supports both `<rect>` and `<path>` elements for holds:
- **Rectangle elements**: Used for simple rectangular holds with x, y, width, height
- **Path elements**: Automatically parsed to extract bounding box for display
- **Mixed SVGs**: Can handle SVGs with both element types

This allows compatibility with different SVG generation tools and formats.

## Development Notes

The visualizer uses pygame for rendering and websockets for communication. It scales the SVG to fit the window while maintaining aspect ratio. The pose skeleton is drawn using MediaPipe pose landmark connections.

The mock server generates realistic climbing motion patterns and simulates hold touches based on hand proximity to hold positions.