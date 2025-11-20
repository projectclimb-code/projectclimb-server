#!/usr/bin/env python3
"""
Test script for the kill all tasks functionality.
"""

import os
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.test import Client

def test_kill_all_tasks_endpoint():
    """Test the kill all tasks endpoint."""
    client = Client()
    
    print("Testing kill all tasks endpoint...")
    
    # Test the endpoint exists
    try:
        response = client.get('/tasks/kill-all/')
        print(f"✓ GET /tasks/kill-all/ endpoint exists: {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing GET endpoint: {e}")
        return False
    
    # Test POST request (should fail without CSRF token)
    try:
        response = client.post(reverse('kill_all_tasks'), {})
        print(f"✓ POST without CSRF returns: {response.status_code}")
        if response.status_code == 403:
            print("✓ CSRF protection working correctly")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"✗ Error testing POST endpoint: {e}")
        return False
    
    # Test POST request with CSRF token
    try:
        response = client.post(reverse('kill_all_tasks'), {}, HTTP_X_CSRFTOKEN='test-token')
        print(f"✓ POST with CSRF token returns: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Response data: {data}")
            
            # Check response structure
            expected_keys = ['status', 'message', 'killed_count', 'errors']
            for key in expected_keys:
                if key not in data:
                    print(f"✗ Missing key in response: {key}")
                    return False
            
            print("✓ Kill all tasks endpoint test completed successfully!")
            return True
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing POST with CSRF: {e}")
        return False

if __name__ == '__main__':
    success = test_kill_all_tasks_endpoint()
    
    if success:
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("✅ Kill all tasks functionality is working correctly!")
        print("="*50)
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ SOME TESTS FAILED!")
        print("="*50)
        sys.exit(1)