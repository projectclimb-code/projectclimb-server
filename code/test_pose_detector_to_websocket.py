#!/usr/bin/env python3
"""
Test script for the Pose Detector to WebSocket functionality
"""

import asyncio
import json
import logging
import argparse
import websockets
from pose_detector_to_websocket import PoseDetectorToWebSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_websocket_receiver(websocket_url: str, message_count: int = 10):
    """
    Test WebSocket receiver to listen for pose data
    
    Args:
        websocket_url: WebSocket URL to connect to
        message_count: Number of messages to receive before stopping
    """
    received_messages = []
    
    try:
        logger.info(f"Connecting to WebSocket: {websocket_url}")
        async with websockets.connect(websocket_url) as websocket:
            logger.info("Connected to WebSocket, waiting for messages...")
            
            for i in range(message_count):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    received_messages.append(data)
                    
                    logger.info(f"Received message {i+1}/{message_count}")
                    logger.debug(f"Message data: {data}")
                    
                    # Check if pose landmarks are present
                    if 'landmarks' in data and data['landmarks']:
                        logger.info(f"Pose detected with {len(data['landmarks'])} landmarks")
                    else:
                        logger.info("No pose detected in this frame")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for message {i+1}")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    
    except Exception as e:
        logger.error(f"Error in WebSocket receiver: {e}")
    
    return received_messages


async def run_test(video_source: str, websocket_url: str, test_duration: int = 10):
    """
    Run a complete test of the pose detector
    
    Args:
        video_source: Video source to test with
        websocket_url: WebSocket URL for testing
        test_duration: Duration in seconds to run the test
    """
    logger.info(f"Starting test with video source: {video_source}")
    logger.info(f"WebSocket URL: {websocket_url}")
    
    # Create pose detector instance
    detector = PoseDetectorToWebSocket(
        websocket_url=websocket_url,
        video_source=video_source,
        loop_video=True,
        target_fps=10,  # Lower FPS for testing
        debug=True
    )
    
    # Start the detector in the background
    detector_task = asyncio.create_task(detector.run())
    
    # Wait a bit for the detector to start
    await asyncio.sleep(2)
    
    # Run the WebSocket receiver test
    logger.info("Starting WebSocket receiver test...")
    expected_messages = test_duration * 10  # Based on 10 FPS
    received_messages = await test_websocket_receiver(websocket_url, expected_messages)
    
    # Stop the detector
    logger.info("Stopping detector...")
    detector.running = False
    await detector_task
    
    # Print test results
    logger.info(f"Test completed. Received {len(received_messages)} messages")
    
    if received_messages:
        # Analyze received messages
        pose_detected_count = sum(1 for msg in received_messages if msg.get('landmarks'))
        logger.info(f"Frames with pose detected: {pose_detected_count}/{len(received_messages)}")
        
        if pose_detected_count > 0:
            logger.info("✅ Test PASSED: Pose data successfully streamed to WebSocket")
        else:
            logger.warning("⚠️ Test WARNING: No pose data detected in any frames")
    else:
        logger.error("❌ Test FAILED: No messages received from WebSocket")


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test Pose Detector to WebSocket")
    parser.add_argument(
        "--video-source",
        default="0",
        help="Video source to test with (camera index or file path)"
    )
    parser.add_argument(
        "--websocket-url",
        default="ws://localhost:8000/ws/pose/",
        help="WebSocket URL for testing"
    )
    parser.add_argument(
        "--test-duration",
        type=int,
        default=10,
        help="Duration in seconds to run the test"
    )
    
    args = parser.parse_args()
    
    await run_test(args.video_source, args.websocket_url, args.test_duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test stopped by user")