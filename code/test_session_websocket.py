#!/usr/bin/env python3
"""
Test script for the session WebSocket implementation.
This script tests the new session WebSocket endpoint and fake data command.
"""

import asyncio
import websockets
import json
import sys
import argparse
from datetime import datetime

async def test_session_websocket(session_id, ws_url="ws://localhost:8000/ws/session-live/"):
    """Test the session WebSocket connection"""
    full_ws_url = f"{ws_url}{session_id}/"
    
    print(f"Testing WebSocket connection to: {full_ws_url}")
    
    try:
        async with websockets.connect(full_ws_url) as websocket:
            print("✓ WebSocket connection established")
            
            # Send a test message
            test_message = {
                'type': 'test',
                'timestamp': datetime.now().isoformat()
            }
            await websocket.send(json.dumps(test_message))
            print(f"✓ Sent test message: {test_message}")
            
            # Wait for responses
            timeout = 5  # seconds
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                response_data = json.loads(response)
                print(f"✓ Received response: {response_data}")
            except asyncio.TimeoutError:
                print("✗ No response received within timeout")
                return False
            
            return True
            
    except websockets.exceptions.ConnectionRefused:
        print("✗ Connection refused. Make sure the Django server is running.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

async def test_fake_data_command(session_id, duration=10):
    """Test the fake data command by running it"""
    print(f"Testing fake data command for session {session_id}")
    
    # Import here to avoid Django setup issues
    import os
    import subprocess
    
    try:
        # Change to the code directory
        os.chdir('code')
        
        # Run the management command
        cmd = [
            'uv', 'run', 'python', 'manage.py', 'send_fake_session_data',
            '--session-id', session_id,
            '--duration', str(duration)
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for the process to complete
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            print("✓ Fake data command executed successfully")
            print(f"Output: {stdout}")
            return True
        else:
            print(f"✗ Fake data command failed with return code {process.returncode}")
            print(f"Error: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error running fake data command: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test session WebSocket implementation")
    parser.add_argument("--session-id", help="UUID of the session to test")
    parser.add_argument("--ws-url", default="ws://localhost:8000/ws/session-live/", help="WebSocket URL")
    parser.add_argument("--test-fake-data", action="store_true", help="Test the fake data command")
    parser.add_argument("--duration", type=int, default=10, help="Duration for fake data test")
    
    args = parser.parse_args()
    
    print("Starting session WebSocket tests...\n")
    
    all_tests_passed = True
    
    # Test WebSocket connection
    if args.session_id:
        if not asyncio.run(test_session_websocket(args.session_id, args.ws_url)):
            all_tests_passed = False
            print("\nWebSocket test failed.")
    else:
        print("No session ID provided. Skipping WebSocket test.")
    
    print()
    
    # Test fake data command
    if args.test_fake_data and args.session_id:
        if not asyncio.run(test_fake_data_command(args.session_id, args.duration)):
            all_tests_passed = False
            print("\nFake data command test failed.")
    elif args.test_fake_data:
        print("No session ID provided. Skipping fake data command test.")
    
    print()
    
    if all_tests_passed:
        print("✓ All tests passed! The session WebSocket implementation is working correctly.")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()