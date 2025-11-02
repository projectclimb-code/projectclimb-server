#!/usr/bin/env python3
"""
Test script to verify go2rtc camera configuration.
This script will:
1. Check if go2rtc is running
2. Test camera stream configuration
3. Verify stream accessibility
"""

import requests
import json
import time
import sys

def test_go2rtc_connection(go2rtc_url="http://localhost:1984"):
    """Test if go2rtc is running and accessible."""
    try:
        response = requests.get(f"{go2rtc_url}/api/info", timeout=5)
        if response.status_code == 200:
            print("✓ go2rtc is running and accessible")
            return True
        else:
            print(f"✗ go2rtc returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Cannot connect to go2rtc: {e}")
        print("  Make sure docker-compose up go2rtc is running")
        return False

def test_stream_configuration(go2rtc_url="http://localhost:1984"):
    """Test if the camera stream is properly configured."""
    try:
        response = requests.get(f"{go2rtc_url}/api/streams", timeout=5)
        if response.status_code == 200:
            streams = response.json()
            print("✓ Retrieved stream configurations")
            
            # Check if camera stream exists
            if "camera" in streams:
                print("✓ Camera stream is configured")
                print(f"  Stream config: {streams['camera']}")
                return True
            else:
                print("✗ Camera stream not found in configuration")
                print("  Available streams:", list(streams.keys()))
                return False
        else:
            print(f"✗ Failed to get streams: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Error getting stream configuration: {e}")
        return False

def test_stream_access(go2rtc_url="http://localhost:1984"):
    """Test if the camera stream can be accessed."""
    stream_url = f"{go2rtc_url}/stream.mp4?src=camera"
    
    try:
        # Make a request to the stream endpoint
        response = requests.get(stream_url, timeout=10, stream=True)
        if response.status_code == 200:
            print("✓ Camera stream is accessible")
            print(f"  Stream URL: {stream_url}")
            
            # Try to read a small chunk of data
            chunk = next(response.iter_content(chunk_size=1024), None)
            if chunk:
                print("✓ Stream data is being received")
                return True
            else:
                print("✗ No data received from stream")
                return False
        else:
            print(f"✗ Stream returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Error accessing stream: {e}")
        return False

def test_web_ui(go2rtc_url="http://localhost:1984"):
    """Test if the go2rtc web UI is accessible."""
    try:
        response = requests.get(f"{go2rtc_url}/", timeout=5)
        if response.status_code == 200:
            print("✓ go2rtc web UI is accessible")
            print(f"  Web UI URL: {go2rtc_url}/")
            return True
        else:
            print(f"✗ Web UI returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Error accessing web UI: {e}")
        return False

def main():
    print("Testing go2rtc camera configuration...\n")
    
    go2rtc_url = "http://localhost:1984"
    
    # Run tests
    tests = [
        ("go2rtc Connection", lambda: test_go2rtc_connection(go2rtc_url)),
        ("Stream Configuration", lambda: test_stream_configuration(go2rtc_url)),
        ("Stream Access", lambda: test_stream_access(go2rtc_url)),
        ("Web UI Access", lambda: test_web_ui(go2rtc_url))
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- Testing {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n✓ All tests passed! Your go2rtc configuration is working correctly.")
        print("\nYou can now:")
        print(f"  - Access the web UI at: {go2rtc_url}/")
        print(f"  - Access the camera stream at: {go2rtc_url}/stream.mp4?src=camera")
        print(f"  - Access the RTSP stream at: rtsp://localhost:8554/camera")
    else:
        print("\n✗ Some tests failed. Please check the configuration.")
        print("\nTroubleshooting:")
        print("  1. Make sure docker-compose up go2rtc is running")
        print("  2. Check if your camera is connected and accessible")
        print("  3. Verify /dev/video0 exists (on Linux/macOS)")
        print("  4. Check docker logs with: docker-compose logs go2rtc")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())