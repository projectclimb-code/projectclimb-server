import os
import sys

# Add the 'code' directory to sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(base_dir, 'code'))

# Correct settings module name from manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

import numpy as np
import cv2
from climber.models import Wall, WallCalibration

def create_calibration():
    try:
        # Using the UUID from the URL
        w = Wall.objects.get(uuid='264d7633-65b2-41a8-92a4-34eb79a891bb')
        print(f"Found Wall: {w.name} (ID: {w.id})")
        
        # USE CORNERS OF WOOD WALL (Non-collinear)
        image_points = [
            [0.18, 0.18], # Top Left
            [0.83, 0.18], # Top Right
            [0.17, 0.92], # Bottom Left
            [0.85, 0.92]  # Bottom Right
        ]
        
        # Map to SVG Boundaries (0..1)
        svg_points = [
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0]
        ]
        
        # Deactivate previous ones
        WallCalibration.objects.filter(wall=w).update(is_active=False)
        
        c_new = WallCalibration.objects.create(
            wall=w,
            name='Manual Quad ID 17 (Corrected Activation)',
            manual_image_points=image_points,
            manual_svg_points=svg_points,
            calibration_type='MANUAL',
            is_active=True
        )
        
        # Compute the Homography (Image -> SVG)
        img_pts_np = np.array(image_points, dtype=np.float32)
        svg_pts_np = np.array(svg_points, dtype=np.float32)
        
        h_matrix, _ = cv2.findHomography(img_pts_np, svg_pts_np)
        
        c_new.perspective_transform = h_matrix.tolist()
        c_new.save()
        
        print(f"Successfully created and activated Calibration ID: {c_new.id}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    create_calibration()
