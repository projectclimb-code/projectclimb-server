#!/usr/bin/env python3
"""
Simple test script for pose_replayer.py without external dependencies
"""

import os
import sys
import json
import tempfile
import asyncio

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pose_replayer import JsonsFileReader, PoseReplayer


async def test_file_reader():
    """Test the file reader functionality"""
    print("Testing JsonsFileReader...")
    
    # Create test file with sample data
    test_content = [
        {"timestamp": 1000.0, "data": "test1", "landmarks": [{"x": 0.5, "y": 0.5}]},
        {"timestamp": 1002.5, "data": "test2", "landmarks": [{"x": 0.6, "y": 0.6}]},
        {"timestamp": 1005.0, "data": "test3", "landmarks": [{"x": 0.7, "y": 0.7}]}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    try:
        # Test file reader
        reader = JsonsFileReader(test_file)
        await reader.load_file()
        
        print(f"✓ Loaded {len(reader.json_data)} messages")
        
        # Test timestamp extraction
        timestamps = reader.extract_timestamps()
        print(f"✓ Timestamps: {timestamps}")
        
        # Test delay calculation
        delays = reader.calculate_delays()
        print(f"✓ Delays: {delays}")
        
        # Verify results
        assert len(reader.json_data) == 3
        assert timestamps == [1000.0, 1002.5, 1005.0]
        assert delays == [0.0, 2.5, 2.5]
        
        print("✓ All tests passed!")
        
    finally:
        # Clean up
        os.unlink(test_file)


async def test_pose_replayer_setup():
    """Test the pose replayer setup"""
    print("\nTesting PoseReplayer setup...")
    
    # Create test file with sample data
    test_content = [
        {"timestamp": 1000.0, "data": "test1"},
        {"timestamp": 1001.0, "data": "test2"},
        {"timestamp": 1002.0, "data": "test3"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    try:
        # Test replayer setup
        replayer = PoseReplayer(
            file_path=test_file,
            websocket_url="ws://localhost:9999",  # Non-existent endpoint
            loop=False
        )
        
        await replayer.setup()
        
        print(f"✓ Setup complete with {len(replayer.file_reader.json_data)} messages")
        print(f"✓ Total replay duration: {sum(replayer.delays):.2f} seconds")
        
        # Verify results
        assert len(replayer.file_reader.json_data) == 3
        assert len(replayer.delays) == 3
        assert replayer.delays == [0.0, 1.0, 1.0]
        
        print("✓ All tests passed!")
        
    finally:
        # Clean up
        os.unlink(test_file)


async def test_iso_timestamps():
    """Test with ISO format timestamps"""
    print("\nTesting ISO timestamp parsing...")
    
    # Create test file with ISO timestamps
    test_content = [
        {"timestamp": "2025-01-01T12:00:00Z", "data": "test1"},
        {"timestamp": "2025-01-01T12:00:02.500Z", "data": "test2"},
        {"timestamp": "2025-01-01T12:00:05Z", "data": "test3"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    try:
        # Test file reader
        reader = JsonsFileReader(test_file)
        await reader.load_file()
        timestamps = reader.extract_timestamps()
        
        print(f"✓ Loaded {len(reader.json_data)} messages")
        print(f"✓ ISO timestamps converted to: {timestamps[:3]}...")  # Show first 3
        
        # Verify timestamps are increasing
        assert len(timestamps) == 3
        assert timestamps[1] > timestamps[0]
        assert timestamps[2] > timestamps[1]
        
        print("✓ All tests passed!")
        
    finally:
        # Clean up
        os.unlink(test_file)


async def main():
    """Run all tests"""
    print("Running simple tests for pose_replayer.py")
    print("=" * 50)
    
    try:
        await test_file_reader()
        await test_pose_replayer_setup()
        await test_iso_timestamps()
        
        print("\n" + "=" * 50)
        print("All tests passed successfully!")
        print("\nThe pose_replayer.py script is ready to use!")
        print("\nExample usage:")
        print("  uv run python pose_replayer.py \\")
        print("    --file 2025-11-13_pleza.jsons \\")
        print("    --websocket ws://localhost:8000/ws/pose/ \\")
        print("    --timestamp-field timestamp \\")
        print("    --loop \\")
        print("    --debug")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)