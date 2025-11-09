#!/usr/bin/env python3
"""
Test script to verify WebSocket functionality for get_image message
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_get_image_message():
    """Test sending a get_image message to the WebSocket endpoint"""
    uri = "ws://127.0.0.1:8000/ws/pose/"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"Connected to WebSocket at {uri}")
            
            # Send the get_image message
            message = {
                "type": "get_image",
                "wall_id": "264d7633-65b2-41a8-92a4-34eb79a891bb"
            }
            
            await websocket.send(json.dumps(message))
            logger.info(f"Sent message: {message}")
            
            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"Received response: {response}")
            except asyncio.TimeoutError:
                logger.info("No response received within 5 seconds (this may be expected)")
            
    except Exception as e:
        logger.error(f"WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_get_image_message())