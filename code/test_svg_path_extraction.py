#!/usr/bin/env python3
"""
Test script to verify SVG path extraction is working correctly
"""

import os
import sys
import django
import numpy as np
import cv2
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.append(str(Path(__file__).parent))
django.setup()

def main():
    print("Testing SVG Path Extraction")
    print("=" * 60)
    
    # Import after Django setup
    from climber.svg_utils import SVGParser
    
    # Test with the wall SVG file
    svg_path = "data/wall.svg"
    if not os.path.exists(svg_path):
        print(f"SVG file not found: {svg_path}")
        return
    
    print(f"Loading SVG from: {svg_path}")
    
    # Create SVG parser
    parser = SVGParser(svg_file_path=svg_path)
    
    # Get SVG dimensions
    width, height = parser.get_svg_dimensions()
    print(f"SVG dimensions: {width}x{height}")
    
    # Extract paths
    paths = parser.extract_paths()
    print(f"Found {len(paths)} paths in SVG")
    
    # Test path extraction for first few paths
    test_paths = list(paths.items())[:5]  # Test first 5 paths
    
    # Create a test image to visualize paths
    test_img = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Calculate scaling factors
    scale_x = 1280 / width
    scale_y = 720 / height
    scale = min(scale_x, scale_y)
    
    # Calculate offset to center the SVG
    offset_x = (1280 - width * scale) / 2
    offset_y = (720 - height * scale) / 2
    
    print(f"\nScale factors: X={scale_x}, Y={scale_y}, Using={scale}")
    print(f"Offset: X={offset_x}, Y={offset_y}")
    
    for path_id, path_data in test_paths:
        print(f"\nTesting path: {path_id}")
        
        # Extract path coordinates using both methods
        coords1 = parser.extract_path_coordinates(path_data['d'])
        polygon_points = parser.path_to_polygon(path_data['d'], num_points=100)
        
        print(f"  extract_path_coordinates: {len(coords1) if coords1 else 0} points")
        print(f"  path_to_polygon: {len(polygon_points) if polygon_points is not None else 0} points")
        
        if polygon_points is not None and len(polygon_points) > 0:
            # Scale and translate points
            polygon_points[:, 0] = polygon_points[:, 0] * scale + offset_x
            polygon_points[:, 1] = polygon_points[:, 1] * scale + offset_y
            
            # Convert to integer for OpenCV
            points = polygon_points.astype(np.int32)
            
            # Draw on test image
            cv2.fillPoly(test_img, [points], (0, 255, 0))  # Green
            cv2.polylines(test_img, [points], True, (0, 150, 0), 2)  # Darker green outline
            
            print(f"  Successfully drew path with {len(points)} points")
        else:
            print(f"  Failed to extract polygon for path")
    
    # Save test image
    output_path = "test_svg_paths.png"
    cv2.imwrite(output_path, test_img)
    print(f"\nTest image saved to: {output_path}")
    print("You can view this image to verify that paths are being extracted correctly.")
    
    # Test point in path functionality
    print("\nTesting point in path functionality...")
    test_point = (width / 2, height / 2)  # Center of SVG
    print(f"Test point: {test_point}")
    
    for path_id, path_data in test_paths:
        is_inside = parser.point_in_path(test_point, path_data['d'])
        print(f"  Point in {path_id}: {is_inside}")

if __name__ == "__main__":
    main()