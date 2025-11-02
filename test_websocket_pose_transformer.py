#!/usr/bin/env python3
"""
Test script for the WebSocket pose transformer management command.
This script creates a simple test setup to verify the transformer functionality.
"""

import asyncio
import json
import time
import websockets
from typing import Dict, Any

# Test configuration
TEST_CONFIG = {
    'wall_id': 1,  # Adjust this to match your test wall
    'input_websocket_url': 'ws://localhost:8765',  # Test input WebSocket
    'output_websocket_url': 'ws://localhost:8766',  # Test output WebSocket
    'test_duration': 30,  # Test duration in seconds
    'pose_interval': 0.5,  # Interval between pose messages in seconds
}


class TestPoseSender:
    """Test client that sends fake pose data"""
    
    def __init__(self, url: str):
        self.url = url
        self.websocket = None
    
    async def connect(self):
        """Connect to WebSocket"""
        self.websocket = await websockets.connect(self.url)
        print(f"Connected to {self.url}")
    
    async def send_pose_data(self, pose_data: Dict[str, Any]):
        """Send pose data"""
        if self.websocket:
            await self.websocket.send(json.dumps(pose_data))
    
    async def close(self):
        """Close connection"""
        if self.websocket:
            await self.websocket.close()


class TestOutputReceiver:
    """Test client that receives transformed pose data"""
    
    def __init__(self, url: str):
        self.url = url
        self.websocket = None
        self.received_messages = []
    
    async def connect(self):
        """Connect to WebSocket"""
        self.websocket = await websockets.connect(self.url)
        print(f"Connected to {self.url}")
    
    async def listen_for_messages(self):
        """Listen for incoming messages"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.received_messages.append(data)
                print(f"Received transformed pose data: {data}")
        except websockets.exceptions.ConnectionClosed:
            print("Output WebSocket connection closed")
    
    async def close(self):
        """Close connection"""
        if self.websocket:
            await self.websocket.close()


def create_fake_pose_data(frame_id: int) -> Dict[str, Any]:
    """Create fake pose data for testing"""
    # Create 33 MediaPipe pose landmarks with normalized coordinates
    landmarks = []
    for i in range(33):
        # Create some simple movement patterns
        x = 0.5 + 0.3 * (i % 3 - 1) * (0.9 + 0.1 * (frame_id % 10) / 10)
        y = 0.3 + 0.6 * (i / 33) + 0.1 * (frame_id % 20) / 20
        z = 0.0
        visibility = 0.9 if i in [15, 16, 17, 18, 19, 20, 21, 22] else 0.7  # Higher visibility for hands
        
        landmarks.append({
            'x': x,
            'y': y,
            'z': z,
            'visibility': visibility
        })
    
    return {
        'landmarks': landmarks,
        'timestamp': time.time(),
        'frame_id': frame_id
    }


async def run_test():
    """Run the test"""
    print("Starting WebSocket pose transformer test...")
    
    # Create test clients
    pose_sender = TestPoseSender(TEST_CONFIG['input_websocket_url'])
    output_receiver = TestOutputReceiver(TEST_CONFIG['output_websocket_url'])
    
    try:
        # Connect to WebSockets
        await pose_sender.connect()
        await output_receiver.connect()
        
        # Start listening for output messages
        listen_task = asyncio.create_task(output_receiver.listen_for_messages())
        
        # Send pose data for the test duration
        start_time = time.time()
        frame_id = 0
        
        while time.time() - start_time < TEST_CONFIG['test_duration']:
            pose_data = create_fake_pose_data(frame_id)
            await pose_sender.send_pose_data(pose_data)
            
            frame_id += 1
            await asyncio.sleep(TEST_CONFIG['pose_interval'])
        
        # Wait a bit for any remaining messages
        await asyncio.sleep(2)
        
        # Stop listening
        listen_task.cancel()
        
        # Print test results
        print(f"\nTest completed!")
        print(f"Sent {frame_id} pose messages")
        print(f"Received {len(output_receiver.received_messages)} transformed pose messages")
        
        if output_receiver.received_messages:
            print("\nSample received message:")
            sample_msg = output_receiver.received_messages[0]
            print(f"  Type: {sample_msg.get('type')}")
            print(f"  Wall ID: {sample_msg.get('wall_id')}")
            print(f"  Original landmark count: {sample_msg.get('original_landmark_count')}")
            print(f"  Transformed landmark count: {sample_msg.get('transformed_landmark_count')}")
            
            if sample_msg.get('landmarks'):
                print(f"  Sample transformed landmark: {sample_msg['landmarks'][0]}")
        
    except Exception as e:
        print(f"Test error: {e}")
    finally:
        # Clean up
        await pose_sender.close()
        await output_receiver.close()


async def start_test_servers():
    """Start simple test WebSocket servers"""
    print("Starting test WebSocket servers...")
    
    async def handle_input(websocket, path):
        """Handle input WebSocket connections"""
        print(f"Input client connected: {websocket.remote_address}")
        try:
            async for message in websocket:
                # Just echo back for testing
                await websocket.send(f"Received: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Input client disconnected")
    
    async def handle_output(websocket, path):
        """Handle output WebSocket connections"""
        print(f"Output client connected: {websocket.remote_address}")
        try:
            # Keep connection open
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            print("Output client disconnected")
    
    # Start servers
    input_server = await websockets.serve(handle_input, "localhost", 8765)
    output_server = await websockets.serve(handle_output, "localhost", 8766)
    
    print("Test servers started on ports 8765 (input) and 8766 (output)")
    
    return input_server, output_server


async def main():
    """Main test function"""
    # Start test servers
    input_server, output_server = await start_test_servers()
    
    try:
        # Wait a moment for servers to start
        await asyncio.sleep(1)
        
        # Run the test
        await run_test()
    finally:
        # Close servers
        input_server.close()
        output_server.close()
        await input_server.wait_closed()
        await output_server.wait_closed()
        print("Test servers closed")


if __name__ == "__main__":
    print("WebSocket Pose Transformer Test")
    print("=" * 40)
    print("This test will:")
    print("1. Start test WebSocket servers")
    print("2. Send fake pose data to input server")
    print("3. Verify the transformer processes the data")
    print("4. Check output for transformed coordinates")
    print()
    print("To test with the actual transformer:")
    print("1. Start the transformer: uv run python manage.py websocket_pose_transformer --wall-id 1 --input-websocket-url ws://localhost:8765 --output-websocket-url ws://localhost:8766")
    print("2. Run this test script")
    print()
    
    asyncio.run(main())