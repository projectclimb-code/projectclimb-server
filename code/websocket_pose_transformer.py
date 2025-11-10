#!/usr/bin/env python3
"""
WebSocket Pose Transformer Script

This script connects to two WebSocket channels:
1. Input channel - receives pose data messages
2. Output channel - sends transformed pose data messages

It applies a custom transformation function to the received data before forwarding it.
"""

import asyncio
import json
import time
import argparse
import logging
from typing import Dict, Any, Callable, Optional

import websockets

from climber.tansformation_utils import apply_homography_to_mediapipe_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketPoseTransformer:
    """Main class for transforming pose data between WebSocket channels"""
    
    def __init__(
        self,
        input_url: str,
        output_url: str,
        transform_func: Optional[Callable] = None,
        reconnect_delay: float = 5.0,
        debug: bool = False
    ):
        """
        Initialize the WebSocket pose transformer
        
        Args:
            input_url: WebSocket URL to receive messages from
            output_url: WebSocket URL to send transformed messages to
            transform_func: Function to transform the data (default: dummy_transform)
            reconnect_delay: Delay in seconds between reconnection attempts
            debug: Enable debug logging
        """
        self.input_url = input_url
        self.output_url = output_url
        self.transform_func = transform_func or self.dummy_transform
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # WebSocket connections
        self.input_websocket = None
        self.output_websocket = None
        
        # State
        self.running = False
        self.message_count = 0
        self.start_time = time.time()
        
    async def connect_input_websocket(self):
        """Connect to the input WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to input WebSocket: {self.input_url}")
                self.input_websocket = await websockets.connect(self.input_url)
                logger.info("Successfully connected to input WebSocket")
                
                # Listen for messages
                await self.listen_for_messages()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Input WebSocket connection error: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                logger.error(f"Unexpected error in input WebSocket: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
    
    async def connect_output_websocket(self):
        """Connect to the output WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to output WebSocket: {self.output_url}")
                self.output_websocket = await websockets.connect(self.output_url)
                logger.info("Successfully connected to output WebSocket")
                
                # Keep connection alive with periodic pings
                await self.keep_output_alive()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"Output WebSocket connection error: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                logger.error(f"Unexpected error in output WebSocket: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
    
    async def keep_output_alive(self):
        """Keep the output WebSocket connection alive with periodic pings"""
        try:
            while self.running and self.output_websocket:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if self.output_websocket:
                    await self.output_websocket.ping()
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Output WebSocket connection closed during keep-alive")
            raise
    
    async def listen_for_messages(self):
        """Listen for incoming messages from the input WebSocket"""
        try:
            async for message in self.input_websocket:
                try:
                    # Parse the message
                    data = json.loads(message)
                    logger.debug(f"Received message: {data}")
                    
                    # Apply transformation
                    transformed_data = await self.transform_data(data)
                    
                    # Send to output
                    await self.send_to_output(transformed_data)
                    
                    self.message_count += 1
                    
                    # Log progress every 100 messages
                    if self.message_count % 100 == 0:
                        elapsed = time.time() - self.start_time
                        rate = self.message_count / elapsed
                        logger.info(f"Processed {self.message_count} messages ({rate:.2f} msg/sec)")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Input WebSocket connection closed")
            raise
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            raise
    
    async def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform the received data using the custom transformation function
        
        Args:
            data: The original data received from the input WebSocket
            
        Returns:
            The transformed data
        """
        try:
            # Apply the custom transformation function
            transformed = await self.transform_func(data)
            
            # Add metadata
            transformed['_transformed'] = True
            transformed['_transform_timestamp'] = time.time()
            transformed['_message_count'] = self.message_count + 1
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error in transformation: {e}")
            # Return original data with error flag
            return {
                '_error': True,
                '_error_message': str(e),
                '_original_data': data,
                '_transform_timestamp': time.time()
            }
    
    async def send_to_output(self, data: Dict[str, Any]):
        """
        Send transformed data to the output WebSocket
        
        Args:
            data: The data to send
        """
        if self.output_websocket:
            try:
                await self.output_websocket.send(json.dumps(data))
                logger.debug(f"Sent transformed message: {data}")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                raise
    
    async def dummy_transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Default dummy transformation function
        Simply adds a timestamp and passes the data through
        
        Args:
            data: The original data
            
        Returns:
            The transformed data
        """
        # Create a copy to avoid modifying the original
        result = data.copy()
        
        # Add some dummy transformation
        result['dummy_transformed'] = True
        result['dummy_timestamp'] = time.time()
        
        # If the data contains pose landmarks, add a simple transformation
        transform_matrix = [[0.8759625081014805, -0.29987838627308905, 0.0014179425240763138],
                        [-0.017790708207697313, 0.7811108885186794, -0.023430990240347126],
                        [-0.03868152961860345, -0.7459689352582686, 1.0]]
        result = apply_homography_to_mediapipe_json(result, transform_matrix)

        
        return result
    
    async def run(self):
        """Main event loop"""
        logger.info("Starting WebSocket pose transformer...")
        self.running = True
        self.start_time = time.time()
        
        try:
            # Start both WebSocket connections
            input_task = asyncio.create_task(self.connect_input_websocket())
            output_task = asyncio.create_task(self.connect_output_websocket())
            
            # Wait for tasks to complete (they should run indefinitely)
            await asyncio.gather(input_task, output_task)
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        self.running = False
        
        if self.input_websocket:
            await self.input_websocket.close()
        
        if self.output_websocket:
            await self.output_websocket.close()
        
        # Log final statistics
        elapsed = time.time() - self.start_time
        logger.info(f"Processed {self.message_count} messages in {elapsed:.2f} seconds")
        if elapsed > 0:
            logger.info(f"Average rate: {self.message_count / elapsed:.2f} messages/second")
        
        logger.info("Cleanup complete")


async def example_transform_function(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example custom transformation function
    
    This function demonstrates how to create a custom transformation.
    It adds a simple offset to pose landmark coordinates.
    
    Args:
        data: The original data
        
    Returns:
        The transformed data
    """
    result = data.copy()
    
    # Add custom transformation metadata
    result['custom_transformed'] = True
    result['transform_name'] = 'example_offset_transform'
    
    # If pose landmarks are present, apply coordinate transformation
    if 'landmarks' in data and isinstance(data['landmarks'], list):
        for i, landmark in enumerate(data['landmarks']):
            if isinstance(landmark, dict):
                # Apply a simple offset transformation
                if 'x' in landmark:
                    landmark['transformed_x'] = landmark['x'] + 0.1
                if 'y' in landmark:
                    landmark['transformed_y'] = landmark['y'] + 0.1
                if 'z' in landmark:
                    landmark['transformed_z'] = landmark['z']
    
    return result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='WebSocket Pose Transformer')
    parser.add_argument(
        '--input-url',
        type=str,
        required=True,
        help='WebSocket URL for receiving messages (e.g., ws://localhost:8765)'
    )
    parser.add_argument(
        '--output-url',
        type=str,
        required=True,
        help='WebSocket URL for sending transformed messages (e.g., ws://localhost:8766)'
    )
    parser.add_argument(
        '--reconnect-delay',
        type=float,
        default=5.0,
        help='Delay between reconnection attempts in seconds'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--use-example-transform',
        action='store_true',
        help='Use the example transformation function instead of the dummy one'
    )
    
    args = parser.parse_args()
    
    # Choose transformation function
    transform_func = example_transform_function if args.use_example_transform else None
    
    # Create and run transformer
    transformer = WebSocketPoseTransformer(
        input_url=args.input_url,
        output_url=args.output_url,
        transform_func=transform_func,
        reconnect_delay=args.reconnect_delay,
        debug=args.debug
    )
    
    # Run the transformer
    asyncio.run(transformer.run())


if __name__ == "__main__":
    main()