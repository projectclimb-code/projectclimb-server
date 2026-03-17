#!/usr/bin/env python3
"""
Test script for the enhanced websocket_pose_session_tracker control commands.

This script tests the new control functionality:
- pause_output/resume_output commands
- update_parameters command for proximity_threshold, touch_duration, route_id
- get_status command to retrieve current state
- reset_holds command (existing functionality)

Usage:
    python test_control_commands.py --control-websocket-url ws://localhost:8003
"""

import asyncio
import json
import websockets
import argparse
import time
from datetime import datetime


async def test_control_commands(control_ws_url):
    """Test various control commands"""
    
    try:
        # Connect to control WebSocket
        print(f"Connecting to control WebSocket: {control_ws_url}")
        async with websockets.connect(control_ws_url) as websocket:
            print("Connected to control WebSocket")
            
            # Test 1: Get status
            print("\n=== Test 1: Get Status ===")
            status_command = {"type": "get_status"}
            await websocket.send(json.dumps(status_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            status_data = json.loads(response)
            print(f"Status response: {json.dumps(status_data, indent=2)}")
            
            # Test 2: Pause output
            print("\n=== Test 2: Pause Output ===")
            pause_command = {"type": "pause_output"}
            await websocket.send(json.dumps(pause_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            pause_data = json.loads(response)
            print(f"Pause response: {json.dumps(pause_data, indent=2)}")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Test 3: Update parameters
            print("\n=== Test 3: Update Parameters ===")
            update_command = {
                "type": "update_parameters",
                "parameters": {
                    "proximity_threshold": 75.0,
                    "touch_duration": 1.5,
                    "route_id": 1
                }
            }
            await websocket.send(json.dumps(update_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            update_data = json.loads(response)
            print(f"Update response: {json.dumps(update_data, indent=2)}")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Test 4: Resume output
            print("\n=== Test 4: Resume Output ===")
            resume_command = {"type": "resume_output"}
            await websocket.send(json.dumps(resume_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            resume_data = json.loads(response)
            print(f"Resume response: {json.dumps(resume_data, indent=2)}")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Test 5: Get status again to verify changes
            print("\n=== Test 5: Get Status (After Updates) ===")
            await websocket.send(json.dumps(status_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            final_status = json.loads(response)
            print(f"Final status: {json.dumps(final_status, indent=2)}")
            
            # Test 6: Reset holds (existing functionality)
            print("\n=== Test 6: Reset Holds ===")
            reset_command = {"type": "reset_holds"}
            await websocket.send(json.dumps(reset_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            reset_data = json.loads(response)
            print(f"Reset response: {json.dumps(reset_data, indent=2)}")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Test 7: Stop tracker
            print("\n=== Test 7: Stop Tracker ===")
            stop_command = {"type": "stop"}
            await websocket.send(json.dumps(stop_command))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            stop_data = json.loads(response)
            print(f"Stop response: {json.dumps(stop_data, indent=2)}")
            
            print("\n=== All Tests Completed ===")
            
    except Exception as e:
        print(f"Error during test: {e}")


def main():
    parser = argparse.ArgumentParser(description='Test control commands for websocket_pose_session_tracker')
    parser.add_argument(
        '--control-websocket-url',
        required=True,
        help='WebSocket URL for control commands'
    )
    
    args = parser.parse_args()
    
    # Run the test
    asyncio.run(test_control_commands(args.control_websocket_url))


if __name__ == '__main__':
    main()