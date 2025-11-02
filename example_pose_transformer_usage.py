#!/usr/bin/env python3
"""
Example script demonstrating how to use the WebSocket pose transformer command.
This script shows how to send pose data to the transformer and receive transformed coordinates.
"""

import asyncio
import json
import time
import websockets
import numpy as np
from typing import Dict, Any, List


class PoseDataSender:
    """Example client that sends MediaPipe pose data to the transformer"""
    
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
    
    async def connect(self):
        """Connect to the transformer input WebSocket"""
        self.websocket = await websockets.connect(self.websocket_url)
        print(f"Connected to transformer at {self.websocket_url}")
    
    async def send_pose_data(self, pose_data: Dict[str, Any]):
        """Send pose data to the transformer"""
        if self.websocket:
            await self.websocket.send(json.dumps(pose_data))
            print(f"Sent pose data with {len(pose_data['landmarks'])} landmarks")
    
    def create_sample_pose_data(self, frame_id: int) -> Dict[str, Any]:
        """Create sample MediaPipe pose data"""
        # Create 33 MediaPipe pose landmarks
        landmarks = []
        
        # Generate some realistic pose landmarks with movement
        for i in range(33):
            # Create different movement patterns for different body parts
            if i in [15, 16, 17, 18, 19, 20, 21, 22]:  # Hands and wrists
                # Hands move more
                x = 0.5 + 0.3 * np.sin(frame_id * 0.1 + i)
                y = 0.3 + 0.2 * np.cos(frame_id * 0.1 + i)
                visibility = 0.9
            elif i in [11, 12, 13, 14]:  # Arms
                # Arms move moderately
                x = 0.5 + 0.2 * np.sin(frame_id * 0.05 + i)
                y = 0.2 + 0.1 * np.cos(frame_id * 0.05 + i)
                visibility = 0.8
            else:  # Body and head
                # Body moves less
                x = 0.5 + 0.1 * np.sin(frame_id * 0.02 + i)
                y = 0.3 + 0.05 * np.cos(frame_id * 0.02 + i)
                visibility = 0.7
            
            landmarks.append({
                'x': x,
                'y': y,
                'z': 0.0,  # Keep z at 0 for simplicity
                'visibility': visibility
            })
        
        return {
            'landmarks': landmarks,
            'timestamp': time.time(),
            'frame_id': frame_id
        }
    
    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()


class TransformedDataReceiver:
    """Example client that receives transformed pose data from the transformer"""
    
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
        self.received_data = []
    
    async def connect(self):
        """Connect to the transformer output WebSocket"""
        self.websocket = await websockets.connect(self.websocket_url)
        print(f"Connected to output at {self.websocket_url}")
    
    async def listen_for_data(self):
        """Listen for transformed pose data"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.received_data.append(data)
                
                print(f"\nReceived transformed pose data:")
                print(f"  Type: {data.get('type')}")
                print(f"  Wall ID: {data.get('wall_id')}")
                print(f"  Timestamp: {data.get('timestamp')}")
                print(f"  Original landmarks: {data.get('original_landmark_count')}")
                print(f"  Transformed landmarks: {data.get('transformed_landmark_count')}")
                
                # Show a few sample transformed landmarks
                landmarks = data.get('landmarks', [])
                if landmarks:
                    print(f"  Sample transformed landmarks:")
                    for i, landmark in enumerate(landmarks[:3]):  # Show first 3
                        print(f"    {i}: ({landmark['x']:.1f}, {landmark['y']:.1f})")
                
        except websockets.exceptions.ConnectionClosed:
            print("Output WebSocket connection closed")
    
    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()


async def run_example():
    """Run the example demonstration"""
    print("WebSocket Pose Transformer Example")
    print("=" * 50)
    print("\nThis example demonstrates:")
    print("1. Sending MediaPipe pose data to the transformer")
    print("2. Receiving transformed coordinates")
    print("3. Comparing original vs transformed data")
    print("\nMake sure the transformer is running:")
    print("uv run python manage.py websocket_pose_transformer \\")
    print("    --wall-id 1 \\")
    print("    --input-websocket-url ws://localhost:8765 \\")
    print("    --output-websocket-url ws://localhost:8766")
    print("\nPress Enter to continue...")
    input()
    
    # Configuration
    input_url = "ws://localhost:8765"
    output_url = "ws://localhost:8766"
    
    # Create clients
    sender = PoseDataSender(input_url)
    receiver = TransformedDataReceiver(output_url)
    
    try:
        # Connect to WebSockets
        await sender.connect()
        await receiver.connect()
        
        # Start listening for transformed data
        listen_task = asyncio.create_task(receiver.listen_for_data())
        
        # Send pose data for demonstration
        print("\nSending pose data...")
        for frame_id in range(20):  # Send 20 frames
            pose_data = sender.create_sample_pose_data(frame_id)
            await sender.send_pose_data(pose_data)
            await asyncio.sleep(0.5)  # Wait 0.5 seconds between frames
        
        # Wait a bit for any remaining messages
        await asyncio.sleep(2)
        
        # Stop listening
        listen_task.cancel()
        
        # Print summary
        print(f"\nExample completed!")
        print(f"Sent 20 pose frames")
        print(f"Received {len(receiver.received_data)} transformed pose messages")
        
        if receiver.received_data:
            # Calculate average transformation statistics
            total_original = sum(msg.get('original_landmark_count', 0) for msg in receiver.received_data)
            total_transformed = sum(msg.get('transformed_landmark_count', 0) for msg in receiver.received_data)
            
            print(f"\nTransformation Statistics:")
            print(f"  Average original landmarks: {total_original / len(receiver.received_data):.1f}")
            print(f"  Average transformed landmarks: {total_transformed / len(receiver.received_data):.1f}")
            print(f"  Transformation rate: {(total_transformed / total_original * 100):.1f}%")
        
    except Exception as e:
        print(f"Example error: {e}")
        print("\nMake sure the transformer is running with the correct WebSocket URLs")
    finally:
        # Clean up
        await sender.close()
        await receiver.close()


if __name__ == "__main__":
    asyncio.run(run_example())