#!/usr/bin/env python3
"""
Simple test script to send fake MediaPipe pose data to WebSocket for testing the pose skeleton visualization.
"""

import asyncio
import websockets
import json
import time
import math
import random

async def send_fake_pose_data(uri="ws://localhost:8000/ws/pose/"):
    """Connect to WebSocket and send fake pose data."""
    
    # Generate fake pose landmarks (33 landmarks for MediaPipe Pose)
    def generate_fake_landmarks(frame_num):
        landmarks = []
        
        # Create a simple walking animation
        t = frame_num * 0.1
        
        for i in range(33):
            # Basic pose structure with some animation
            if i == 0:  # Nose
                x, y, z = 0.5, 0.1 + 0.02 * math.sin(t), 0.0
            elif i in [1, 2, 3, 4, 5, 6, 7, 8]:  # Face/ears
                x = 0.5 + 0.05 * (1 if i % 2 == 0 else -1)
                y = 0.1 + 0.02 * math.sin(t)
                z = 0.0
            elif i in [11, 12]:  # Shoulders
                x = 0.5 + 0.1 * (1 if i == 11 else -1)
                y = 0.3 + 0.02 * math.sin(t)
                z = 0.0
            elif i in [13, 14]:  # Elbows
                x = 0.5 + 0.15 * (1 if i == 13 else -1)
                y = 0.4 + 0.03 * math.sin(t + 0.5)
                z = 0.05
            elif i in [15, 16]:  # Wrists
                x = 0.5 + 0.2 * (1 if i == 15 else -1)
                y = 0.5 + 0.04 * math.sin(t + 1.0)
                z = 0.1
            elif i in [23, 24]:  # Hips
                x = 0.5 + 0.05 * (1 if i == 23 else -1)
                y = 0.6 + 0.02 * math.sin(t)
                z = 0.0
            elif i in [25, 26]:  # Knees
                x = 0.5 + 0.06 * (1 if i == 25 else -1)
                y = 0.75 + 0.05 * math.sin(t + 0.5)
                z = 0.05
            elif i in [27, 28]:  # Ankles
                x = 0.5 + 0.07 * (1 if i == 27 else -1)
                y = 0.9 + 0.06 * math.sin(t + 1.0)
                z = 0.1
            else:  # Other landmarks (fingers, toes, etc.)
                x = 0.5 + random.uniform(-0.1, 0.1)
                y = 0.5 + random.uniform(-0.2, 0.2)
                z = random.uniform(-0.05, 0.05)
            
            landmarks.append({
                'x': max(0, min(1, x)),  # Clamp to [0, 1]
                'y': max(0, min(1, y)),  # Clamp to [0, 1]
                'z': z,
                'visibility': 0.9 if i < 25 else 0.7  # Higher visibility for main body
            })
        
        return landmarks
    
    try:
        print(f"Connecting to WebSocket at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected! Sending fake pose data...")
            
            frame_num = 0
            while True:
                landmarks = generate_fake_landmarks(frame_num)
                
                message = {
                    'landmarks': landmarks,
                    'frame_number': frame_num,
                    'timestamp': time.time()
                }
                
                await websocket.send(json.dumps(message))
                print(f"Sent frame {frame_num} with {len(landmarks)} landmarks")
                
                frame_num += 1
                await asyncio.sleep(0.033)  # ~30 FPS
                
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the Django server is running and the WebSocket endpoint is accessible.")

if __name__ == "__main__":
    # You can pass a custom WebSocket URI as an argument
    import sys
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws/pose/"
    
    try:
        asyncio.run(send_fake_pose_data(uri))
    except KeyboardInterrupt:
        print("\nTest stopped by user.")