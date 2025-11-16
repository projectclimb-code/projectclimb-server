#!/usr/bin/env python3
"""
Test script for the pose visualizer.

This script creates a mock WebSocket server that sends sample session data
to test the pose_visualizer.py script without needing the full Django setup.
"""

import asyncio
import json
import time
import random
import argparse
from typing import List, Dict
import numpy as np

try:
    import websockets
except ImportError:
    print("Error: websockets package not found. Install with: pip install websockets")
    exit(1)


def generate_mock_pose_data(frame_num: int) -> List[Dict]:
    """Generate mock pose data for testing"""
    # Create a simple climbing motion pattern
    t = frame_num * 0.1
    
    # Base positions
    landmarks = []
    
    # Generate 33 MediaPipe pose landmarks
    for i in range(33):
        # Create different movement patterns for different body parts
        if i == 0:  # Nose
            x = 1250 + 50 * np.sin(t)
            y = 500 + 30 * np.cos(t * 0.8)
        elif i in [11, 12]:  # Shoulders
            if i == 11:  # Left shoulder
                x = 1100 + 20 * np.sin(t)
                y = 600 + 10 * np.cos(t)
            else:  # Right shoulder
                x = 1400 + 20 * np.cos(t)
                y = 600 + 10 * np.sin(t)
        elif i in [13, 14]:  # Elbows
            if i == 13:  # Left elbow
                x = 1000 + 100 * np.sin(t * 1.5)
                y = 800 + 50 * np.cos(t * 1.2)
            else:  # Right elbow
                x = 1500 + 100 * np.cos(t * 1.5)
                y = 800 + 50 * np.sin(t * 1.2)
        elif i in [15, 16]:  # Wrists (hands)
            if i == 15:  # Left wrist
                # Climbing motion - reaching for holds
                x = 900 + 200 * np.sin(t * 2)
                y = 1000 + 150 * np.abs(np.sin(t * 1.8))
            else:  # Right wrist
                x = 1600 + 200 * np.cos(t * 2)
                y = 1000 + 150 * np.abs(np.cos(t * 1.8))
        elif i in [23, 24]:  # Hips
            if i == 23:  # Left hip
                x = 1150 + 10 * np.sin(t * 0.5)
                y = 1200
            else:  # Right hip
                x = 1350 + 10 * np.cos(t * 0.5)
                y = 1200
        elif i in [25, 26]:  # Knees
            if i == 25:  # Left knee
                x = 1100 + 20 * np.sin(t * 0.7)
                y = 1600 + 30 * np.sin(t * 1.1)
            else:  # Right knee
                x = 1400 + 20 * np.cos(t * 0.7)
                y = 1600 + 30 * np.cos(t * 1.1)
        elif i in [27, 28]:  # Ankles
            if i == 27:  # Left ankle
                x = 1050 + 30 * np.sin(t * 0.9)
                y = 2000 + 50 * np.sin(t * 1.3)
            else:  # Right ankle
                x = 1450 + 30 * np.cos(t * 0.9)
                y = 2000 + 50 * np.cos(t * 1.3)
        else:
            # Other landmarks with smaller movements
            x = 1250 + random.uniform(-50, 50) + 20 * np.sin(t + i * 0.2)
            y = 1000 + random.uniform(-30, 30) + 15 * np.cos(t + i * 0.3)
        
        # Add some random variation
        x += random.uniform(-5, 5)
        y += random.uniform(-5, 5)
        
        # Create landmark with high visibility
        landmark = {
            'x': x,
            'y': y,
            'z': random.uniform(-0.5, 0.5),  # Small depth variation
            'visibility': random.uniform(0.7, 1.0)
        }
        landmarks.append(landmark)
    
    return landmarks


def generate_mock_session_data(frame_num: int) -> Dict:
    """Generate mock session data for testing"""
    # Simulate hold touches based on hand positions
    pose = generate_mock_pose_data(frame_num)
    
    # Get hand positions
    left_wrist = pose[15] if len(pose) > 15 else None
    right_wrist = pose[16] if len(pose) > 16 else None
    
    # Generate hold status based on proximity to holds
    holds = []
    hold_positions = [
        (1178.6, 340.9, "hold_0"),
        (1782.8, 742.6, "hold_1"),
        (1175.0, 1140.0, "hold_2"),
        (1776.3, 1539.3, "hold_3"),
        (1170.5, 2150.0, "hold_4"),
    ]
    
    for hold_x, hold_y, hold_id in hold_positions:
        status = 'untouched'
        
        # Check if hands are near this hold
        if left_wrist:
            dist = np.sqrt((left_wrist['x'] - hold_x)**2 + (left_wrist['y'] - hold_y)**2)
            if dist < 100:
                status = 'completed'
        
        if right_wrist and status == 'untouched':
            dist = np.sqrt((right_wrist['x'] - hold_x)**2 + (right_wrist['y'] - hold_y)**2)
            if dist < 100:
                status = 'completed'
        
        # Simulate progression - complete holds in order
        if frame_num > 50 and hold_id == "hold_0":
            status = 'completed'
        elif frame_num > 100 and hold_id == "hold_1":
            status = 'completed'
        elif frame_num > 150 and hold_id == "hold_2":
            status = 'completed'
        
        holds.append({
            'id': hold_id,
            'type': 'start' if hold_id == 'hold_0' else 'normal',
            'status': status,
            'time': None if status == 'untouched' else f"2024-01-01T00:00:{frame_num:02d}Z"
        })
    
    return {
        'holds': holds,
        'startTime': '2024-01-01T00:00:00Z',
        'endTime': None,
        'status': 'started'
    }


async def mock_websocket_server(port: int, frame_rate: int = 10):
    """Run a mock WebSocket server that sends pose data"""
    
    async def handler(websocket):
        print(f"Client connected from {websocket.remote_address}")
        
        frame_num = 0
        try:
            while True:
                # Generate session data
                session_data = generate_mock_session_data(frame_num)
                pose_data = generate_mock_pose_data(frame_num)
                
                # Create message
                message = {
                    'session': session_data,
                    'pose': pose_data
                }
                
                # Send message
                await websocket.send(json.dumps(message))
                
                # Print progress
                if frame_num % 50 == 0:
                    print(f"Sent frame {frame_num}")
                
                frame_num += 1
                await asyncio.sleep(1.0 / frame_rate)
                
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected")
        except Exception as e:
            print(f"Error: {e}")
    
    # Start server
    print(f"Starting mock WebSocket server on ws://localhost:{port}")
    server = await websockets.serve(handler, "localhost", port)
    
    print("Server started. Press Ctrl+C to stop.")
    print(f"Connect the visualizer with: python pose_visualizer.py --websocket-url ws://localhost:{port} --wall-svg code/data/wall_bbox.svg")
    
    try:
        await server.wait_closed()
    except KeyboardInterrupt:
        print("\nServer stopped by user")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Mock WebSocket server for testing pose visualizer")
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='Port to run the server on (default: 8765)'
    )
    parser.add_argument(
        '--frame-rate',
        type=int,
        default=10,
        help='Frame rate for sending data (default: 10 FPS)'
    )
    
    args = parser.parse_args()
    
    await mock_websocket_server(args.port, args.frame_rate)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")