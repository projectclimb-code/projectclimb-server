#!/usr/bin/env python3
"""
Simple WebSocket client to test the general functionality.
This script connects to the WebSocket general endpoint and can send/receive messages.
"""

import asyncio
import websockets
import json
import sys
from datetime import datetime

async def test_websocket_general(room_name, client_id):
    """Connect to the WebSocket general endpoint and send/receive messages."""
    uri = f"ws://localhost:8000/ws/general/{room_name}/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{client_id}] Connected to WebSocket general room: {room_name}")
            
            # Send a greeting message (JSON)
            greeting = {
                "type": "greeting",
                "client_id": client_id,
                "message": f"Hello from client {client_id} in room {room_name}",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(greeting))
            print(f"[{client_id}] Sent JSON: {greeting}")
            
            # Send a plain string message
            string_message = f"Plain string message from {client_id}"
            await websocket.send(string_message)
            print(f"[{client_id}] Sent string: {string_message}")
            
            # Listen for messages
            message_count = 0
            while message_count < 5:  # Limit to 5 messages for testing
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    try:
                        # Try to parse as JSON
                        data = json.loads(message)
                        print(f"[{client_id}] Received JSON: {data}")
                    except json.JSONDecodeError:
                        # If not JSON, treat as plain string
                        print(f"[{client_id}] Received string: {message}")
                    
                    message_count += 1
                except asyncio.TimeoutError:
                    print(f"[{client_id}] Timeout waiting for messages")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print(f"[{client_id}] Connection closed")
                    break
                    
    except Exception as e:
        print(f"[{client_id}] Error: {e}")

async def interactive_client(room_name):
    """Interactive client that sends user input to the general room."""
    uri = f"ws://localhost:8000/ws/general/{room_name}/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to WebSocket general room: {room_name}")
            print("Type messages to send (or 'quit' to exit):")
            print("Send 'json:' followed by JSON to send as JSON, otherwise sends as plain string")
            
            # Create a task to receive messages
            async def receive_messages():
                while True:
                    try:
                        message = await websocket.recv()
                        try:
                            # Try to parse as JSON
                            data = json.loads(message)
                            print(f"\nReceived JSON: {data}")
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain string
                            print(f"\nReceived string: {message}")
                        print("Type messages to send (or 'quit' to exit): ", end="", flush=True)
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection closed")
                        break
            
            # Start the receiver task
            receiver_task = asyncio.create_task(receive_messages())
            
            # Send user input
            while True:
                try:
                    user_input = input("Type messages to send (or 'quit' to exit): ")
                    if user_input.lower() == 'quit':
                        break
                    
                    if user_input.startswith('json:'):
                        # Send as JSON
                        json_content = user_input[5:]  # Remove 'json:' prefix
                        try:
                            # Try to parse as JSON to validate
                            json_obj = json.loads(json_content)
                            await websocket.send(json.dumps(json_obj))
                            print(f"Sent JSON: {json_obj}")
                        except json.JSONDecodeError:
                            print("Invalid JSON format")
                    else:
                        # Send as plain string
                        await websocket.send(user_input)
                        print(f"Sent string: {user_input}")
                    
                except KeyboardInterrupt:
                    break
            
            # Cancel the receiver task
            receiver_task.cancel()
            
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Main function to run the test."""
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        if len(sys.argv) < 3:
            print("Usage: python test_websocket_general.py interactive <room_name>")
            return
        room_name = sys.argv[2]
        await interactive_client(room_name)
    else:
        # Create multiple test clients
        room_name = sys.argv[1] if len(sys.argv) > 1 else "test_room"
        client_id = sys.argv[2] if len(sys.argv) > 2 else "test_client"
        await test_websocket_general(room_name, client_id)

if __name__ == "__main__":
    print("WebSocket General Test Client")
    print("Usage:")
    print("  python test_websocket_general.py <room_name> [client_id]  # Run automated test client")
    print("  python test_websocket_general.py interactive <room_name>  # Run interactive client")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted")