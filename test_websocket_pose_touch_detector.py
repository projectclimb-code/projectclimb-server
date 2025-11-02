#!/usr/bin/env python3
"""
Test script for WebSocket pose touch detector command
"""

import asyncio
import json
import time
import math
import websockets
from unittest.mock import Mock, patch
import sys
import os

# Add the code directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

from climber.management.commands.websocket_pose_touch_detector import (
    WebSocketPoseTouchDetector, 
    TouchTracker, 
    validate_pose_data,
    extract_hand_positions
)


class MockPoseWebSocketServer:
    """Mock WebSocket server that sends pose data"""
    
    def __init__(self, port=8001):
        self.port = port
        self.clients = set()
        self.running = False
    
    async def register(self, websocket):
        """Register a new client"""
        self.clients.add(websocket)
        print(f"Client connected to pose server")
    
    async def unregister(self, websocket):
        """Unregister a client"""
        self.clients.remove(websocket)
        print(f"Client disconnected from pose server")
    
    async def broadcast_pose_data(self):
        """Broadcast mock pose data to all clients"""
        frame_count = 0
        while self.running:
            # Generate mock pose data with hand movements
            t = time.time()
            
            # Simulate hand movement in a pattern
            left_x = 0.3 + 0.1 * (0.5 + 0.5 * time.sin(t * 0.5))
            left_y = 0.4 + 0.1 * (0.5 + 0.5 * time.cos(t * 0.5))
            
            right_x = 0.6 + 0.1 * (0.5 + 0.5 * time.cos(t * 0.7))
            right_y = 0.4 + 0.1 * (0.5 + 0.5 * time.sin(t * 0.7))
            
            pose_data = {
                'landmarks': [
                    # Head and body landmarks (simplified)
                    {'x': 0.5, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},
                    {'x': 0.5, 'y': 0.2, 'z': 0.0, 'visibility': 0.9},
                    {'x': 0.5, 'y': 0.3, 'z': 0.0, 'visibility': 0.9},
                    # Left arm
                    {'x': 0.3, 'y': 0.35, 'z': 0.0, 'visibility': 0.8},  # 15 left elbow
                    {'x': left_x, 'y': left_y, 'z': 0.0, 'visibility': 0.9},  # 17 left wrist
                    {'x': left_x + 0.02, 'y': left_y + 0.05, 'z': 0.0, 'visibility': 0.9},  # 19 left index
                    # Right arm
                    {'x': 0.6, 'y': 0.35, 'z': 0.0, 'visibility': 0.8},  # 16 right elbow
                    {'x': right_x, 'y': right_y, 'z': 0.0, 'visibility': 0.9},  # 18 right wrist
                    {'x': right_x + 0.02, 'y': right_y + 0.05, 'z': 0.0, 'visibility': 0.9},  # 20 right index
                ],
                'timestamp': t,
                'frame_number': frame_count
            }
            
            message = json.dumps(pose_data)
            
            # Send to all clients
            if self.clients:
                await asyncio.gather(
                    *[client.send(message) for client in self.clients],
                    return_exceptions=True
                )
            
            frame_count += 1
            await asyncio.sleep(0.1)  # 10 FPS for testing
    
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
        """Start WebSocket server"""
        self.running = True
        
        # Start broadcasting task
        broadcast_task = asyncio.create_task(self.broadcast_pose_data())
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.port
        )
        
        print(f"Mock pose WebSocket server started on ws://localhost:{self.port}")
        return server, broadcast_task
    
    async def stop(self):
        """Stop WebSocket server"""
        self.running = False


class MockEventWebSocketServer:
    """Mock WebSocket server that receives hold touch events"""
    
    def __init__(self, port=8002):
        self.port = port
        self.received_events = []
        self.clients = set()
        self.running = False
    
    async def handle_client(self, websocket, path):
        """Handle a new client connection"""
        self.clients.add(websocket)
        print(f"Client connected to event server")
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
            print(f"Client disconnected from event server")
    
    async def start(self):
        """Start WebSocket server"""
        self.running = True
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.port
        )
        
        print(f"Mock event WebSocket server started on ws://localhost:{self.port}")
        return server
    
    async def stop(self):
        """Stop WebSocket server"""
        self.running = False


async def test_components():
    """Test individual components"""
    print("Testing individual components...")
    
    # Test pose data validation
    valid_pose = {
        'landmarks': [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}
        ]
    }
    
    is_valid, msg = validate_pose_data(valid_pose)
    print(f"Pose validation: {is_valid}, {msg}")
    
    # Test hand position extraction
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
    print(f"Left hand position: {left_pos}")
    print(f"Right hand position: {right_pos}")
    
    # Test touch tracker
    tracker = TouchTracker(touch_duration=0.5)
    timestamp = time.time()
    
    tracker.update_touches(['hold_1'], timestamp)
    ready_holds = tracker.get_ready_holds(timestamp)
    print(f"Ready holds immediately: {ready_holds}")
    
    # Wait and check again
    await asyncio.sleep(0.6)
    ready_holds = tracker.get_ready_holds(timestamp + 0.6)
    print(f"Ready holds after 0.6s: {ready_holds}")


async def test_end_to_end():
    """Test end-to-end WebSocket flow"""
    print("Testing end-to-end WebSocket flow...")
    
    # Start mock servers
    pose_server = MockPoseWebSocketServer(8003)  # Use different port to avoid conflict
    event_server = MockEventWebSocketServer(8004)  # Use different port to avoid conflict
    
    pose_server_task, pose_broadcast_task = await pose_server.start()
    event_server_task = await event_server.start()
    
    # Wait a moment for servers to start
    await asyncio.sleep(1)
    
    try:
        # Create and configure detector with mocked components
        detector = WebSocketPoseTouchDetector(
            wall_id=1,  # This should exist in test database
            input_websocket_url="ws://localhost:8001",
            output_websocket_url="ws://localhost:8002",
            touch_duration=0.5,  # Short duration for testing
            debug=True
        )
        
        # Mock the setup to avoid database dependency
        detector.wall = Mock()
        detector.wall.name = "Test Wall"
        detector.wall.svg_file.name = "test_wall.svg"
        
        detector.calibration = Mock()
        detector.calibration.name = "Test Calibration"
        detector.calibration.perspective_transform = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        
        # Mock SVG parser
        detector.svg_parser = Mock()
        detector.svg_parser.paths = {
            'hold_1': {'d': 'M 100 100 L 150 150 L 200 100 Z'},
            'hold_2': {'d': 'M 300 300 L 350 350 L 400 300 Z'}
        }
        detector.svg_parser.point_in_path.return_value = True  # Always return True for testing
        
        # Mock calibration utils
        from climber.calibration.calibration_utils import CalibrationUtils
        detector.calibration_utils = CalibrationUtils()
        import numpy as np
        detector.transform_matrix = np.array(detector.calibration.perspective_transform, dtype=np.float32)
        
        # Start detector
        detector_task = asyncio.create_task(detector.run())
        
        # Let it run for a few seconds
        await asyncio.sleep(3)
        
        # Stop detector
        detector.running = False
        await detector.cleanup()
        
        # Check if events were received
        print(f"Events received by mock server: {len(event_server.received_events)}")
        for event in event_server.received_events:
            print(f"  - {event}")
        
    except Exception as e:
        print(f"Error during end-to-end test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop servers
        await pose_server.stop()
        await event_server.stop()
        
        # Cancel server tasks
        pose_broadcast_task.cancel()
        pose_server_task.close()
        event_server_task.close()


async def main():
    """Main test function"""
    print("Starting WebSocket pose touch detector tests...")
    
    # Test individual components
    await test_components()
    
    print("\n" + "="*50 + "\n")
    
    # Test end-to-end flow
    await test_end_to_end()
    
    print("\nTests completed!")


if __name__ == "__main__":
    asyncio.run(main())