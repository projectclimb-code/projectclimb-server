# Pose Replayer Script Design

## Overview
The `pose_replayer.py` script will read pose data from a JSONS file (JSON Lines format) and replay it to a WebSocket endpoint with proper timing based on timestamps in the data. The script will loop indefinitely when reaching the end of the file.

## Requirements
1. Read a file containing multiple JSON objects, one per line (JSONS format)
2. Connect to a WebSocket endpoint specified as a parameter
3. Send each JSON object to the WebSocket endpoint
4. Maintain timing based on timestamps in the JSON data
5. Loop forever when reaching the end of the file
6. Handle connection errors gracefully

## Architecture

### Components
1. **File Reader**: Reads and parses JSON lines from the input file
2. **WebSocket Client**: Manages connection to the output WebSocket endpoint
3. **Timing Controller**: Calculates and maintains proper delays between messages
4. **Main Controller**: Orchestrates the replay process and looping

### Data Flow
```
Input File → File Reader → Timing Controller → WebSocket Client → Output Endpoint
     ↑                                                          ↓
     └─────────────────── Loop Back ──────────────────────────────┘
```

## Implementation Details

### 1. Command Line Arguments
- `--file`: Path to the input JSONS file (required)
- `--websocket`: WebSocket endpoint URL (required)
- `--timestamp-field`: Field name containing timestamp (default: "timestamp")
- `--loop`: Whether to loop indefinitely (default: True)
- `--debug`: Enable debug logging (default: False)
- `--reconnect-delay`: Delay between reconnection attempts in seconds (default: 5.0)

### 2. JSON Data Format
Based on the existing codebase, the JSON data likely contains:
- Pose landmarks data
- Timestamp information
- Possibly session metadata

The script should be flexible enough to handle different JSON structures as long as they contain a timestamp field.

### 3. WebSocket Implementation
Using the `websockets` library (already in requirements.txt):
- Async WebSocket client with reconnection logic
- Message queue for reliable delivery
- Connection state monitoring

### 4. Timing Logic
- Parse timestamp from each JSON object
- Calculate delay between consecutive messages
- Use `asyncio.sleep()` for precise timing
- Handle edge cases (missing timestamps, out-of-order data)

### 5. Error Handling
- File not found or read errors
- WebSocket connection failures
- Invalid JSON format
- Missing timestamp fields
- Network interruptions

## Code Structure

```python
import asyncio
import json
import argparse
import time
from datetime import datetime
from typing import List, Dict, Optional
import websockets
from loguru import logger

class PoseReplayer:
    def __init__(self, file_path: str, websocket_url: str, 
                 timestamp_field: str = "timestamp", 
                 loop: bool = True,
                 reconnect_delay: float = 5.0):
        # Initialize attributes
        
    async def connect_websocket(self):
        # Connect to WebSocket with reconnection logic
        
    async def read_json_lines(self) -> List[Dict]:
        # Read and parse all JSON lines from file
        
    def calculate_delays(self, json_data: List[Dict]) -> List[float]:
        # Calculate delays between messages based on timestamps
        
    async def replay_data(self):
        # Main replay loop with timing
        
    async def run(self):
        # Main entry point
```

## Usage Example
```bash
python pose_replayer.py \
  --file 2025-11-13_pleza.jsons \
  --websocket ws://localhost:8000/ws/pose/ \
  --timestamp-field timestamp \
  --loop \
  --debug
```

## Integration with Existing Codebase
The script will follow patterns established in:
- `websocket_pose_session_tracker.py` for WebSocket client implementation
- Use `loguru` for logging (already in requirements)
- Follow the project's error handling patterns
- Use similar async/await patterns

## Testing Strategy
1. Unit tests for each component
2. Integration test with sample WebSocket server
3. Test with actual JSONS file
4. Test reconnection logic
5. Test timing accuracy

## Edge Cases to Handle
1. Empty input file
2. Missing timestamp field
3. Invalid JSON format
4. WebSocket connection drops during replay
5. Timestamps not in chronological order
6. Very large files that don't fit in memory

## Performance Considerations
1. Stream file reading for large files
2. Batch JSON parsing if needed
3. Memory-efficient message queuing
4. Optimize timing calculations

## Future Enhancements
1. Speed control (replay faster/slower than original)
2. Start/stop/pause controls
3. Real-time status reporting
4. GUI interface
5. Support for multiple output endpoints