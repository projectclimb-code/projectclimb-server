#!/usr/bin/env python3
"""
Test script to verify millisecond timestamp handling
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


async def test_millisecond_handling():
    """Test handling of millisecond timestamps"""
    print("Testing millisecond timestamp handling...")
    
    # Create test file with millisecond timestamps
    test_content = [
        {"timestamp": 1000, "data": "Message at 1 second"},
        {"timestamp": 1500, "data": "Message at 1.5 seconds"},
        {"timestamp": 2000, "data": "Message at 2 seconds"},
        {"timestamp": 2500, "data": "Message at 2.5 seconds"},
        {"timestamp": 3000, "data": "Message at 3 seconds"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    print(f"\nCreated test file with millisecond timestamps: {test_file}")
    print("\nFile content:")
    for i, item in enumerate(test_content):
        print(f"  Line {i+1}: timestamp={item['timestamp']}ms, data='{item['data']}'")
    
    # Test file reader
    reader = JsonsFileReader(test_file)
    await reader.load_file()
    timestamps = reader.extract_timestamps()
    delays = reader.calculate_delays()
    
    print("\nExtracted timestamps (seconds):", timestamps)
    print("Calculated delays (seconds):", delays)
    
    print("\nExpected delays:")
    print("  Message 1: 0.0s (immediate)")
    print("  Message 2: 0.5s (1500ms - 1000ms = 500ms = 0.5s)")
    print("  Message 3: 0.5s (2000ms - 1500ms = 500ms = 0.5s)")
    print("  Message 4: 0.5s (2500ms - 2000ms = 500ms = 0.5s)")
    print("  Message 5: 0.5s (3000ms - 2500ms = 500ms = 0.5s)")
    
    # Verify calculations
    expected_delays = [0.0, 0.5, 0.5, 0.5, 0.5]
    
    print("\nVerification:")
    for i, (actual, expected) in enumerate(zip(delays, expected_delays)):
        if abs(actual - expected) < 0.001:  # Allow small floating point differences
            print(f"  ✓ Delay {i+1}: {actual:.3f}s (expected {expected:.3f}s)")
        else:
            print(f"  ✗ Delay {i+1}: {actual:.3f}s (expected {expected:.3f}s)")
    
    # Test with actual data file
    print("\n" + "="*50)
    print("Testing with actual data file...")
    
    # Check if actual file exists
    actual_file = "2025-11-13_pleza.jsons"
    if os.path.exists(actual_file):
        print(f"Found actual file: {actual_file}")
        
        # Read first few lines to check format
        with open(actual_file, 'r') as f:
            print("\nFirst 3 lines of actual file:")
            for i, line in enumerate(f):
                if i >= 3:
                    break
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        print(f"  Line {i+1}: {json.dumps(data)[:100]}...")
                    except json.JSONDecodeError:
                        print(f"  Line {i+1}: Invalid JSON")
        
        # Test with actual file
        actual_reader = JsonsFileReader(actual_file)
        await actual_reader.load_file()
        actual_timestamps = actual_reader.extract_timestamps()
        actual_delays = actual_reader.calculate_delays()
        
        print(f"\nLoaded {len(actual_reader.json_data)} messages from actual file")
        if len(actual_timestamps) > 0:
            print(f"First timestamp: {actual_timestamps[0]}")
            print(f"Second timestamp: {actual_timestamps[1]}")
            print(f"First delay: {actual_delays[1]:.3f}s")
    else:
        print(f"Actual file not found: {actual_file}")
    
    # Clean up
    os.unlink(test_file)


if __name__ == "__main__":
    asyncio.run(test_millisecond_handling())