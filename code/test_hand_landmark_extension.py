#!/usr/bin/env python
"""
Test script for the hand landmark extension functionality.
"""

import json
import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

from climber.management.commands.websocket_pose_transformer_with_hand_landmarks import calculate_extended_hand_landmarks


def create_test_landmarks():
    """Create test pose landmarks with hand data"""
    # Create a minimal set of landmarks for testing
    landmarks = []
    
    # Add all 33 MediaPipe pose landmarks with dummy data
    for i in range(33):
        landmarks.append({
            'x': 0.5 + i * 0.01,
            'y': 0.5 + i * 0.01,
            'z': 0.0,
            'visibility': 0.9
        })
    
    # Set specific hand landmarks with more realistic values
    # Left hand
    landmarks[13] = {'x': 0.3, 'y': 0.4, 'z': -0.1, 'visibility': 0.9}  # LEFT_ELBOW
    landmarks[15] = {'x': 0.25, 'y': 0.6, 'z': -0.2, 'visibility': 0.9}  # LEFT_WRIST
    landmarks[17] = {'x': 0.2, 'y': 0.65, 'z': -0.25, 'visibility': 0.9}  # LEFT_PINKY
    landmarks[19] = {'x': 0.3, 'y': 0.62, 'z': -0.22, 'visibility': 0.9}  # LEFT_INDEX
    landmarks[21] = {'x': 0.22, 'y': 0.58, 'z': -0.18, 'visibility': 0.9}  # LEFT_THUMB
    
    # Right hand
    landmarks[14] = {'x': 0.7, 'y': 0.4, 'z': -0.1, 'visibility': 0.9}  # RIGHT_ELBOW
    landmarks[16] = {'x': 0.75, 'y': 0.6, 'z': -0.2, 'visibility': 0.9}  # RIGHT_WRIST
    landmarks[18] = {'x': 0.8, 'y': 0.65, 'z': -0.25, 'visibility': 0.9}  # RIGHT_PINKY
    landmarks[20] = {'x': 0.7, 'y': 0.62, 'z': -0.22, 'visibility': 0.9}  # RIGHT_INDEX
    landmarks[22] = {'x': 0.78, 'y': 0.58, 'z': -0.18, 'visibility': 0.9}  # RIGHT_THUMB
    
    return landmarks


def test_hand_landmark_extension():
    """Test the hand landmark extension functionality"""
    print("Testing hand landmark extension...")
    
    # Create test landmarks
    landmarks = create_test_landmarks()
    
    # Test with different extension percentages
    for extension_percent in [10.0, 20.0, 50.0]:
        print(f"\nTesting with {extension_percent}% extension:")
        
        # Calculate extended landmarks
        extended_landmarks = calculate_extended_hand_landmarks(landmarks, extension_percent)
        
        print(f"Number of extended landmarks: {len(extended_landmarks)}")
        
        for i, landmark in enumerate(extended_landmarks):
            print(f"  Extended landmark {i}: x={landmark['x']:.4f}, y={landmark['y']:.4f}, z={landmark['z']:.4f}")
        
        # Verify the landmarks are extended in the right direction
        if len(extended_landmarks) >= 2:
            # Left hand extension should be further from elbow than palm center
            left_palm_center_x = (landmarks[15]['x'] + landmarks[17]['x'] + landmarks[19]['x'] + landmarks[21]['x']) / 4
            left_palm_center_y = (landmarks[15]['y'] + landmarks[17]['y'] + landmarks[19]['y'] + landmarks[21]['y']) / 4
            
            # Check if the extended landmark is further from the elbow than the palm center
            left_elbow_to_palm_dist = ((left_palm_center_x - landmarks[13]['x'])**2 + 
                                      (left_palm_center_y - landmarks[13]['y'])**2)**0.5
            left_elbow_to_extended_dist = ((extended_landmarks[0]['x'] - landmarks[13]['x'])**2 + 
                                          (extended_landmarks[0]['y'] - landmarks[13]['y'])**2)**0.5
            
            print(f"  Left hand: elbow-to-palm distance = {left_elbow_to_palm_dist:.4f}")
            print(f"  Left hand: elbow-to-extended distance = {left_elbow_to_extended_dist:.4f}")
            
            if left_elbow_to_extended_dist > left_elbow_to_palm_dist:
                print("  ✓ Left hand extension is correctly positioned beyond the palm")
            else:
                print("  ✗ Left hand extension is not correctly positioned")
    
    print("\nTest completed!")


if __name__ == "__main__":
    test_hand_landmark_extension()