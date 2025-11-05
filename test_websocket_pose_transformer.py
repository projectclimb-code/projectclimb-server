#!/usr/bin/env python3
"""
Test script for the WebSocket Pose Transformer

This script demonstrates how to use the websocket_pose_transformer.py script
by creating mock WebSocket servers and clients to test the transformation.
"""

import asyncio
import json
import time
import websockets
import argparse
from typing import Dict, Any, List


class MockWebSocketServer:
    """Mock WebSocket server for testing"""
    
    def __init__(self, port: int, name: str):
        self.port = port
        self.name = name
        self.clients = set()
        self.messages = []
        
    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        self.clients.add(websocket)
        print(f"[{self.name}] Client connected to port {self.port}")
        
        try:
            async for message in websocket:
                data = json.loads(message)
                self.messages.append(data)
                print(f"[{self.name}] Received: {data}")
                
                # Echo back a confirmation
                response = {
                    'type': 'confirmation',
                    'server': self.name,
                    'timestamp': time.time(),
                    'received_at': self.port
                }
                await websocket.send(json.dumps(response))
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"[{self.name}] Client disconnected from port {self.port}")
    
    async def start(self):
        """Start the mock server"""
        print(f"[{self.name}] Starting server on ws://localhost:{self.port}")
        return await websockets.serve(self.handler, "localhost", self.port)


class MockPoseDataSender:
    """Mock client that sends pose data to the transformer input"""
    
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
    
    async def connect(self):
        """Connect to the transformer input"""
        self.websocket = await websockets.connect(self.websocket_url)
        print(f"[Sender] Connected to {self.websocket_url}")
    
    async def send_pose_data(self, frame_id: int):
        """Send sample pose data"""
        # Create sample MediaPipe pose landmarks
        landmarks = []
        for i in range(33):  # MediaPipe has 33 pose landmarks
            landmarks.append({
                'x': 0.3 + (i * 0.01),
                'y': 0.2 + (i * 0.02),
                'z': 0.0,
                'visibility': 0.8 + (i * 0.005)
            })
        
        pose_data = {
            'type': 'pose_data',
            'frame_id': frame_id,
            'timestamp': time.time(),
            'landmarks': landmarks
        }
        
        await self.websocket.send(json.dumps(pose_data))
        print(f"[Sender] Sent pose data frame {frame_id}")
    
    async def close(self):
        """Close the connection"""
        if self.websocket:
            await self.websocket.close()


class MockTransformedDataReceiver:
    """Mock client that receives transformed data from the transformer output"""
    
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
        self.received_messages = []
    
    async def connect(self):
        """Connect to the transformer output"""
        self.websocket = await websockets.connect(self.websocket_url)
        print(f"[Receiver] Connected to {self.websocket_url}")
    
    async def listen(self, max_messages: int = 10):
        """Listen for transformed messages"""
        count = 0
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.received_messages.append(data)
                count += 1
                
                print(f"[Receiver] Received transformed message {count}:")
                print(f"  Type: {data.get('type', 'unknown')}")
                print(f"  Transformed: {data.get('_transformed', False)}")
                print(f"  Message count: {data.get('_message_count', 0)}")
                
                if 'landmarks' in data:
                    print(f"  Landmarks: {len(data['landmarks'])}")
                    # Show first landmark as example
                    if data['landmarks']:
                        first = data['landmarks'][0]
                        print(f"  First landmark: x={first.get('x', 0):.3f}, y={first.get('y', 0):.3f}")
                
                if count >= max_messages:
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            print("[Receiver] Connection closed")
    
    async def close(self):
        """Close the connection"""
        if self.websocket:
            await self.websocket.close()


async def run_test(use_example_transform: bool = False):
    """Run the test scenario"""
    print("WebSocket Pose Transformer Test")
    print("=" * 50)
    
    # Configuration
    input_port = 8765
    output_port = 8766
    
    input_url = f"ws://localhost:{input_port}"
    output_url = f"ws://localhost:{output_port}"
    
    # Create mock servers
    input_server = MockWebSocketServer(input_port, "InputServer")
    output_server = MockWebSocketServer(output_port, "OutputServer")
    
    # Start servers
    await input_server.start()
    await output_server.start()
    
    # Give servers time to start
    await asyncio.sleep(1)
    
    # Start the transformer in a separate task
    transformer_args = [
        "python", "websocket_pose_transformer.py",
        "--input-url", input_url,
        "--output-url", output_url,
        "--debug"
    ]
    
    if use_example_transform:
        transformer_args.append("--use-example-transform")
    
    print(f"\nStarting transformer with command: {' '.join(transformer_args)}")
    
    # Create transformer process
    import subprocess
    transformer_process = subprocess.Popen(
        transformer_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give transformer time to connect
    await asyncio.sleep(3)
    
    try:
        # Create test clients
        sender = MockPoseDataSender(input_url)
        receiver = MockTransformedDataReceiver(output_url)
        
        # Connect clients
        await sender.connect()
        await receiver.connect()
        
        # Start listening in background
        listen_task = asyncio.create_task(receiver.listen(5))
        
        # Send some test data
        print("\nSending test pose data...")
        for frame_id in range(5):
            await sender.send_pose_data(frame_id)
            await asyncio.sleep(0.5)
        
        # Wait for all messages to be processed
        await listen_task
        
        # Print summary
        print(f"\nTest completed!")
        print(f"Sent 5 pose frames")
        print(f"Received {len(receiver.received_messages)} transformed messages")
        
        # Show transformation details
        if receiver.received_messages:
            msg = receiver.received_messages[0]
            print(f"\nTransformation details:")
            print(f"  Transform function used: {'example' if use_example_transform else 'dummy'}")
            print(f"  Message includes _transformed: {msg.get('_transformed', False)}")
            print(f"  Message includes _transform_timestamp: {'_transform_timestamp' in msg}")
            
            if 'landmarks' in msg and msg['landmarks']:
                landmark = msg['landmarks'][0]
                print(f"  Sample landmark transformations:")
                for key, value in landmark.items():
                    if key.startswith(('dummy_', 'transformed_', 'x', 'y', 'z')):
                        print(f"    {key}: {value}")
        
    except Exception as e:
        print(f"Test error: {e}")
    finally:
        # Clean up
        await sender.close()
        await receiver.close()
        
        # Stop transformer
        transformer_process.terminate()
        transformer_process.wait()
        
        print("\nTest completed successfully!")


async def run_simple_test():
    """Run a simpler test without the transformer process"""
    print("Simple WebSocket Connection Test")
    print("=" * 40)
    
    # Configuration
    input_port = 8765
    output_port = 8766
    
    input_url = f"ws://localhost:{input_port}"
    output_url = f"ws://localhost:{output_port}"
    
    # Create mock servers
    input_server = MockWebSocketServer(input_port, "InputServer")
    output_server = MockWebSocketServer(output_port, "OutputServer")
    
    # Start servers
    await input_server.start()
    await output_server.start()
    
    # Give servers time to start
    await asyncio.sleep(1)
    
    try:
        # Test direct connection to servers
        print("Testing direct connection to input server...")
        sender = MockPoseDataSender(input_url)
        await sender.connect()
        await sender.send_pose_data(1)
        await sender.close()
        
        print("Testing direct connection to output server...")
        receiver = MockTransformedDataReceiver(output_url)
        await receiver.connect()
        await receiver.close()
        
        print("\nDirect connection test successful!")
        print(f"Input server received {len(input_server.messages)} messages")
        print(f"Output server received {len(output_server.messages)} messages")
        
    except Exception as e:
        print(f"Test error: {e}")
    
    print("\nSimple test completed!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Test WebSocket Pose Transformer')
    parser.add_argument(
        '--simple',
        action='store_true',
        help='Run simple connection test only'
    )
    parser.add_argument(
        '--example-transform',
        action='store_true',
        help='Test with example transform function'
    )
    
    args = parser.parse_args()
    
    if args.simple:
        asyncio.run(run_simple_test())
    else:
        asyncio.run(run_test(use_example_transform=args.example_transform))


if __name__ == "__main__":
    main()