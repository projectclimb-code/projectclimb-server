#!/usr/bin/env python3
"""
Test script to verify SVG overlay transformation fix
"""

import os
import sys
import django
import numpy as np
import cv2

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from climber.models import Wall, WallCalibration
from climber.svg_utils import SVGParser
from climber.calibration.calibration_utils import CalibrationUtils


def test_svg_overlay_transformation():
    """Test the SVG overlay transformation with calibration data"""
    
    # Get a wall with calibration
    try:
        wall = Wall.objects.first()
        if not wall:
            print("No wall found in database")
            return False
            
        calibration = WallCalibration.objects.filter(wall=wall).latest('created')
        if not calibration:
            print("No calibration found for wall")
            return False
            
        print(f"Testing with wall: {wall.name}")
        print(f"Calibration: {calibration.name}")
        
    except Exception as e:
        print(f"Error loading wall/calibration: {e}")
        return False
    
    # Setup SVG parser
    if not wall.svg_file:
        print("No SVG file associated with wall")
        return False
    
    svg_path = os.path.join('media', wall.svg_file.name)
    if not os.path.exists(svg_path):
        print(f"SVG file not found: {svg_path}")
        return False
    
    svg_parser = SVGParser(svg_file_path=svg_path)
    svg_parser.paths = svg_parser.extract_paths()
    print(f"Loaded SVG with {len(svg_parser.paths)} paths")
    
    # Get SVG dimensions
    svg_width, svg_height = svg_parser.get_svg_dimensions()
    print(f"SVG dimensions: {svg_width}x{svg_height}")
    
    # Create a test image
    test_image = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Initialize calibration utils
    calibration_utils = CalibrationUtils()
    
    # Load the perspective transform from calibration
    try:
        transform_matrix = np.array(calibration.perspective_transform, dtype=np.float32)
        print("Loaded calibration transformation matrix")
        
        # Test transforming a few points from SVG to camera coordinates
        test_points = [
            (0, 0),  # Top-left corner
            (svg_width, 0),  # Top-right corner
            (0, svg_height),  # Bottom-left corner
            (svg_width, svg_height),  # Bottom-right corner
            (svg_width/2, svg_height/2)  # Center
        ]
        
        print("\nTesting point transformations:")
        for i, point in enumerate(test_points):
            transformed = calibration_utils.transform_point_from_svg(point, transform_matrix)
            print(f"Point {i+1}: SVG({point[0]:.1f}, {point[1]:.1f}) -> Camera({transformed[0]:.1f}, {transformed[1]:.1f})")
        
        # Create SVG overlay
        svg_overlay = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Draw SVG paths on the overlay
        for path_id, path_data in list(svg_parser.paths.items())[:5]:  # Test first 5 paths
            try:
                polygon_points = svg_parser.path_to_polygon(path_data['d'], num_points=100)
                
                if polygon_points is not None and len(polygon_points) > 0:
                    # Transform SVG points to camera coordinates
                    transformed_points = calibration_utils.transform_points_from_svg(
                        polygon_points, transform_matrix
                    )
                    polygon_points = np.array(transformed_points)
                    
                    # Convert to integer for OpenCV
                    points = polygon_points.astype(np.int32)
                    
                    # Draw the path
                    cv2.fillPoly(svg_overlay, [points], (0, 255, 0))  # Green holds
                    cv2.polylines(svg_overlay, [points], True, (0, 150, 0), 2)  # Darker green outline
                    
                    print(f"Drew path {path_id} with {len(points)} points")
                else:
                    print(f"Failed to extract polygon for path {path_id}")
            except Exception as e:
                print(f"Error drawing path {path_id}: {e}")
                continue
        
        # Save the overlay image
        output_path = 'test_svg_overlay_fixed.png'
        cv2.imwrite(output_path, svg_overlay)
        print(f"\nSVG overlay saved to: {output_path}")
        
        # Create a blended image with the test image
        alpha = 0.6  # Transparency factor
        blended = cv2.addWeighted(test_image, 1-alpha, svg_overlay, alpha, 0)
        blended_path = 'test_svg_overlay_blended_fixed.png'
        cv2.imwrite(blended_path, blended)
        print(f"Blended image saved to: {blended_path}")
        
        return True
        
    except Exception as e:
        print(f"Error with calibration transformation: {e}")
        return False


if __name__ == "__main__":
    print("Testing SVG overlay transformation fix...")
    success = test_svg_overlay_transformation()
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed!")
        sys.exit(1)