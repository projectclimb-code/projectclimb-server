#!/usr/bin/env python
"""
Test script for the wall image upload API endpoint.
This script tests the api_upload_wall_image endpoint with a base64 encoded image.
"""

import base64
import json
import requests
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000/api/upload-wall-image/"
# Use one of the existing wall UUIDs from the database
WALL_ID = "264d7633-65b2-41a8-92a4-34eb79a891bb"  # "Rdeče-kvadratna stena"
# Replace with valid credentials for authentication
USERNAME = "admin"
PASSWORD = "admin"

def get_auth_token():
    """Get authentication token from Django."""
    # First, get CSRF token
    session = requests.Session()
    session.get("http://localhost:8000/admin/")
    
    # Login to get session cookie
    login_data = {
        'username': USERNAME,
        'password': PASSWORD,
        'csrfmiddlewaretoken': session.cookies.get('csrftoken', '')
    }
    
    login_response = session.post("http://localhost:8000/admin/login/", data=login_data)
    
    if login_response.status_code != 200:
        print(f"Login failed with status: {login_response.status_code}")
        return None
    
    return session

def test_upload_endpoint():
    """Test the wall image upload endpoint."""
    # Get an existing image file to test with
    image_path = Path("data/IMG_2568.jpeg")  # Update with actual image path
    
    if not image_path.exists():
        print(f"Test image not found at {image_path}")
        print("Please update the image_path variable to point to an existing image file.")
        return
    
    # Read and encode the image
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Prepare the request data
    payload = {
        'wall_id': WALL_ID,
        'image_data': f"data:image/jpeg;base64,{image_data}"
    }
    
    # Get authenticated session
    session = get_auth_token()
    if not session:
        print("Authentication failed")
        return
    
    # Make the API request
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': session.cookies.get('csrftoken', '')
    }
    
    print(f"Testing API endpoint: {API_URL}")
    print(f"Wall ID: {WALL_ID}")
    print(f"Image size: {len(image_data)} characters")
    
    try:
        response = session.post(API_URL, json=payload, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Test PASSED: Image uploaded successfully")
                print(f"Image URL: {result.get('image_url')}")
            else:
                print(f"❌ Test FAILED: {result.get('error')}")
        else:
            print(f"❌ Test FAILED: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test FAILED with exception: {str(e)}")

def test_invalid_requests():
    """Test the endpoint with invalid requests."""
    session = get_auth_token()
    if not session:
        print("Authentication failed for invalid request tests")
        return
    
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': session.cookies.get('csrftoken', '')
    }
    
    # Test 1: Missing wall_id
    print("\n--- Testing with missing wall_id ---")
    payload = {'image_data': 'data:image/jpeg;base64,invalid'}
    response = session.post(API_URL, json=payload, headers=headers)
    print(f"Status: {response.status_code}, Response: {response.text}")
    
    # Test 2: Missing image_data
    print("\n--- Testing with missing image_data ---")
    payload = {'wall_id': WALL_ID}
    response = session.post(API_URL, json=payload, headers=headers)
    print(f"Status: {response.status_code}, Response: {response.text}")
    
    # Test 3: Invalid wall_id
    print("\n--- Testing with invalid wall_id ---")
    payload = {
        'wall_id': 'invalid-uuid',
        'image_data': 'data:image/jpeg;base64,invalid'
    }
    response = session.post(API_URL, json=payload, headers=headers)
    print(f"Status: {response.status_code}, Response: {response.text}")
    
    # Test 4: Invalid image data
    print("\n--- Testing with invalid image data ---")
    payload = {
        'wall_id': WALL_ID,
        'image_data': 'data:image/jpeg;base64,invalid-base64-data'
    }
    response = session.post(API_URL, json=payload, headers=headers)
    print(f"Status: {response.status_code}, Response: {response.text}")

if __name__ == "__main__":
    print("=== Testing Wall Image Upload API Endpoint ===")
    test_upload_endpoint()
    test_invalid_requests()
    print("\n=== Test Complete ===")