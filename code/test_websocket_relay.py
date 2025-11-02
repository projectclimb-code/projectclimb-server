#!/usr/bin/env python3
"""
Simple WebSocket client to test the relay functionality.
This script connects to the WebSocket relay endpoint and can send/receive messages.
"""

import asyncio
import websockets
import json
import sys
from datetime import datetime

async def test_websocket_relay(client_id):
    """Connect to the WebSocket relay and send/receive messages."""
    uri = "ws://localhost:8000/ws/relay/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{client_id}] Connected to WebSocket relay")
            
            # Send a greeting message
            greeting = {
                "type": "greeting",
                "client_id": client_id,
                "message": f"Hello from client {client_id}",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(greeting))
            print(f"[{client_id}] Sent: {greeting}")
            
            # Listen for messages
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    print(f"[{client_id}] Received: {data}")
                except asyncio.TimeoutError:
                    # Send a periodic heartbeat
                    heartbeat = {
                        "type": "heartbeat",
                        "client_id": client_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(heartbeat))
                    print(f"[{client_id}] Sent heartbeat")
                except websockets.exceptions.ConnectionClosed:
                    print(f"[{client_id}] Connection closed")
                    break
                    
    except Exception as e:
        print(f"[{client_id}] Error: {e}")

async def interactive_client():
    """Interactive client that sends user input to the relay."""
    uri = "ws://localhost:8000/ws/relay/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket relay")
            print("Type messages to send (or 'quit' to exit):")
            
            # Create a task to receive messages
            async def receive_messages():
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        print(f"\nReceived: {data}")
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
                    
                    message = {
                        "type": "user_message",
                        "text": user_input,
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(message))
                    print(f"Sent: {message}")
                    
                except KeyboardInterrupt:
                    break
            
            # Cancel the receiver task
            receiver_task.cancel()
            
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Main function to run the test."""
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        await interactive_client()
    else:
        # Create multiple test clients
        client_id = sys.argv[1] if len(sys.argv) > 1 else "test_client"
        await test_websocket_relay(client_id)

if __name__ == "__main__":
    print("WebSocket Relay Test Client")
    print("Usage:")
    print("  python test_websocket_relay.py [client_id]  # Run automated test client")
    print("  python test_websocket_relay.py interactive   # Run interactive client")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted")