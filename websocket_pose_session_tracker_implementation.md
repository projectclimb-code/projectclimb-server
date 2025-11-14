# WebSocket Pose Session Tracker Implementation Plan

## Overview
Create a new Django management command `websocket_pose_session_tracker.py` based on `websocket_pose_transformer_with_hand_landmarks.py` with additional features for session tracking and configurable output.

## Requirements
1. Add runtime argument to allow not streaming transformed landmarks
2. Add runtime argument to stream only SVGs touched by new hand points
3. Output JSON in specified format with session data and hold status

## Architecture

### Command Line Arguments
- `--wall-id`: ID of wall to use for calibration transformation (required)
- `--input-websocket-url`: WebSocket URL for receiving pose data (required)
- `--output-websocket-url`: WebSocket URL for sending session data (required)
- `--no-stream-landmarks`: Skip streaming transformed landmarks in output
- `--stream-svg-only`: Stream only SVG paths that are touched
- `--proximity-threshold`: Distance in pixels to consider hand near hold (default: 50.0)
- `--touch-duration`: Time in seconds hand must be near hold to count as touch (default: 2.0)
- `--reconnect-delay`: Delay between reconnection attempts in seconds (default: 5.0)
- `--debug`: Enable debug output

### Key Classes

#### 1. InputWebSocketClient (reuse from existing)
- WebSocket client for receiving MediaPipe pose data
- Handles reconnection logic
- Passes messages to handler

#### 2. OutputWebSocketClient (reuse from existing)
- WebSocket client for sending session data
- Handles reconnection logic
- Queues and sends messages

#### 3. SVGHoldDetector (enhanced version)
- Detects hold touches based on hand proximity to SVG paths
- Tracks hold touch state and timing
- Can return SVG path data for touched holds
- Methods:
  - `detect_holds_touched(transformed_landmarks)`: Detect which holds are touched
  - `get_touched_svg_paths()`: Return SVG path data for touched holds
  - `get_all_hold_status()`: Get current status of all holds

#### 4. SessionTracker (similar to existing)
- Tracks climbing session state and hold progress
- Manages session start/end times
- Formats output according to specified JSON schema
- Methods:
  - `update_session(transformed_landmarks)`: Update with new pose data
  - `get_session_data()`: Get formatted session data
  - `end_session()`: End the current session

#### 5. WebSocketPoseSessionTracker (main class)
- Coordinates all components
- Handles pose transformation using wall calibration
- Manages output based on command line flags
- Methods:
  - `setup()`: Initialize all components
  - `handle_pose_data(pose_data)`: Process incoming pose data
  - `send_session_data(session_data)`: Send formatted output
  - `run()`: Main event loop

### Output Format
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
      { 
        "id": "91", 
        "type": "start", 
        "status": "completed", 
        "time": "2025-01-01T12:00:23.000Z" 
      },
      { 
        "id": "6",  
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:33.000Z" 
      },
      { 
        "id": "101",
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:43.000Z" 
      },
      { 
        "id": "55", 
        "type": "normal", 
        "status": "completed", 
        "time": "2025-01-01T12:00:53.000Z" 
      },
      { 
        "id": "133",
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "89", 
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "41", 
        "type": "normal", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "72", 
        "type": "finish", 
        "status": "untouched", 
        "time": null 
      },
      { 
        "id": "11", 
        "type": "finish", 
        "status": "untouched", 
        "time": null 
      }
    ],
    "startTime": "2025-10-19T17:44:37.187Z",
    "endTime":  null,
    "status": "started"
  },
  "pose": []  // Only included if --no-stream-landmarks is NOT set
}
```

### Implementation Steps

1. **Create basic command structure**
   - Copy from `websocket_pose_transformer_with_hand_landmarks.py`
   - Update class names and docstrings
   - Add new command line arguments

2. **Implement SVGHoldDetector class**
   - Base on existing HoldDetector from websocket_session_tracker.py
   - Add methods to return SVG path data
   - Use SVGParser to extract path information

3. **Implement SessionTracker class**
   - Track session state (start time, end time, status)
   - Format output according to specified schema
   - Handle different output modes based on flags

4. **Update WebSocketPoseSessionTracker class**
   - Integrate new components
   - Handle pose transformation using wall calibration
   - Manage output based on command line flags
   - Add extended hand landmarks from original code

5. **Add error handling and logging**
   - Proper error handling for all components
   - Debug logging for troubleshooting
   - Log file configuration

6. **Test implementation**
   - Test with sample data
   - Verify output format
   - Test different flag combinations

### Key Differences from Existing Code

1. **From websocket_pose_transformer_with_hand_landmarks.py**:
   - Keep pose transformation and hand landmark extension
   - Add session tracking and hold detection
   - Add configurable output options

2. **From websocket_session_tracker.py**:
   - Adapt hold detection for SVG paths
   - Enhance to return SVG path data
   - Integrate with pose transformation

### File Structure
```
code/climber/management/commands/websocket_pose_session_tracker.py
├── Imports
├── InputWebSocketClient class (reuse)
├── OutputWebSocketClient class (reuse)
├── SVGHoldDetector class (enhanced)
├── SessionTracker class (adapted)
├── WebSocketPoseSessionTracker class (main)
├── validate_pose_data function (adapted)
├── calculate_extended_hand_landmarks function (reuse)
└── Command class (Django management command)
```

### Dependencies
- Existing: websockets, numpy, loguru, django
- From existing code: transformation_utils, svg_utils, calibration_utils
- Models: Wall, WallCalibration, Hold

### Testing Strategy
1. Test with mock WebSocket connections
2. Verify pose transformation works correctly
3. Test hold detection with sample SVG paths
4. Validate output format matches specification
5. Test different flag combinations