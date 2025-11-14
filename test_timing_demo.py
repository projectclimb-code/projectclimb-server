#!/usr/bin/env python3
"""
Demo script to show timing output of pose_replayer.py with debug logging
"""

import os
import sys
import json
import tempfile
import asyncio

# Add to project root
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pose_replayer import JsonsFileReader, PoseReplayer


async def demo_timing():
    """Demonstrate timing with debug output"""
    print("Creating demo file with timestamps...")
    
    # Create test file with specific timing
    test_content = [
        {"timestamp": 1000.0, "data": "First message (immediate)"},
        {"timestamp": 1002.0, "data": "Second message (2s delay)"},
        {"timestamp": 1003.5, "data": "Third message (1.5s delay)"},
        {"timestamp": 1006.5, "data": "Fourth message (3s delay)"},
        {"timestamp": 1007.0, "data": "Fifth message (0.5s delay)"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    print(f"Created test file: {test_file}")
    print("\nFile content:")
    for i, item in enumerate(test_content):
        print(f"  Line {i+1}: timestamp={item['timestamp']}, data='{item['data']}'")
    
    # Test file reader
    reader = JsonsFileReader(test_file)
    await reader.load_file()
    timestamps = reader.extract_timestamps()
    delays = reader.calculate_delays()
    
    print("\nExtracted timestamps:", timestamps)
    print("Calculated delays:", delays)
    
    print("\nExpected timing:")
    print("  Message 1: Send immediately")
    print("  Wait 2.0s")
    print("  Message 2: Send")
    print("  Wait 1.5s")
    print("  Message 3: Send")
    print("  Wait 3.0s")
    print("  Message 4: Send")
    print("  Wait 0.5s")
    print("  Message 5: Send")
    print("  End of cycle")
    
    # Create replayer with debug enabled
    replayer = PoseReplayer(
        file_path=test_file,
        websocket_url="ws://localhost:9999",  # Non-existent endpoint
        loop=False,
        debug=True
    )
    
    print("\n" + "="*50)
    print("Starting replayer with debug logging...")
    print("(Note: WebSocket will fail to connect, but we'll see timing logs)")
    print("="*50)
    
    try:
        # Setup will work even without WebSocket connection
        await replayer.setup()
        
        # Run just one cycle to show timing
        json_data = replayer.file_reader.json_data
        delays = replayer.delays
        
        print("\nReplay simulation:")
        for i, (message, delay) in enumerate(zip(json_data, delays)):
            print(f"\nMessage {i+1}: {message['data']}")
            
            if i == 0:
                print("  -> Sending immediately (delay = 0.0s)")
            else:
                print(f"  -> Waiting {delay:.3f}s until next message...")
                # Simulate the wait
                await asyncio.sleep(0.1)  # Shortened for demo
        
        print("\nEnd of demo")
        
    finally:
        # Clean up
        os.unlink(test_file)


if __name__ == "__main__":
    asyncio.run(demo_timing())