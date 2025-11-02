# WebSocket Pose Touch Detector Implementation Plan

## Overview
This document outlines the implementation of a Django management command that connects to a WebSocket to receive MediaPipe pose data, transforms coordinates according to wall calibration, detects hand touches on holds in the wall's SVG, and sends hold touch events to another WebSocket when holds are touched for a predefined duration.

## File Structure
The new management command will be created at:
`code/climber/management/commands/websocket_pose_touch_detector.py`

## Implementation Details

### 1. Imports and Dependencies
```python
import os
import json
import time
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Set, Optional, Tuple

import websockets
import numpy as np
from loguru import logger
from django.core.management.base import BaseCommand
from django.conf import settings

from climber.models import Wall, WallCalibration
from climber.svg_utils import SVGParser
from climber.calibration.calibration_utils import CalibrationUtils
```

### 2. WebSocketPoseTouchDetector Class
Main class that orchestrates the entire process.

#### Key Attributes:
- `wall_id`: ID of the wall to process
- `input_websocket_url`: URL for receiving pose data
- `output_websocket_url`: URL for sending hold touch events
- `touch_duration`: Minimum duration (seconds) a hand must touch a hold before sending event
- `reconnect_delay`: Delay between reconnection attempts
- `debug`: Enable debug logging

#### Core Methods:

##### `__init__`
Initialize all components and state variables.

##### `setup()`
Load wall data, calibration, and SVG file. Initialize WebSocket clients.

##### `connect_input_websocket()`
Establish connection to input WebSocket with reconnection logic.

##### `connect_output_websocket()`
Establish connection to output WebSocket with reconnection logic.

##### `transform_pose_coordinates(landmarks)`
Transform pose landmarks from normalized coordinates to SVG coordinates using wall calibration.

##### `detect_hand_touches(landmarks)`
Extract hand positions from pose landmarks and check for hold intersections.

##### `check_hold_intersections(hand_position)`
Check if a hand position intersects with any holds in the SVG.

##### `track_touch_durations(touched_holds)`
Track how long each hold has been touched and send events for holds that meet duration threshold.

##### `send_hold_touch_event(hold_id, touch_duration)`
Send hold touch event to output WebSocket.

##### `handle_pose_data(pose_data)`
Process incoming pose data from input WebSocket.

##### `run()`
Main event loop that manages WebSocket connections and processes pose data.

### 3. Touch Tracking Logic

#### TouchTracker Class
Helper class to track touch durations for each hold.

##### Attributes:
- `touch_start_times`: Dictionary mapping hold_id to timestamp when touch started
- `sent_events`: Set of hold_ids for which events have already been sent
- `touch_duration`: Minimum duration required before sending event

##### Methods:
- `start_touch(hold_id)`: Record when a hold is first touched
- `end_touch(hold_id)`: Clear touch tracking for a hold
- `update_touches(touched_holds)`: Update tracking based on currently touched holds
- `get_ready_holds()`: Return holds that have been touched long enough to send events

### 4. WebSocket Client Implementation

#### Input WebSocket Client
- Connects to MediaPipe pose data stream
- Expects JSON format with landmarks and timestamp
- Handles reconnection with exponential backoff
- Processes pose data through touch detection pipeline

#### Output WebSocket Client
- Connects to hold touch event receiver
- Sends JSON events when holds are touched for required duration
- Handles reconnection with exponential backoff
- Queues events if connection is lost

### 5. Command Line Arguments

```python
def add_arguments(self, parser):
    parser.add_argument(
        '--wall-id',
        type=int,
        required=True,
        help='ID of wall to process'
    )
    parser.add_argument(
        '--input-websocket-url',
        type=str,
        required=True,
        help='WebSocket URL for receiving MediaPipe pose data'
    )
    parser.add_argument(
        '--output-websocket-url',
        type=str,
        required=True,
        help='WebSocket URL for sending hold touch events'
    )
    parser.add_argument(
        '--touch-duration',
        type=float,
        default=1.0,
        help='Minimum duration (seconds) hand must touch hold before sending event'
    )
    parser.add_argument(
        '--reconnect-delay',
        type=float,
        default=5.0,
        help='Delay between reconnection attempts'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
```

### 6. Message Formats

#### Input Pose Data (expected format)
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

#### Output Hold Touch Event
```json
{
  "type": "hold_touch",
  "hold_id": "hold_123",
  "wall_id": 1,
  "timestamp": 1234567890.123,
  "touch_duration": 1.0
}
```

### 7. Reconnection Logic

#### Exponential Backoff Strategy
- Start with base delay (configurable, default 5 seconds)
- Double delay after each failed attempt
- Cap maximum delay at 60 seconds
- Reset delay after successful connection

#### Connection Monitoring
- Monitor WebSocket connection health
- Detect connection drops and initiate reconnection
- Handle different types of connection errors appropriately

### 8. Error Handling and Logging

#### Logging Strategy
- Use loguru for structured logging
- Different log levels for different types of events
- Include relevant context (wall_id, hold_id, timestamps) in log messages

#### Error Handling
- Graceful handling of WebSocket connection errors
- Recovery from temporary network issues
- Validation of incoming pose data format
- Handling of missing or invalid wall/calibration data

### 9. Coordinate Transformation

#### Process
1. Extract hand landmark positions from pose data
2. Convert normalized coordinates to image coordinates
3. Apply perspective transformation using wall calibration
4. Check for intersections with SVG hold paths

#### Hand Landmark Extraction
- Use MediaPipe pose landmarks for hands (indices 17-21 for left, 18-20 for right)
- Calculate average position of multiple hand landmarks for stability
- Filter out landmarks with low visibility

### 10. Hold Intersection Detection

#### Process
1. Transform hand position to SVG coordinates
2. Use SVGParser.point_in_path() to check each hold path
3. Return set of touched hold IDs

#### Performance Considerations
- Cache SVG path data for efficient intersection checking
- Use spatial indexing if many holds exist
- Optimize point-in-polygon tests

## Implementation Steps

1. Create basic command structure with argument parsing
2. Implement wall and calibration loading
3. Create WebSocket input client with reconnection logic
4. Implement coordinate transformation using calibration
5. Create hold intersection detection using SVG parser
6. Implement touch duration tracking
7. Create WebSocket output client with reconnection logic
8. Add comprehensive error handling and logging
9. Test with sample data
10. Optimize performance and add final polish

## Testing Strategy

### Unit Tests
- Test coordinate transformation with known calibration data
- Test touch duration tracking logic
- Test WebSocket reconnection logic

### Integration Tests
- Test end-to-end flow with mock WebSocket servers
- Test with real pose data streams
- Test with different wall configurations

### Performance Tests
- Test with high-frequency pose data (30+ FPS)
- Test with complex SVG files (many holds)
- Test memory usage over extended periods

## Usage Example

```bash
python manage.py websocket_pose_touch_detector \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8001/pose \
    --output-websocket-url=ws://localhost:8002/hold-events \
    --touch-duration=1.0 \
    --reconnect-delay=5.0 \
    --debug
```

## Dependencies

### Required Python Packages
- `websockets`: For WebSocket client implementation
- `numpy`: For numerical operations
- `loguru`: For structured logging
- `django`: For Django management command framework

### Django Dependencies
- `climber.models.Wall`: For wall data
- `climber.models.WallCalibration`: For calibration data
- `climber.svg_utils.SVGParser`: For SVG parsing and intersection detection
- `climber.calibration.calibration_utils.CalibrationUtils`: For coordinate transformation