# WebSocket Pose Receiver Management Command Implementation

## Overview
Create a Django management command that connects to an input WebSocket to receive MediaPipe pose landmarks from `phone_camera.html`, transforms them according to wall calibration, and sends the transformed data to an output WebSocket for further processing.

## File Structure
```
code/climber/management/commands/websocket_pose_receiver.py
```

## Implementation Details

### 1. Basic Command Structure
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
from channels.db import database_sync_to_async

from climber.models import Wall, WallCalibration
from climber.calibration.calibration_utils import CalibrationUtils

class Command(BaseCommand):
    help = 'WebSocket-based pose receiver for transforming MediaPipe pose landmarks from phone camera'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--wall-id',
            type=int,
            required=True,
            help='ID of wall to use for calibration transformation'
        )
        parser.add_argument(
            '--input-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for receiving pose data from phone camera'
        )
        parser.add_argument(
            '--output-websocket-url',
            type=str,
            required=True,
            help='WebSocket URL for sending transformed pose data'
        )
        parser.add_argument(
            '--reconnect-delay',
            type=float,
            default=5.0,
            help='Delay between reconnection attempts in seconds'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug output'
        )
```

### 2. Input WebSocket Client
```python
class InputWebSocketClient:
    """WebSocket client for receiving MediaPipe pose data from phone camera"""
    
    def __init__(self, url, message_handler, reconnect_delay=5.0):
        self.url = url
        self.message_handler = message_handler
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        
    async def connect(self):
        """Connect to input WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to input WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to input WebSocket")
                self.current_reconnect_delay = self.reconnect_delay
                
                # Listen for messages
                await self.listen_for_messages()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Input WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in input WebSocket: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def listen_for_messages(self):
        """Listen for incoming messages and pass to handler"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.message_handler(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Input WebSocket connection closed")
            raise
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            raise
```

### 3. Output WebSocket Client
```python
class OutputWebSocketClient:
    """WebSocket client for sending transformed pose data"""
    
    def __init__(self, url, reconnect_delay=5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.message_queue = asyncio.Queue()
        self.sender_task = None
        
    async def connect(self):
        """Connect to output WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to output WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to output WebSocket")
                self.current_reconnect_delay = self.reconnect_delay
                
                # Start sender task
                self.sender_task = asyncio.create_task(self.message_sender())
                
                # Keep connection alive
                await self.keep_alive()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Output WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in output WebSocket: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def send_message(self, message):
        """Queue a message to be sent"""
        await self.message_queue.put(message)
```

### 4. Pose Data Validation
```python
def validate_pose_data(data):
    """Validate incoming pose data format from phone camera"""
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    
    if 'type' not in data or data['type'] != 'pose':
        return False, "Missing or invalid 'type' field (expected 'pose')"
    
    if 'landmarks' not in data:
        return False, "Missing 'landmarks' field"
    
    if 'width' not in data or 'height' not in data:
        return False, "Missing 'width' or 'height' fields"
    
    landmarks = data['landmarks']
    if not isinstance(landmarks, list):
        return False, "Landmarks must be a list"
    
    for i, landmark in enumerate(landmarks):
        if not isinstance(landmark, dict):
            return False, f"Landmark {i} must be a dictionary"
        
        required_fields = ['x', 'y', 'z', 'visibility']
        for field in required_fields:
            if field not in landmark:
                return False, f"Landmark {i} missing '{field}' field"
            
            if not isinstance(landmark[field], (int, float)):
                return False, f"Landmark {i} field '{field}' must be numeric"
    
    return True, "Valid"
```

### 5. Coordinate Transformation
```python
def transform_landmarks_to_svg_coordinates(landmarks, calibration_utils, transform_matrix, image_size):
    """Transform normalized landmark positions to SVG coordinates"""
    transformed_landmarks = []
    
    width, height = image_size
    
    for landmark in landmarks:
        # Convert normalized position to image coordinates
        img_x = landmark['x'] * width
        img_y = landmark['y'] * height
        
        # Transform to SVG coordinates using calibration
        svg_point = calibration_utils.transform_point_to_svg(
            (img_x, img_y),
            transform_matrix
        )
        
        if svg_point:
            transformed_landmarks.append({
                'index': landmarks.index(landmark),  # Get original index
                'x': svg_point[0],
                'y': svg_point[1],
                'z': landmark['z'],  # Keep original z-coordinate
                'visibility': landmark['visibility']
            })
    
    return transformed_landmarks
```

### 6. Main WebSocket Pose Receiver Class
```python
class WebSocketPoseReceiver:
    """Main class for WebSocket-based pose coordinate transformation"""
    
    def __init__(self, wall_id, input_websocket_url, output_websocket_url,
                 reconnect_delay=5.0, debug=False):
        self.wall_id = wall_id
        self.input_websocket_url = input_websocket_url
        self.output_websocket_url = output_websocket_url
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.wall = None
        self.calibration = None
        self.calibration_utils = None
        self.transform_matrix = None
        
        # WebSocket clients
        self.input_client = None
        self.output_client = None
        
        # State
        self.running = False
        
    async def setup(self):
        """Setup all components"""
        # Load wall and calibration
        try:
            self.wall = await database_sync_to_async(Wall.objects.get)(id=self.wall_id)
            logger.info(f"Loaded wall: {self.wall.name}")
        except Wall.DoesNotExist:
            logger.error(f"Wall with ID {self.wall_id} not found")
            return False
        
        # Get active calibration
        try:
            self.calibration = await database_sync_to_async(
                lambda: self.wall.calibrations.filter(is_active=True).first()
            )()
            if not self.calibration:
                # Fallback to latest calibration
                self.calibration = await database_sync_to_async(
                    lambda: self.wall.calibrations.latest('created')
                )()
            logger.info(f"Loaded calibration: {self.calibration.name}")
        except WallCalibration.DoesNotExist:
            logger.error(f"No calibration found for wall {self.wall.name}")
            return False
        
        # Setup calibration utils
        self.calibration_utils = CalibrationUtils()
        self.transform_matrix = np.array(self.calibration.perspective_transform, dtype=np.float32)
        
        # Setup WebSocket clients
        self.input_client = InputWebSocketClient(
            self.input_websocket_url,
            self.handle_pose_data,
            self.reconnect_delay
        )
        
        self.output_client = OutputWebSocketClient(
            self.output_websocket_url,
            self.reconnect_delay
        )
        
        return True
    
    async def handle_pose_data(self, pose_data):
        """Handle incoming pose data from phone camera"""
        try:
            # Validate pose data
            is_valid, error_msg = validate_pose_data(pose_data)
            if not is_valid:
                logger.warning(f"Invalid pose data: {error_msg}")
                return
            
            # Extract image dimensions
            width = pose_data.get('width', 1280)
            height = pose_data.get('height', 720)
            image_size = (width, height)
            
            # Extract landmarks
            landmarks = pose_data['landmarks']
            
            # Transform coordinates
            transformed_landmarks = transform_landmarks_to_svg_coordinates(
                landmarks, self.calibration_utils, self.transform_matrix, image_size
            )
            
            # Send transformed pose data
            await self.send_transformed_pose_data(transformed_landmarks, pose_data)
            
            if self.debug and transformed_landmarks:
                logger.info(f"Transformed {len(transformed_landmarks)} landmarks")
                
        except Exception as e:
            logger.error(f"Error handling pose data: {e}")
    
    async def send_transformed_pose_data(self, transformed_landmarks, original_data):
        """Send transformed pose data to output WebSocket"""
        message = {
            'type': 'transformed_pose',
            'wall_id': self.wall_id,
            'timestamp': original_data.get('timestamp', time.time()),
            'landmarks': transformed_landmarks,
            'original_landmark_count': len(original_data.get('landmarks', [])),
            'transformed_landmark_count': len(transformed_landmarks),
            'image_width': original_data.get('width'),
            'image_height': original_data.get('height')
        }
        
        await self.output_client.send_message(message)
        logger.debug(f"Sent transformed pose data with {len(transformed_landmarks)} landmarks")
```

### 7. Command Handle Method
```python
    def handle(self, *args, **options):
        # Configure logging
        logger.remove()
        logger.add(
            "logs/websocket_pose_receiver.log",
            rotation="1 day",
            retention="1 week",
            level="DEBUG" if options['debug'] else "INFO"
        )
        logger.add(
            lambda msg: self.stdout.write(msg),
            level="DEBUG" if options['debug'] else "INFO"
        )
        
        # Create and run receiver
        receiver = WebSocketPoseReceiver(
            wall_id=options['wall_id'],
            input_websocket_url=options['input_websocket_url'],
            output_websocket_url=options['output_websocket_url'],
            reconnect_delay=options['reconnect_delay'],
            debug=options['debug']
        )
        
        # Run receiver
        asyncio.run(receiver.run())
```

## Usage Example

```bash
# Run the management command
uv run python manage.py websocket_pose_receiver \
    --wall-id=1 \
    --input-websocket-url=ws://localhost:8080 \
    --output-websocket-url=ws://localhost:8000/ws/pose/ \
    --debug
```

## Expected Input Message Format (from phone_camera.html)
```json
{
  "type": "pose",
  "timestamp": 1234567890,
  "width": 1280,
  "height": 720,
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

## Expected Output Message Format
```json
{
  "type": "transformed_pose",
  "wall_id": 1,
  "timestamp": 1234567890,
  "landmarks": [
    {
      "index": 0,
      "x": 250.5,
      "y": 180.3,
      "z": 0.1,
      "visibility": 0.9
    },
    ...
  ],
  "original_landmark_count": 33,
  "transformed_landmark_count": 33,
  "image_width": 1280,
  "image_height": 720
}
```

## Dependencies
- websockets
- numpy
- loguru
- Django
- channels

## Testing Strategy
1. Test with fake pose data generator
2. Test WebSocket reconnection logic
3. Test coordinate transformation accuracy
4. Test with different wall calibrations
5. Test error handling for invalid data