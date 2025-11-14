# Pose Replayer Implementation Plan

## Detailed Implementation Guide

### 1. JSON Data Format Analysis

Based on the existing codebase, particularly the `websocket_pose_session_tracker.py`, the JSON data likely follows this structure:

```json
{
  "timestamp": 1699876543.123,
  "landmarks": [
    {"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.9},
    {"x": 0.6, "y": 0.4, "z": 0.1, "visibility": 0.8},
    // ... more landmarks
  ],
  // Possibly additional fields
}
```

Or it might be in the session format:
```json
{
  "session": {
    "holds": [...],
    "startTime": "...",
    "endTime": null,
    "status": "started"
  },
  "pose": [...]
}
```

The script needs to be flexible to handle different timestamp formats:
- Unix timestamp (float)
- ISO 8601 string
- Custom format

### 2. WebSocket Client Implementation

Following the pattern from `websocket_pose_session_tracker.py`:

```python
class WebSocketClient:
    def __init__(self, url, reconnect_delay=5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.websocket = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.message_queue = asyncio.Queue()
        self.sender_task = None
        
    async def connect(self):
        """Connect to WebSocket with reconnection logic"""
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                logger.info("Successfully connected to WebSocket")
                self.current_reconnect_delay = self.reconnect_delay
                
                # Start sender task
                self.sender_task = asyncio.create_task(self.message_sender())
                
                # Keep connection alive
                await self.keep_alive()
                
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.ConnectionClosedError,
                   ConnectionRefusedError,
                   OSError) as e:
                logger.error(f"WebSocket connection error: {e}")
                if self.running:
                    await self._wait_and_reconnect()
            except Exception as e:
                logger.error(f"Unexpected error in WebSocket: {e}")
                if self.running:
                    await self._wait_and_reconnect()
    
    async def message_sender(self):
        """Send queued messages to WebSocket"""
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                
                if self.websocket:
                    await self.websocket.send(json.dumps(message))
                    logger.debug(f"Sent message: {message}")
                    
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed while sending")
                await self.message_queue.put(message)
                raise
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await self.message_queue.put(message)
    
    async def send_message(self, message):
        """Queue a message to be sent"""
        await self.message_queue.put(message)
```

### 3. File Reading and JSON Parsing

```python
class JsonsFileReader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.json_data = []
        self.timestamps = []
        
    async def load_file(self):
        """Load and parse all JSON lines from file"""
        try:
            with open(self.file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        json_obj = json.loads(line)
                        self.json_data.append(json_obj)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON on line {line_num}: {e}")
                        continue
            
            logger.info(f"Loaded {len(self.json_data)} JSON objects from {self.file_path}")
            
        except FileNotFoundError:
            logger.error(f"File not found: {self.file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {self.file_path}: {e}")
            raise
    
    def extract_timestamps(self, timestamp_field: str = "timestamp"):
        """Extract timestamps from JSON objects"""
        self.timestamps = []
        
        for i, obj in enumerate(self.json_data):
            timestamp = None
            
            # Try direct field access
            if timestamp_field in obj:
                timestamp = obj[timestamp_field]
            
            # Try nested in session
            elif 'session' in obj and timestamp_field in obj['session']:
                timestamp = obj['session'][timestamp_field]
            
            # Try other common fields
            elif 'time' in obj:
                timestamp = obj['time']
            elif 'created_at' in obj:
                timestamp = obj['created_at']
            
            if timestamp is None:
                logger.warning(f"No timestamp found in object {i}, using index")
                timestamp = i  # Fallback to index
            
            # Convert to float if needed
            if isinstance(timestamp, str):
                try:
                    # Try ISO format first
                    timestamp = datetime.fromisoformat(
                        timestamp.replace('Z', '+00:00')
                    ).timestamp()
                except ValueError:
                    try:
                        # Try parsing as float
                        timestamp = float(timestamp)
                    except ValueError:
                        logger.warning(f"Cannot parse timestamp '{timestamp}' in object {i}")
                        timestamp = i
            
            self.timestamps.append(float(timestamp))
        
        return self.timestamps
    
    def calculate_delays(self):
        """Calculate delays between consecutive messages"""
        if len(self.timestamps) < 2:
            return [0.0] * len(self.timestamps)
        
        delays = []
        for i in range(len(self.timestamps)):
            if i == 0:
                delays.append(0.0)  # No delay for first message
            else:
                delay = self.timestamps[i] - self.timestamps[i-1]
                # Ensure non-negative delay
                delays.append(max(0.0, delay))
        
        return delays
```

### 4. Main PoseReplayer Class

```python
class PoseReplayer:
    def __init__(self, file_path: str, websocket_url: str, 
                 timestamp_field: str = "timestamp", 
                 loop: bool = True,
                 reconnect_delay: float = 5.0,
                 debug: bool = False):
        self.file_path = file_path
        self.websocket_url = websocket_url
        self.timestamp_field = timestamp_field
        self.loop = loop
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        
        # Components
        self.file_reader = JsonsFileReader(file_path)
        self.websocket_client = WebSocketClient(websocket_url, reconnect_delay)
        
        # State
        self.running = False
        self.delays = []
        
    async def setup(self):
        """Setup all components"""
        # Load and parse file
        await self.file_reader.load_file()
        
        # Extract timestamps
        self.file_reader.extract_timestamps(self.timestamp_field)
        
        # Calculate delays
        self.delays = self.file_reader.calculate_delays()
        
        logger.info(f"Setup complete with {len(self.file_reader.json_data)} messages")
        
    async def replay_loop(self):
        """Main replay loop"""
        json_data = self.file_reader.json_data
        
        while self.running:
            logger.info("Starting replay cycle")
            
            for i, (message, delay) in enumerate(zip(json_data, self.delays)):
                if not self.running:
                    break
                
                # Send message
                await self.websocket_client.send_message(message)
                
                if self.debug:
                    logger.debug(f"Sent message {i+1}/{len(json_data)}")
                
                # Wait for next message timing
                if i < len(json_data) - 1:  # Don't wait after last message
                    await asyncio.sleep(delay)
            
            # Check if we should continue looping
            if not self.loop:
                logger.info("Replay complete (loop disabled)")
                break
            
            logger.info("Replay cycle complete, restarting...")
    
    async def run(self):
        """Main entry point"""
        try:
            # Setup
            await self.setup()
            
            # Start WebSocket client
            self.running = True
            self.websocket_client.running = True
            websocket_task = asyncio.create_task(self.websocket_client.connect())
            
            # Wait a bit for connection
            await asyncio.sleep(1)
            
            # Start replay
            await self.replay_loop()
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up...")
        self.running = False
        self.websocket_client.running = False
        
        if self.websocket_client.websocket:
            await self.websocket_client.websocket.close()
        
        logger.info("Cleanup complete")
```

### 5. Command Line Interface

```python
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Replay pose data from JSONS file to WebSocket endpoint"
    )
    
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to the input JSONS file'
    )
    parser.add_argument(
        '--websocket',
        type=str,
        required=True,
        help='WebSocket endpoint URL'
    )
    parser.add_argument(
        '--timestamp-field',
        type=str,
        default='timestamp',
        help='Field name containing timestamp (default: timestamp)'
    )
    parser.add_argument(
        '--no-loop',
        action='store_true',
        help='Disable looping (play once)'
    )
    parser.add_argument(
        '--reconnect-delay',
        type=float,
        default=5.0,
        help='Delay between reconnection attempts in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Configure logging
    logger.remove()
    if args.debug:
        logger.add(
            sys.stderr,
            level="DEBUG"
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO"
        )
    
    # Create and run replayer
    replayer = PoseReplayer(
        file_path=args.file,
        websocket_url=args.websocket,
        timestamp_field=args.timestamp_field,
        loop=not args.no_loop,
        reconnect_delay=args.reconnect_delay,
        debug=args.debug
    )
    
    asyncio.run(replayer.run())


if __name__ == "__main__":
    main()
```

### 6. Error Handling Enhancements

```python
class PoseReplayerError(Exception):
    """Base exception for pose replayer"""
    pass

class FileLoadError(PoseReplayerError):
    """Error loading file"""
    pass

class WebSocketConnectionError(PoseReplayerError):
    """WebSocket connection error"""
    pass

class TimestampError(PoseReplayerError):
    """Error with timestamps"""
    pass
```

### 7. Testing Strategy

```python
# test_pose_replayer.py
import pytest
import asyncio
import json
import tempfile
import websockets
from unittest.mock import AsyncMock, patch

class TestPoseReplayer:
    @pytest.fixture
    def sample_jsons_file(self):
        # Create temporary JSONS file
        content = [
            {"timestamp": 1000.0, "data": "message1"},
            {"timestamp": 1002.5, "data": "message2"},
            {"timestamp": 1005.0, "data": "message3"}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
            for item in content:
                f.write(json.dumps(item) + '\n')
            return f.name
    
    @pytest.mark.asyncio
    async def test_file_reading(self, sample_jsons_file):
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        
        assert len(reader.json_data) == 3
        assert reader.json_data[0]["data"] == "message1"
    
    @pytest.mark.asyncio
    async def test_timestamp_extraction(self, sample_jsons_file):
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        timestamps = reader.extract_timestamps()
        
        assert timestamps == [1000.0, 1002.5, 1005.0]
    
    @pytest.mark.asyncio
    async def test_delay_calculation(self, sample_jsons_file):
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        reader.extract_timestamps()
        delays = reader.calculate_delays()
        
        assert delays == [0.0, 2.5, 2.5]
```

### 8. Performance Optimizations

For large files, consider:
1. Streaming file reading instead of loading all at once
2. Memory-efficient circular buffer for looping
3. Batch processing of timestamps
4. Configurable buffer size

```python
class StreamingJsonsFileReader:
    def __init__(self, file_path: str, buffer_size: int = 1000):
        self.file_path = file_path
        self.buffer_size = buffer_size
        self.buffer = []
        self.timestamps = []
        self.delays = []
        self.file_handle = None
        
    async def __aenter__(self):
        self.file_handle = open(self.file_path, 'r')
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.file_handle:
            self.file_handle.close()
    
    async def read_next_batch(self):
        """Read next batch of JSON lines"""
        batch = []
        timestamps = []
        
        for _ in range(self.buffer_size):
            line = self.file_handle.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                json_obj = json.loads(line)
                batch.append(json_obj)
                # Extract timestamp here
                # ...
            except json.JSONDecodeError:
                continue
        
        return batch, timestamps
```

This implementation plan provides a comprehensive guide for building the pose_replayer.py script with all the required functionality.