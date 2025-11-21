#!/usr/bin/env python3
"""
Test script to demonstrate the reset holds functionality
for the WebSocket pose session tracker.

This script shows how to send a reset message to mark all holds as untouched.
"""

import asyncio
import json
import websockets
import time
from datetime import datetime

async def test_reset_functionality():
    """Test the reset holds functionality"""
    
    # Configuration - update these URLs to match your setup
    input_websocket_url = "ws://localhost:8001"  # URL where the tracker is listening
    output_websocket_url = "ws://localhost:8002"  # URL where tracker sends data
    
    print("Testing WebSocket Pose Session Tracker Reset Functionality")
    print("=" * 60)
    
    try:
        # Connect to the output WebSocket to receive session data
        print(f"Connecting to output WebSocket: {output_websocket_url}")
        output_ws = await websockets.connect(output_websocket_url)
        print("Connected to output WebSocket")
        
        # Connect to the input WebSocket to send messages
        print(f"Connecting to input WebSocket: {input_websocket_url}")
        input_ws = await websockets.connect(input_websocket_url)
        print("Connected to input WebSocket")
        
        # Create a task to receive messages
        async def receive_messages():
            try:
                async for message in output_ws:
                    data = json.loads(message)
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received message:")
                    
                    # Check if this is a reset message
                    if data.get('reset'):
                        print("  🔄 RESET MESSAGE DETECTED!")
                        print(f"  Reset flag: {data.get('reset')}")
                    
                    # Display hold status
                    if 'session' in data and 'holds' in data['session']:
                        holds = data['session']['holds']
                        touched_count = sum(1 for hold in holds if hold.get('status') == 'touched')
                        untouched_count = sum(1 for hold in holds if hold.get('status') == 'untouched')
                        
                        print(f"  Holds: {len(holds)} total, {touched_count} touched, {untouched_count} untouched")
                        
                        # Show status of first few holds
                        for i, hold in enumerate(holds[:5]):
                            status_emoji = "✅" if hold.get('status') == 'touched' else "⭕"
                            print(f"    {status_emoji} {hold.get('id', 'unknown')}: {hold.get('status', 'unknown')}")
                        
                        if len(holds) > 5:
                            print(f"    ... and {len(holds) - 5} more holds")
                    
                    print("-" * 40)
                    
            except websockets.exceptions.ConnectionClosed:
                print("Output WebSocket connection closed")
        
        # Start receiving messages
        receive_task = asyncio.create_task(receive_messages())
        
        # Wait a bit for connections to establish
        await asyncio.sleep(2)
        
        # Send a reset message
        print("\n🔄 Sending reset message...")
        reset_message = {
            "type": "reset_holds"
        }
        
        await input_ws.send(json.dumps(reset_message))
        print(f"Sent: {reset_message}")
        
        # Wait to see the response
        await asyncio.sleep(3)
        
        # Send some fake pose data to see normal operation
        print("\n📸 Sending fake pose data...")
        fake_pose_data = {
            "landmarks": [
                {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9} for _ in range(33)
            ]
        }
        
        await input_ws.send(json.dumps(fake_pose_data))
        print(f"Sent fake pose data with {len(fake_pose_data['landmarks'])} landmarks")
        
        # Wait to see the response
        await asyncio.sleep(3)
        
        # Send another reset message
        print("\n🔄 Sending another reset message...")
        await input_ws.send(json.dumps(reset_message))
        
        # Wait to see the final response
        await asyncio.sleep(3)
        
        # Close connections
        print("\nClosing connections...")
        receive_task.cancel()
        await input_ws.close()
        await output_ws.close()
        
        print("\nTest completed!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("WebSocket Pose Session Tracker - Reset Functionality Test")
    print("\nThis test requires the WebSocket pose session tracker to be running.")
    print("Make sure to start the tracker with appropriate WebSocket URLs.")
    print("\nExample command to start the tracker:")
    print("uv run python manage.py websocket_pose_session_tracker \\")
    print("  --wall-id 1 \\")
    print("  --input-websocket-url ws://localhost:8001 \\")
    print("  --output-websocket-url ws://localhost:8002 \\")
    print("  --debug")
    print("\nPress Enter to start the test...")
    input()
    
    asyncio.run(test_reset_functionality())