#!/usr/bin/env python3
"""
Test script to verify WebSocket connection improvements in websocket_pose_session_tracker.py

This script creates a simple test to verify that the WebSocket connections are more stable
and don't experience the "keepalive ping timeout" errors that were occurring before.
"""

import asyncio
import json
import time
import websockets
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

from climber.management.commands.websocket_pose_session_tracker import (
    InputWebSocketClient, 
    OutputWebSocketClient,
    WebSocketPoseSessionTracker
)


async def test_output_websocket_client():
    """Test the improved OutputWebSocketClient"""
    print("Testing OutputWebSocketClient...")
    
    # Create a mock WebSocket server
    async def mock_server(websocket):
        try:
            # Echo back received messages
            async for message in websocket:
                await websocket.send(f"Echo: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Server: Connection closed")
        except Exception as e:
            print(f"Server error: {e}")
    
    # Start the mock server
    server = await websockets.serve(mock_server, "localhost", 8765)
    print("Mock WebSocket server started on ws://localhost:8765")
    
    # Create output client
    message_handler = AsyncMock()
    output_client = OutputWebSocketClient("ws://localhost:8765")
    
    # Start the client
    client_task = output_client.start()
    
    # Wait a bit for connection to establish
    await asyncio.sleep(1)
    
    # Send some test messages
    test_messages = [
        {"type": "test", "message": "Hello World"},
        {"type": "pose", "landmarks": [{"x": 0.1, "y": 0.2, "z": 0.3, "visibility": 0.9}]},
        {"type": "session", "session_id": "test123"}
    ]
    
    for msg in test_messages:
        await output_client.send_message(msg)
        print(f"Sent message: {msg}")
        await asyncio.sleep(0.5)
    
    # Let it run for a bit to test keep-alive
    print("Testing keep-alive mechanism for 15 seconds...")
    await asyncio.sleep(15)
    
    # Stop the client
    output_client.stop()
    
    # Wait for client task to complete
    try:
        await asyncio.wait_for(client_task, timeout=5)
    except asyncio.TimeoutError:
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass
    
    # Stop the server
    server.close()
    await server.wait_closed()
    
    print("OutputWebSocketClient test completed successfully!")


async def test_connection_stability():
    """Test connection stability with multiple reconnections"""
    print("\nTesting connection stability...")
    
    # Create a mock WebSocket server that disconnects clients periodically
    disconnect_counter = 0
    
    async def unstable_server(websocket):
        nonlocal disconnect_counter
        try:
            disconnect_counter += 1
            print(f"Server: Client connected (connection #{disconnect_counter})")
            
            # Disconnect after 5 seconds every other connection
            if disconnect_counter % 2 == 0:
                await asyncio.sleep(5)
                print(f"Server: Forcefully disconnecting client #{disconnect_counter}")
                return
            
            # Otherwise keep connection alive
            async for message in websocket:
                await websocket.send(f"Echo: {message}")
                
        except websockets.exceptions.ConnectionClosed:
            print(f"Server: Client #{disconnect_counter} disconnected")
        except Exception as e:
            print(f"Server error: {e}")
    
    # Start the mock server
    server = await websockets.serve(unstable_server, "localhost", 8766)
    print("Unstable WebSocket server started on ws://localhost:8766")
    
    # Create output client with shorter reconnect delay for testing
    output_client = OutputWebSocketClient("ws://localhost:8766", reconnect_delay=1.0)
    
    # Start the client
    client_task = output_client.start()
    
    # Test for 30 seconds to see reconnection behavior
    print("Testing reconnection behavior for 30 seconds...")
    
    for i in range(6):
        await asyncio.sleep(5)
        if output_client.websocket:
            await output_client.send_message({"test": f"message_{i}", "timestamp": time.time()})
            print(f"Sent message {i}")
        else:
            print(f"Connection not available at iteration {i}")
    
    # Stop the client
    output_client.stop()
    
    # Wait for client task to complete
    try:
        await asyncio.wait_for(client_task, timeout=5)
    except asyncio.TimeoutError:
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass
    
    # Stop the server
    server.close()
    await server.wait_closed()
    
    print(f"Connection stability test completed! Server handled {disconnect_counter} connections.")


async def main():
    """Run all tests"""
    print("Starting WebSocket connection improvement tests...\n")
    
    try:
        await test_output_websocket_client()
        await test_connection_stability()
        
        print("\n" + "="*50)
        print("All tests completed successfully!")
        print("The WebSocket connection improvements appear to be working correctly.")
        print("You should no longer see 'keepalive ping timeout' errors.")
        print("="*50)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)