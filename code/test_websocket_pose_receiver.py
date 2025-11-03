#!/usr/bin/env python3
"""
Test script for the websocket_pose_receiver management command.

This script generates fake MediaPipe pose data and sends it to a WebSocket
to test the pose receiver command.
"""

import asyncio
import json
import time
import websockets
import argparse
from typing import List, Dict


def generate_fake_pose_landmarks(num_landmarks: int = 33) -> List[Dict]:
    """Generate fake MediaPipe pose landmarks"""
    landmarks = []
    
    # MediaPipe pose landmark indices (simplified)
    landmark_names = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
        "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_pinky", "right_pinky", "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
        "left_heel", "right_heel", "left_foot_index", "right_foot_index"
    ]
    
    for i in range(min(num_landmarks, len(landmark_names))):
        # Generate realistic pose coordinates
        # x: 0.0 to 1.0 (horizontal position)
        # y: 0.0 to 1.0 (vertical position)  
        # z: -1.0 to 1.0 (depth)
        # visibility: 0.0 to 1.0 (confidence)
        
        # Create a simple standing pose with some movement
        if i in [0]:  # nose
            x, y = 0.5, 0.15
        elif i in [11, 12]:  # shoulders
            x = 0.4 if i == 11 else 0.6
            y = 0.25
        elif i in [13, 14]:  # elbows
            x = 0.35 if i == 13 else 0.65
            y = 0.4
        elif i in [15, 16]:  # wrists
            x = 0.3 if i == 15 else 0.7
            y = 0.55
        elif i in [23, 24]:  # hips
            x = 0.45 if i == 23 else 0.55
            y = 0.5
        elif i in [25, 26]:  # knees
            x = 0.43 if i == 25 else 0.57
            y = 0.7
        elif i in [27, 28]:  # ankles
            x = 0.42 if i == 27 else 0.58
            y = 0.85
        else:
            # Default positions for other landmarks
            x = 0.5 + (i % 3 - 1) * 0.1
            y = 0.2 + (i // 3) * 0.05
        
        # Add some movement over time
        time_offset = time.time() * 0.5
        x += 0.02 * (time_offset % (2 * 3.14159))
        y += 0.01 * (time_offset % (2 * 3.14159))
        
        landmarks.append({
            'x': max(0.0, min(1.0, x)),
            'y': max(0.0, min(1.0, y)),
            'z': 0.0,
            'visibility': 0.9
        })
    
    return landmarks


async def send_fake_pose_data(websocket_url: str, duration: int = 30, fps: int = 10):
    """Send fake pose data to WebSocket"""
    
    pose_message = {
        'type': 'pose',
        'timestamp': int(time.time() * 1000),
        'width': 1280,
        'height': 720,
        'landmarks': generate_fake_pose_landmarks()
    }
    
    try:
        print(f"Connecting to WebSocket: {websocket_url}")
        async with websockets.connect(websocket_url) as websocket:
            print("Connected to WebSocket successfully")
            
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < duration:
                # Update timestamp and landmarks
                pose_message['timestamp'] = int(time.time() * 1000)
                pose_message['landmarks'] = generate_fake_pose_landmarks()
                
                # Send message
                message_str = json.dumps(pose_message)
                await websocket.send(message_str)
                
                frame_count += 1
                print(f"Sent frame {frame_count} at {fps} FPS")
                
                # Wait for next frame
                await asyncio.sleep(1.0 / fps)
            
            print(f"Sent {frame_count} frames over {duration} seconds")
            
    except Exception as e:
        print(f"Error sending pose data: {e}")


async def test_pose_receiver(input_url: str, output_url: str, duration: int = 30):
    """Test the pose receiver by sending data and optionally receiving output"""
    
    # Start sending fake pose data
    sender_task = asyncio.create_task(
        send_fake_pose_data(input_url, duration, fps=10)
    )
    
    # If output URL is provided, listen for transformed data
    if output_url:
        async def listen_for_output():
            try:
                print(f"Listening for transformed data on: {output_url}")
                async with websockets.connect(output_url) as websocket:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        print(f"Received transformed pose: {data.get('type')} with {len(data.get('landmarks', []))} landmarks")
            except Exception as e:
                print(f"Error receiving transformed data: {e}")
        
        listener_task = asyncio.create_task(listen_for_output())
        
        # Wait for both tasks
        await asyncio.gather(sender_task, listener_task)
    else:
        # Just wait for sender to finish
        await sender_task


def main():
    parser = argparse.ArgumentParser(description='Test websocket_pose_receiver management command')
    parser.add_argument(
        '--input-url',
        type=str,
        default='ws://localhost:8080',
        help='WebSocket URL to send fake pose data to'
    )
    parser.add_argument(
        '--output-url',
        type=str,
        help='WebSocket URL to listen for transformed data (optional)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=30,
        help='Duration in seconds to send test data'
    )
    
    args = parser.parse_args()
    
    print(f"Testing pose receiver with:")
    print(f"  Input URL: {args.input_url}")
    print(f"  Output URL: {args.output_url or 'None'}")
    print(f"  Duration: {args.duration} seconds")
    print()
    
    # Run the test
    asyncio.run(test_pose_receiver(args.input_url, args.output_url, args.duration))


if __name__ == '__main__':
    main()