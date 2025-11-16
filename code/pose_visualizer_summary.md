# Pose Visualizer - Summary

I've created a complete standalone visualization system for climbing sessions that receives data from `websocket_pose_session_tracker.py` and displays both the SVG wall and climber skeleton in real-time.

## Files Created

### 1. `pose_visualizer.py` - Main Visualization Script
- **Purpose**: Standalone script that connects to WebSocket and displays climbing session data
- **Features**:
  - Real-time SVG wall rendering with hold status indicators
  - MediaPipe pose skeleton overlay
  - Color-coded hold status (gray=untouched, green=touched, red=completed)
  - Session information display
  - Configurable window size and frame rate
- **Dependencies**: pygame, websockets, numpy, xml.etree.ElementTree
- **Usage**: `uv run python pose_visualizer.py --websocket-url ws://localhost:8765 --wall-svg code/data/wall_bbox.svg`

### 2. `test_pose_visualizer.py` - Mock WebSocket Server
- **Purpose**: Creates a mock WebSocket server for testing without full Django setup
- **Features**:
  - Generates realistic climbing motion patterns
  - Simulates hold touches based on hand proximity
  - Configurable frame rate and port
- **Usage**: `uv run python test_pose_visualizer.py --port 8765 --frame-rate 10`

### 3. `run_pose_visualizer_demo.sh` - Demo Launcher Script
- **Purpose**: Convenience script to start both mock server and visualizer
- **Features**:
  - Automatically starts mock server in background
  - Launches visualizer with correct parameters
  - Handles cleanup of background processes
  - Configurable options via command line
- **Usage**: `./run_pose_visualizer_demo.sh --port 8765 --frame-rate 10`

### 4. `pose_visualizer_example.py` - Usage Example and Guide
- **Purpose**: Demonstrates integration with actual `websocket_pose_session_tracker.py`
- **Features**:
  - Shows complete workflow example
  - Provides example commands for full pipeline
  - Quick demo option with mock server
- **Usage**: `uv run python pose_visualizer_example.py --demo`

### 5. `pose_visualizer_README.md` - Comprehensive Documentation
- **Purpose**: Complete documentation for the visualization system
- **Contents**:
  - Installation instructions
  - Usage examples
  - WebSocket message format specification
  - SVG file requirements
  - Troubleshooting guide
  - Integration instructions with Django session tracker

## Key Features

### Real-time Visualization
- Displays climbing wall from SVG file with accurate scaling
- Shows climber skeleton using MediaPipe pose landmarks
- Updates hold status in real-time based on session data
- Smooth 30 FPS rendering with pygame

### Hold Status Indicators
- **Gray**: Untouched holds
- **Green**: Currently being touched
- **Red**: Completed holds
- Hold IDs displayed for easy reference

### Pose Skeleton
- Full MediaPipe pose skeleton with 33 landmarks
- Color-coded landmarks (red for hands, orange for body, light red for fingers)
- Visibility-based rendering (only shows visible landmarks)
- Realistic joint connections

### Session Information
- Message count and FPS display
- Session start time and status
- Hold completion progress (e.g., "3/5 holds completed")

## Integration with websocket_pose_session_tracker.py

The visualizer is designed to work seamlessly with the Django session tracker:

1. **Session tracker sends WebSocket messages** with:
   - Session data (holds, status, timestamps)
   - Pose landmarks (transformed coordinates)

2. **Visualizer receives and displays**:
   - SVG wall with hold status updates
   - Climber skeleton overlay
   - Real-time session progress

### Example Integration Commands

```bash
# 1. Start pose detector (input)
uv run python pose_detector_to_websocket.py --websocket-url ws://localhost:9000

# 2. Start session tracker (processing)
uv run python manage.py websocket_pose_session_tracker \
    --wall-id 1 \
    --input-websocket-url ws://localhost:9000 \
    --output-websocket-url ws://localhost:8000

# 3. Start visualizer (output)
uv run python pose_visualizer.py \
    --websocket-url ws://localhost:8000 \
    --wall-svg path/to/wall.svg
```

## Quick Demo

For immediate testing without Django setup:

```bash
# Run complete demo with mock server
./run_pose_visualizer_demo.sh

# Or run step by step:
uv run python test_pose_visualizer.py --port 8765 &
uv run python pose_visualizer.py --websocket-url ws://localhost:8765 --wall-svg code/data/wall_bbox.svg
```

## WebSocket Message Format

The visualizer expects messages in this format:

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

This matches exactly the output format from `websocket_pose_session_tracker.py`.

## Dependencies Added

I've added the required packages to the project:
- `pygame==2.6.1` - For graphics rendering
- `websockets` - For WebSocket communication

These are now available via `uv run` in the project environment.

## Summary

The created visualization system provides:
- ✅ Standalone operation (no Django required for testing)
- ✅ Real-time SVG wall and pose rendering
- ✅ Direct integration with websocket_pose_session_tracker.py
- ✅ Easy-to-use demo and example scripts
- ✅ Comprehensive documentation
- ✅ Configurable parameters
- ✅ Professional visual presentation

You can now immediately start using this to visualize climbing sessions from the WebSocket output of your session tracker!