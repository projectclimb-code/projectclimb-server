#!/usr/bin/env python3
"""
Test script for pose_replayer.py
"""

import os
import sys
import json
import asyncio
import tempfile
import websockets
from unittest.mock import AsyncMock, patch
import pytest

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pose_replayer import JsonsFileReader, WebSocketClient, PoseReplayer


class TestJsonsFileReader:
    """Test cases for JsonsFileReader class"""
    
    @pytest.fixture
    def sample_jsons_file(self):
        """Create a temporary JSONS file with sample data"""
        content = [
            {"timestamp": 1000.0, "data": "message1", "landmarks": [{"x": 0.5, "y": 0.5}]},
            {"timestamp": 1002.5, "data": "message2", "landmarks": [{"x": 0.6, "y": 0.6}]},
            {"timestamp": 1005.0, "data": "message3", "landmarks": [{"x": 0.7, "y": 0.7}]}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
            for item in content:
                f.write(json.dumps(item) + '\n')
            return f.name
    
    @pytest.fixture
    def iso_timestamp_file(self):
        """Create a temporary JSONS file with ISO timestamps"""
        content = [
            {"timestamp": "2025-01-01T12:00:00Z", "data": "message1"},
            {"timestamp": "2025-01-01T12:00:02.500Z", "data": "message2"},
            {"timestamp": "2025-01-01T12:00:05Z", "data": "message3"}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
            for item in content:
                f.write(json.dumps(item) + '\n')
            return f.name
    
    @pytest.mark.asyncio
    async def test_file_reading(self, sample_jsons_file):
        """Test reading JSONS file"""
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        
        assert len(reader.json_data) == 3
        assert reader.json_data[0]["data"] == "message1"
        assert reader.json_data[1]["data"] == "message2"
        assert reader.json_data[2]["data"] == "message3"
        
        # Clean up
        os.unlink(sample_jsons_file)
    
    @pytest.mark.asyncio
    async def test_timestamp_extraction_float(self, sample_jsons_file):
        """Test timestamp extraction with float timestamps"""
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        timestamps = reader.extract_timestamps()
        
        assert timestamps == [1000.0, 1002.5, 1005.0]
        
        # Clean up
        os.unlink(sample_jsons_file)
    
    @pytest.mark.asyncio
    async def test_timestamp_extraction_iso(self, iso_timestamp_file):
        """Test timestamp extraction with ISO timestamps"""
        reader = JsonsFileReader(iso_timestamp_file)
        await reader.load_file()
        timestamps = reader.extract_timestamps()
        
        # Convert to expected Unix timestamps (approximate)
        assert len(timestamps) == 3
        assert timestamps[0] > 0  # Should be a valid Unix timestamp
        assert timestamps[1] > timestamps[0]  # Should be increasing
        assert timestamps[2] > timestamps[1]  # Should be increasing
        
        # Clean up
        os.unlink(iso_timestamp_file)
    
    @pytest.mark.asyncio
    async def test_delay_calculation(self, sample_jsons_file):
        """Test delay calculation between messages"""
        reader = JsonsFileReader(sample_jsons_file)
        await reader.load_file()
        reader.extract_timestamps()
        delays = reader.calculate_delays()
        
        assert delays == [0.0, 2.5, 2.5]
        
        # Clean up
        os.unlink(sample_jsons_file)


class TestWebSocketClient:
    """Test cases for WebSocketClient class"""
    
    @pytest.mark.asyncio
    async def test_message_queueing(self):
        """Test message queueing functionality"""
        client = WebSocketClient("ws://localhost:8000")
        
        # Mock the websocket connection
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value = mock_websocket
            
            # Start client
            client.running = True
            sender_task = asyncio.create_task(client.message_sender())
            
            # Queue a message
            test_message = {"test": "data"}
            await client.send_message(test_message)
            
            # Give some time for processing
            await asyncio.sleep(0.1)
            
            # Stop the client
            client.running = False
            sender_task.cancel()
            
            try:
                await sender_task
            except asyncio.CancelledError:
                pass
            
            # Check message was queued
            assert not client.message_queue.empty()


class TestPoseReplayer:
    """Test cases for PoseReplayer class"""
    
    @pytest.fixture
    def sample_jsons_file(self):
        """Create a temporary JSONS file with sample data"""
        content = [
            {"timestamp": 1000.0, "data": "message1"},
            {"timestamp": 1001.0, "data": "message2"},
            {"timestamp": 1002.0, "data": "message3"}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
            for item in content:
                f.write(json.dumps(item) + '\n')
            return f.name
    
    @pytest.mark.asyncio
    async def test_setup(self, sample_jsons_file):
        """Test replayer setup"""
        replayer = PoseReplayer(
            file_path=sample_jsons_file,
            websocket_url="ws://localhost:8000",
            loop=False
        )
        
        await replayer.setup()
        
        assert len(replayer.file_reader.json_data) == 3
        assert len(replayer.delays) == 3
        assert replayer.delays == [0.0, 1.0, 1.0]
        
        # Clean up
        os.unlink(sample_jsons_file)


def run_integration_test():
    """Run a simple integration test"""
    print("Running integration test...")
    
    # Create test file
    test_content = [
        {"timestamp": 1000.0, "data": "test1", "landmarks": [{"x": 0.5, "y": 0.5}]},
        {"timestamp": 1001.0, "data": "test2", "landmarks": [{"x": 0.6, "y": 0.6}]},
        {"timestamp": 1002.0, "data": "test3", "landmarks": [{"x": 0.7, "y": 0.7}]}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsons', delete=False) as f:
        for item in test_content:
            f.write(json.dumps(item) + '\n')
        test_file = f.name
    
    try:
        # Test file reader
        reader = JsonsFileReader(test_file)
        asyncio.run(reader.load_file())
        timestamps = reader.extract_timestamps()
        delays = reader.calculate_delays()
        
        print(f"✓ Loaded {len(reader.json_data)} messages")
        print(f"✓ Timestamps: {timestamps}")
        print(f"✓ Delays: {delays}")
        
        # Test replayer setup
        replayer = PoseReplayer(
            file_path=test_file,
            websocket_url="ws://localhost:9999",  # Non-existent endpoint
            loop=False
        )
        
        asyncio.run(replayer.setup())
        print("✓ Replayer setup successful")
        
        print("Integration test passed!")
        
    finally:
        # Clean up
        os.unlink(test_file)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--integration":
        run_integration_test()
    else:
        print("Run with --integration flag to run integration test")
        print("Or use pytest to run unit tests:")
        print("  pytest test_pose_replayer.py -v")