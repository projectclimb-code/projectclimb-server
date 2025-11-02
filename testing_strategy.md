# Testing Strategy for WebSocket Pose Touch Detector

## Overview
This document outlines the comprehensive testing strategy for the WebSocket-based pose touch detector management command.

## Testing Environment Setup

### Dependencies
- Python 3.8+
- Django with the existing project setup
- WebSocket test server (can use `websockets` library)
- Test pose data files
- Mock WebSocket servers for testing

### Test Data
- Sample wall with calibration data in the database
- SVG file with known hold positions
- Sample MediaPipe pose data files
- Network simulation tools for testing connection issues

## Unit Tests

### 1. Coordinate Transformation Tests

#### Test Cases
```python
# test_coordinate_transformation.py
import unittest
import numpy as np
from unittest.mock import Mock, patch
from climber.calibration.calibration_utils import CalibrationUtils

class TestCoordinateTransformation(unittest.TestCase):
    def setUp(self):
        self.calibration_utils = CalibrationUtils()
        # Mock transformation matrix
        self.transform_matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ])
    
    def test_transform_normalized_to_image_coordinates(self):
        """Test conversion from normalized to image coordinates"""
        # Test with 1280x720 image
        normalized_pos = (0.5, 0.5)
        expected_img_pos = (640, 360)
        
        img_x = normalized_pos[0] * 1280
        img_y = normalized_pos[1] * 720
        
        self.assertEqual((img_x, img_y), expected_img_pos)
    
    def test_transform_image_to_svg_coordinates(self):
        """Test transformation from image to SVG coordinates"""
        img_point = (640, 360)
        
        svg_point = self.calibration_utils.transform_point_to_svg(
            img_point,
            self.transform_matrix
        )
        
        # With identity matrix, coordinates should be the same
        self.assertEqual(svg_point, (640.0, 360.0))
    
    def test_transform_with_real_calibration_matrix(self):
        """Test transformation with real calibration data"""
        # Use a real transformation matrix from calibration
        real_transform = np.array([
            [1.2, 0.1, -50.0],
            [0.05, 1.3, -30.0],
            [0.0001, 0.0002, 1.0]
        ])
        
        img_point = (640, 360)
        svg_point = self.calibration_utils.transform_point_to_svg(
            img_point,
            real_transform
        )
        
        # Verify the transformation produces reasonable results
        self.assertIsInstance(svg_point, tuple)
        self.assertEqual(len(svg_point), 2)
        self.assertIsInstance(svg_point[0], float)
        self.assertIsInstance(svg_point[1], float)
```

### 2. Touch Duration Tracking Tests

#### Test Cases
```python
# test_touch_tracker.py
import time
import unittest
from websocket_pose_touch_detector import TouchTracker

class TestTouchTracker(unittest.TestCase):
    def setUp(self):
        self.touch_tracker = TouchTracker(touch_duration=1.0)
    
    def test_start_touch(self):
        """Test starting touch tracking"""
        timestamp = time.time()
        self.touch_tracker.start_touch("hold_1", timestamp)
        
        self.assertIn("hold_1", self.touch_tracker.touch_start_times)
        self.assertEqual(self.touch_tracker.touch_start_times["hold_1"], timestamp)
    
    def test_end_touch(self):
        """Test ending touch tracking"""
        timestamp = time.time()
        self.touch_tracker.start_touch("hold_1", timestamp)
        self.touch_tracker.end_touch("hold_1")
        
        self.assertNotIn("hold_1", self.touch_tracker.touch_start_times)
        self.assertNotIn("hold_1", self.touch_tracker.sent_events)
    
    def test_touch_duration_threshold(self):
        """Test touch duration threshold logic"""
        start_time = time.time()
        self.touch_tracker.start_touch("hold_1", start_time)
        
        # Should not be ready immediately
        ready_holds = self.touch_tracker.get_ready_holds(start_time + 0.5)
        self.assertEqual(len(ready_holds), 0)
        
        # Should be ready after threshold
        ready_holds = self.touch_tracker.get_ready_holds(start_time + 1.5)
        self.assertEqual(len(ready_holds), 1)
        self.assertEqual(ready_holds[0]['hold_id'], "hold_1")
        self.assertGreaterEqual(ready_holds[0]['touch_duration'], 1.0)
    
    def test_multiple_holds_tracking(self):
        """Test tracking multiple holds simultaneously"""
        timestamp = time.time()
        self.touch_tracker.start_touch("hold_1", timestamp)
        self.touch_tracker.start_touch("hold_2", timestamp + 0.5)
        
        # Update touches
        self.touch_tracker.update_touches(["hold_1", "hold_2"], timestamp + 1.0)
        
        # Both should be tracked
        self.assertIn("hold_1", self.touch_tracker.touch_start_times)
        self.assertIn("hold_2", self.touch_tracker.touch_start_times)
        
        # End touch for hold_1
        self.touch_tracker.update_touches(["hold_2"], timestamp + 1.5)
        
        self.assertNotIn("hold_1", self.touch_tracker.touch_start_times)
        self.assertIn("hold_2", self.touch_tracker.touch_start_times)
```

### 3. Hand Position Extraction Tests

#### Test Cases
```python
# test_hand_extraction.py
import unittest
from websocket_pose_touch_detector import extract_hand_positions

class TestHandExtraction(unittest.TestCase):
    def test_extract_valid_hand_positions(self):
        """Test extraction with valid pose landmarks"""
        landmarks = [
            {'x': 0.1, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},  # 0
            # ... other landmarks ...
            {'x': 0.3, 'y': 0.4, 'z': 0.0, 'visibility': 0.8},  # 15 (left elbow)
            {'x': 0.35, 'y': 0.45, 'z': 0.0, 'visibility': 0.9},  # 16 (right elbow)
            {'x': 0.32, 'y': 0.48, 'z': 0.0, 'visibility': 0.95},  # 17 (left wrist)
            {'x': 0.38, 'y': 0.49, 'z': 0.0, 'visibility': 0.92},  # 18 (right wrist)
            {'x': 0.31, 'y': 0.52, 'z': 0.0, 'visibility': 0.9},  # 19 (left index)
            {'x': 0.39, 'y': 0.53, 'z': 0.0, 'visibility': 0.88},  # 20 (right index)
            {'x': 0.33, 'y': 0.51, 'z': 0.0, 'visibility': 0.85},  # 21 (left pinky)
            {'x': 0.37, 'y': 0.54, 'z': 0.0, 'visibility': 0.87},  # 22 (right pinky)
        ]
        
        left_pos, right_pos = extract_hand_positions(landmarks)
        
        self.assertIsNotNone(left_pos)
        self.assertIsNotNone(right_pos)
        self.assertEqual(len(left_pos), 2)  # x, y coordinates
        self.assertEqual(len(right_pos), 2)  # x, y coordinates
        
        # Check positions are reasonable (within [0, 1] range)
        self.assertGreaterEqual(left_pos[0], 0)
        self.assertLessEqual(left_pos[0], 1)
        self.assertGreaterEqual(left_pos[1], 0)
        self.assertLessEqual(left_pos[1], 1)
    
    def test_extract_with_low_visibility(self):
        """Test extraction with low visibility landmarks"""
        landmarks = [
            {'x': 0.1, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},  # 0
            # ... other landmarks ...
            {'x': 0.3, 'y': 0.4, 'z': 0.0, 'visibility': 0.8},  # 15 (left elbow)
            {'x': 0.35, 'y': 0.45, 'z': 0.0, 'visibility': 0.9},  # 16 (right elbow)
            {'x': 0.32, 'y': 0.48, 'z': 0.0, 'visibility': 0.3},  # 17 (left wrist) - low visibility
            {'x': 0.38, 'y': 0.49, 'z': 0.0, 'visibility': 0.92},  # 18 (right wrist)
            {'x': 0.31, 'y': 0.52, 'z': 0.0, 'visibility': 0.2},  # 19 (left index) - low visibility
            {'x': 0.39, 'y': 0.53, 'z': 0.0, 'visibility': 0.88},  # 20 (right index)
        ]
        
        left_pos, right_pos = extract_hand_positions(landmarks)
        
        # Left hand should be None due to low visibility
        self.assertIsNone(left_pos)
        # Right hand should be extracted
        self.assertIsNotNone(right_pos)
    
    def test_extract_with_insufficient_landmarks(self):
        """Test extraction with insufficient landmarks"""
        landmarks = [
            {'x': 0.1, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},  # 0
            # ... insufficient landmarks ...
        ]
        
        left_pos, right_pos = extract_hand_positions(landmarks)
        
        # Both should be None
        self.assertIsNone(left_pos)
        self.assertIsNone(right_pos)
```

### 4. WebSocket Client Tests

#### Test Cases
```python
# test_websocket_clients.py
import asyncio
import unittest
import websockets
from unittest.mock import Mock, patch, AsyncMock
from websocket_pose_touch_detector import InputWebSocketClient, OutputWebSocketClient

class TestWebSocketClients(unittest.TestCase):
    def setUp(self):
        self.message_handler = Mock()
        self.input_client = InputWebSocketClient(
            "ws://localhost:8001/test",
            self.message_handler,
            reconnect_delay=0.1  # Short delay for testing
        )
        self.output_client = OutputWebSocketClient(
            "ws://localhost:8002/test",
            reconnect_delay=0.1  # Short delay for testing
        )
    
    @patch('websockets.connect')
    async def test_input_websocket_connection(self, mock_connect):
        """Test input WebSocket connection and message handling"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket
        
        # Mock message
        test_message = '{"landmarks": [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}]}'
        mock_websocket.__aiter__.return_value = [test_message]
        
        # Start client (will stop after one message)
        self.input_client.running = True
        
        # Run for a short time
        task = asyncio.create_task(self.input_client.connect())
        await asyncio.sleep(0.1)
        self.input_client.running = False
        
        # Verify message was handled
        self.message_handler.assert_called_once()
        args = self.message_handler.call_args[0][0]
        self.assertIn('landmarks', args)
    
    @patch('websockets.connect')
    async def test_output_websocket_message_sending(self, mock_connect):
        """Test output WebSocket message sending"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket
        
        # Start client
        self.output_client.running = True
        task = asyncio.create_task(self.output_client.connect())
        
        # Send a message
        test_message = {'type': 'test', 'data': 'hello'}
        await self.output_client.send_message(test_message)
        
        # Wait a bit for processing
        await asyncio.sleep(0.1)
        
        # Stop client
        self.output_client.running = False
        
        # Verify message was sent
        mock_websocket.send.assert_called()
        sent_message = mock_websocket.send.call_args[0][0]
        self.assertIn('test', sent_message)
        
        # Clean up
        task.cancel()
```

## Integration Tests

### 1. End-to-End WebSocket Flow Test

#### Test Setup
```python
# test_integration.py
import asyncio
import json
import time
import unittest
from unittest.mock import Mock, patch
import websockets
from websocket_pose_touch_detector import WebSocketPoseTouchDetector

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_wall_id = 1
        self.input_url = "ws://localhost:8001/test_input"
        self.output_url = "ws://localhost:8002/test_output"
        
        # Mock wall and calibration data
        self.mock_wall = Mock()
        self.mock_wall.name = "Test Wall"
        self.mock_wall.svg_file.name = "test_wall.svg"
        
        self.mock_calibration = Mock()
        self.mock_calibration.name = "Test Calibration"
        self.mock_calibration.perspective_transform = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
    
    @patch('climber.models.Wall.objects.get')
    @patch('climber.models.WallCalibration.objects.filter')
    @patch('climber.svg_utils.SVGParser')
    async def test_end_to_end_flow(self, mock_svg_parser, mock_calibration_filter, mock_wall_get):
        """Test complete end-to-end flow"""
        # Setup mocks
        mock_wall_get.return_value = self.mock_wall
        mock_calibration_filter.return_value.latest.return_value = self.mock_calibration
        
        # Mock SVG parser
        mock_parser_instance = Mock()
        mock_parser_instance.paths = {
            'hold_1': {'d': 'M 100 100 L 150 150 L 200 100 Z'},
            'hold_2': {'d': 'M 300 300 L 350 350 L 400 300 Z'}
        }
        mock_parser_instance.point_in_path.return_value = True
        mock_svg_parser.return_value = mock_parser_instance
        
        # Create detector
        detector = WebSocketPoseTouchDetector(
            wall_id=self.test_wall_id,
            input_websocket_url=self.input_url,
            output_websocket_url=self.output_url,
            touch_duration=0.5,  # Short duration for testing
            debug=True
        )
        
        # Setup detector
        setup_success = await detector.setup()
        self.assertTrue(setup_success)
        
        # Simulate pose data
        pose_data = {
            'landmarks': [
                {'x': 0.1, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},  # 0
                # ... other landmarks ...
                {'x': 0.3, 'y': 0.4, 'z': 0.0, 'visibility': 0.8},  # 15 (left elbow)
                {'x': 0.35, 'y': 0.45, 'z': 0.0, 'visibility': 0.9},  # 16 (right elbow)
                {'x': 0.32, 'y': 0.48, 'z': 0.0, 'visibility': 0.95},  # 17 (left wrist)
                {'x': 0.38, 'y': 0.49, 'z': 0.0, 'visibility': 0.92},  # 18 (right wrist)
                {'x': 0.31, 'y': 0.52, 'z': 0.0, 'visibility': 0.9},  # 19 (left index)
                {'x': 0.39, 'y': 0.53, 'z': 0.0, 'visibility': 0.88},  # 20 (right index)
            ],
            'timestamp': time.time()
        }
        
        # Handle pose data
        await detector.handle_pose_data(pose_data)
        
        # Wait for touch duration
        await asyncio.sleep(0.6)
        
        # Send another pose data to trigger event
        await detector.handle_pose_data(pose_data)
        
        # Verify touch tracking
        self.assertGreater(len(detector.touch_tracker.touch_start_times), 0)
```

### 2. Mock WebSocket Server for Testing

#### Test Server Implementation
```python
# test_websocket_server.py
import asyncio
import json
import websockets

class MockPoseWebSocketServer:
    def __init__(self, port=8001):
        self.port = port
        self.clients = set()
        self.running = False
    
    async def register(self, websocket):
        """Register a new client"""
        self.clients.add(websocket)
    
    async def unregister(self, websocket):
        """Unregister a client"""
        self.clients.remove(websocket)
    
    async def broadcast_pose_data(self):
        """Broadcast mock pose data to all clients"""
        while self.running:
            # Generate mock pose data
            pose_data = {
                'landmarks': [
                    {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9},
                    # ... more landmarks ...
                ],
                'timestamp': time.time()
            }
            
            message = json.dumps(pose_data)
            
            # Send to all clients
            if self.clients:
                await asyncio.gather(
                    *[client.send(message) for client in self.clients],
                    return_exceptions=True
                )
            
            await asyncio.sleep(0.033)  # ~30 FPS
    
    async def handle_client(self, websocket, path):
        """Handle a new client connection"""
        await self.register(websocket)
        try:
            async for message in websocket:
                # Echo back any received messages
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    async def start(self):
        """Start the WebSocket server"""
        self.running = True
        
        # Start broadcasting task
        broadcast_task = asyncio.create_task(self.broadcast_pose_data())
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.port
        )
        
        return server, broadcast_task
    
    async def stop(self):
        """Stop the WebSocket server"""
        self.running = False

class MockEventWebSocketServer:
    def __init__(self, port=8002):
        self.port = port
        self.received_events = []
        self.clients = set()
        self.running = False
    
    async def handle_client(self, websocket, path):
        """Handle a new client connection"""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                # Store received events
                try:
                    event = json.loads(message)
                    self.received_events.append(event)
                    print(f"Received event: {event}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
    
    async def start(self):
        """Start the WebSocket server"""
        self.running = True
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.port
        )
        
        return server
    
    async def stop(self):
        """Stop the WebSocket server"""
        self.running = False
```

## Performance Tests

### 1. High-Frequency Data Test

#### Test Case
```python
# test_performance.py
import asyncio
import time
import unittest
from unittest.mock import Mock, patch
from websocket_pose_touch_detector import WebSocketPoseTouchDetector

class TestPerformance(unittest.TestCase):
    async def test_high_frequency_pose_data(self):
        """Test processing high-frequency pose data (30+ FPS)"""
        # Setup detector with mocks
        detector = WebSocketPoseTouchDetector(
            wall_id=1,
            input_websocket_url="ws://localhost:8001/test",
            output_websocket_url="ws://localhost:8002/test",
            touch_duration=0.1
        )
        
        # Mock setup
        with patch.object(detector, 'setup', return_value=True):
            with patch.object(detector.output_client, 'send_message'):
                # Generate high-frequency pose data
                start_time = time.time()
                frame_count = 0
                
                for i in range(300):  # 10 seconds at 30 FPS
                    pose_data = {
                        'landmarks': [
                            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9},
                            # ... more landmarks ...
                        ],
                        'timestamp': start_time + (i * 0.033)
                    }
                    
                    await detector.handle_pose_data(pose_data)
                    frame_count += 1
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Verify performance
                self.assertLess(duration, 12.0)  # Should complete in reasonable time
                self.assertEqual(frame_count, 300)
                
                # Calculate processing rate
                fps = frame_count / duration
                self.assertGreater(fps, 25.0)  # Should handle at least 25 FPS
```

### 2. Memory Usage Test

#### Test Case
```python
import psutil
import os

async def test_memory_usage(self):
    """Test memory usage over extended period"""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Setup detector
    detector = WebSocketPoseTouchDetector(
        wall_id=1,
        input_websocket_url="ws://localhost:8001/test",
        output_websocket_url="ws://localhost:8002/test",
        touch_duration=1.0
    )
    
    # Mock setup
    with patch.object(detector, 'setup', return_value=True):
        with patch.object(detector.output_client, 'send_message'):
            # Run for extended period
            for i in range(3600):  # 1 hour at 1 FPS
                pose_data = {
                    'landmarks': [
                        {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9},
                        # ... more landmarks ...
                    ],
                    'timestamp': time.time()
                }
                
                await detector.handle_pose_data(pose_data)
                
                # Check memory every 10 minutes
                if i % 600 == 0:
                    current_memory = process.memory_info().rss
                    memory_increase = current_memory - initial_memory
                    
                    # Memory increase should be reasonable (< 100MB)
                    self.assertLess(memory_increase, 100 * 1024 * 1024)
```

## Test Execution

### Running Tests

#### Unit Tests
```bash
# Run all unit tests
python manage.py test climber.tests_websocket_pose_touch_detector

# Run specific test class
python manage.py test climber.tests_websocket_pose_touch_detector.TestCoordinateTransformation

# Run with coverage
coverage run --source='.' manage.py test climber.tests_websocket_pose_touch_detector
coverage report
```

#### Integration Tests
```bash
# Run integration tests
python manage.py test climber.tests_websocket_pose_touch_detector_integration

# Run with mock servers
python -m unittest test_integration.py -v
```

#### Performance Tests
```bash
# Run performance tests
python manage.py test climber.tests_websocket_pose_touch_detector_performance

# Run with profiling
python -m cProfile -o profile.stats manage.py test climber.tests_websocket_pose_touch_detector_performance
```

### Continuous Integration

#### GitHub Actions Configuration
```yaml
# .github/workflows/test_websocket_pose_touch_detector.yml
name: WebSocket Pose Touch Detector Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install coverage pytest pytest-asyncio
    
    - name: Run unit tests
      run: |
        coverage run --source='.' manage.py test climber.tests_websocket_pose_touch_detector
        coverage xml
    
    - name: Run integration tests
      run: |
        python manage.py test climber.tests_websocket_pose_touch_detector_integration
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v1
      with:
        file: ./coverage.xml
```

## Test Data Management

### Sample Pose Data Files

#### Format
```json
{
  "landmarks": [
    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9},
    {"x": 0.51, "y": 0.51, "z": 0.01, "visibility": 0.85},
    // ... more landmarks
  ],
  "timestamp": 1234567890.123
}
```

#### Test Scenarios
1. **Normal climbing sequence**: Hand movements touching different holds
2. **No hands visible**: Low visibility landmarks
3. **Rapid hand movements**: Quick transitions between holds
4. **Simultaneous touches**: Both hands touching holds at same time
5. **Edge cases**: Hands at screen edges, partial visibility

### Mock Wall Data

#### Database Setup
```python
# Create test wall and calibration in database
test_wall = Wall.objects.create(
    name="Test Wall",
    venue=test_venue,
    svg_file="test_wall.svg",
    width_mm=2500.0,
    height_mm=3330.0
)

test_calibration = WallCalibration.objects.create(
    wall=test_wall,
    name="Test Calibration",
    calibration_type="manual_points",
    perspective_transform=[
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ],
    is_active=True
)
```

## Test Reporting

### Coverage Requirements
- Unit tests: > 90% code coverage
- Integration tests: > 80% code coverage
- Performance tests: Document baseline metrics

### Test Metrics
1. **Functionality**: Correct touch detection and event sending
2. **Performance**: Processing rate and memory usage
3. **Reliability**: Reconnection behavior and error handling
4. **Accuracy**: Coordinate transformation precision

### Bug Tracking
- Document any test failures with reproduction steps
- Track performance regressions over time
- Monitor integration test stability