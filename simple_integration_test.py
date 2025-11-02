#!/usr/bin/env python3
"""
Simple integration test for WebSocket pose touch detector command
"""

import asyncio
import json
import time
import websockets
import sys
import os

# Add the code directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()


async def simple_pose_server():
    """Simple WebSocket server that sends pose data"""
    async def handler(websocket, path):
        print("Client connected to pose server")
        try:
            for i in range(10):  # Send 10 frames
                pose_data = {
                    'landmarks': [
                        # Head and body landmarks (simplified)
                        {'x': 0.5, 'y': 0.1, 'z': 0.0, 'visibility': 0.9},
                        {'x': 0.5, 'y': 0.2, 'z': 0.0, 'visibility': 0.9},
                        {'x': 0.5, 'y': 0.3, 'z': 0.0, 'visibility': 0.9},
                        # Left arm
                        {'x': 0.3, 'y': 0.35, 'z': 0.0, 'visibility': 0.8},  # 15 left elbow
                        {'x': 0.25, 'y': 0.4, 'z': 0.0, 'visibility': 0.9},  # 17 left wrist
                        {'x': 0.23, 'y': 0.45, 'z': 0.0, 'visibility': 0.9},  # 19 left index
                        # Right arm
                        {'x': 0.6, 'y': 0.35, 'z': 0.0, 'visibility': 0.8},  # 16 right elbow
                        {'x': 0.65, 'y': 0.4, 'z': 0.0, 'visibility': 0.9},  # 18 right wrist
                        {'x': 0.67, 'y': 0.45, 'z': 0.0, 'visibility': 0.9},  # 20 right index
                    ],
                    'timestamp': time.time(),
                    'frame_number': i
                }
                
                message = json.dumps(pose_data)
                await websocket.send(message)
                print(f"Sent pose data frame {i}")
                await asyncio.sleep(0.5)  # 2 FPS for testing
            
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected from pose server")
    
    server = await websockets.serve(handler, "localhost", 8001)
    print("Simple pose WebSocket server started on ws://localhost:8001")
    return server


async def simple_event_server():
    """Simple WebSocket server that receives hold touch events"""
    events_received = []
    
    async def handler(websocket, path):
        print("Client connected to event server")
        try:
            async for message in websocket:
                try:
                    event = json.loads(message)
                    events_received.append(event)
                    print(f"Received event: {event}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected from event server")
    
    server = await websockets.serve(handler, "localhost", 8002)
    print("Simple event WebSocket server started on ws://localhost:8002")
    return server, events_received


async def run_integration_test():
    """Run integration test with real WebSocket servers"""
    print("Starting integration test...")
    
    # Start servers
    pose_server = await simple_pose_server()
    event_server, events_received = await simple_event_server()
    
    # Wait a moment for servers to start
    await asyncio.sleep(1)
    
    try:
        # Import and run the command
        from climber.management.commands.websocket_pose_touch_detector import WebSocketPoseTouchDetector
        from unittest.mock import Mock
        import numpy as np
        
        # Create detector
        detector = WebSocketPoseTouchDetector(
            wall_id=1,  # This should exist in the database
            input_websocket_url="ws://localhost:8001",
            output_websocket_url="ws://localhost:8002",
            touch_duration=1.0,  # 1 second for testing
            debug=True
        )
        
        # Mock the setup to avoid SVG file dependency
        detector.wall = Mock()
        detector.wall.name = "Test Wall"
        
        detector.calibration = Mock()
        detector.calibration.name = "Test Calibration"
        detector.calibration.perspective_transform = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        
        # Mock SVG parser with simple holds
        detector.svg_parser = Mock()
        detector.svg_parser.paths = {
            'hold_1': {'d': 'M 100 100 L 150 150 L 200 100 Z'},
            'hold_2': {'d': 'M 300 300 L 350 350 L 400 300 Z'}
        }
        
        # Mock point_in_path to return True for specific coordinates
        def mock_point_in_path(point, path_d):
            # Simulate hold intersection based on coordinates
            x, y = point
            # Hold 1 is in the left area
            if x < 0.5 and y > 0.35:
                return True
            # Hold 2 is in the right area
            if x > 0.5 and y > 0.35:
                return True
            return False
        
        detector.svg_parser.point_in_path = mock_point_in_path
        
        # Mock calibration utils
        from climber.calibration.calibration_utils import CalibrationUtils
        detector.calibration_utils = CalibrationUtils()
        detector.transform_matrix = np.array(detector.calibration.perspective_transform, dtype=np.float32)
        
        # Run detector for a short time
        detector_task = asyncio.create_task(detector.run())
        
        # Let it run for a few seconds to process pose data
        await asyncio.sleep(6)
        
        # Stop detector
        detector.running = False
        await detector.cleanup()
        
        # Check results
        print(f"\nIntegration test results:")
        print(f"Events received: {len(events_received)}")
        for event in events_received:
            print(f"  - {event}")
        
        # Verify we received at least one event
        if len(events_received) > 0:
            print("\n✅ Integration test PASSED - Hold touch events were received!")
        else:
            print("\n❌ Integration test FAILED - No hold touch events received!")
        
    except Exception as e:
        print(f"Error during integration test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up servers
        print("\nShutting down servers...")
        pose_server.close()
        event_server.close()
        await asyncio.sleep(1)  # Give servers time to close


if __name__ == "__main__":
    asyncio.run(run_integration_test())