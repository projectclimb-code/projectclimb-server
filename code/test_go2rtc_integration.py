#!/usr/bin/env python3
"""
Test script for go2rtc integration.
This script tests the go2rtc setup and stream configuration.
"""

import requests
import time
import sys
import argparse

def test_go2rtc_connection(go2rtc_url="http://localhost:1984"):
    """Test if go2rtc is running and accessible."""
    print(f"Testing go2rtc connection at {go2rtc_url}...")
    try:
        response = requests.get(f"{go2rtc_url}/api/info", timeout=5)
        if response.status_code == 200:
            print("✓ go2rtc is running and accessible")
            return True
        else:
            print(f"✗ go2rtc returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Failed to connect to go2rtc: {e}")
        return False

def test_stream_configuration(go2rtc_url="http://localhost:1984", stream_name="camera"):
    """Test if the camera stream is configured."""
    print(f"Testing stream configuration for '{stream_name}'...")
    try:
        response = requests.get(f"{go2rtc_url}/api/streams", timeout=5)
        if response.status_code == 200:
            streams = response.json()
            if stream_name in streams:
                print(f"✓ Stream '{stream_name}' is configured")
                print(f"  Source: {streams[stream_name].get('src', 'Unknown')}")
                return True
            else:
                print(f"✗ Stream '{stream_name}' is not configured")
                return False
        else:
            print(f"✗ Failed to get streams: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Failed to connect to go2rtc: {e}")
        return False

def test_stream_accessibility(go2rtc_url="http://localhost:1984", stream_name="camera"):
    """Test if the stream is accessible."""
    print(f"Testing stream accessibility for '{stream_name}'...")
    stream_url = f"{go2rtc_url}/stream.mp4?src={stream_name}"
    try:
        # Just check if we can start downloading the stream
        response = requests.get(stream_url, stream=True, timeout=5)
        if response.status_code == 200:
            print("✓ Stream is accessible")
            return True
        else:
            print(f"✗ Stream returned status code: {response.status_code}")
            return False
    except requests.exceptions.ChunkedEncodingError:
        # This is expected for a video stream - it means the stream is working
        print("✓ Stream is accessible (chunked encoding)")
        return True
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Failed to access stream: {e}")
        return False

def test_django_connection(django_url="http://localhost:8012"):
    """Test if Django is running."""
    print(f"Testing Django connection at {django_url}...")
    try:
        response = requests.get(f"{django_url}/", timeout=5)
        if response.status_code == 200:
            print("✓ Django is running and accessible")
            return True
        else:
            print(f"✗ Django returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Failed to connect to Django: {e}")
        return False

def test_camera_page(django_url="http://localhost:8012"):
    """Test if the camera page is accessible."""
    print(f"Testing camera page at {django_url}/camera/...")
    try:
        response = requests.get(f"{django_url}/camera/", timeout=5)
        if response.status_code == 200:
            print("✓ Camera page is accessible")
            return True
        else:
            print(f"✗ Camera page returned status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"✗ Failed to access camera page: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test go2rtc integration")
    parser.add_argument("--go2rtc-url", default="http://localhost:1984", help="go2rtc URL")
    parser.add_argument("--django-url", default="http://localhost:8012", help="Django URL")
    parser.add_argument("--stream-name", default="camera", help="Stream name")
    
    args = parser.parse_args()
    
    print("Starting go2rtc integration tests...\n")
    
    all_tests_passed = True
    
    # Test go2rtc connection
    if not test_go2rtc_connection(args.go2rtc_url):
        all_tests_passed = False
        print("\nPlease start go2rtc with: docker-compose up go2rtc")
        sys.exit(1)
    
    print()
    
    # Test stream configuration
    if not test_stream_configuration(args.go2rtc_url, args.stream_name):
        all_tests_passed = False
        print("\nPlease configure the stream with: uv run python start_go2rtc_stream.py")
        sys.exit(1)
    
    print()
    
    # Test stream accessibility
    if not test_stream_accessibility(args.go2rtc_url, args.stream_name):
        all_tests_passed = False
        print("\nStream is not accessible. Check camera permissions and configuration.")
    
    print()
    
    # Test Django connection
    if not test_django_connection(args.django_url):
        all_tests_passed = False
        print("\nPlease start Django with: uv run python manage.py runserver 8012")
        sys.exit(1)
    
    print()
    
    # Test camera page
    if not test_camera_page(args.django_url):
        all_tests_passed = False
        print("\nCamera page is not accessible.")
    
    print()
    
    if all_tests_passed:
        print("✓ All tests passed! The go2rtc integration is working correctly.")
        print(f"\nYou can access the camera stream at: {args.django_url}/camera/")
        print(f"Direct stream URL: {args.go2rtc_url}/stream.mp4?src={args.stream_name}")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()