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
        w = Wall.objects.get(uuid='264d7633-65b2-41a8-92a4-34eb79a891bb')
        print(f"Found Wall: {w.name} (ID: {w.id})")
        
        # DEFINITIVE POINTS (Non-collinear)
        # 1. Sticker B0 (Left)
        # 2. Sticker B1 (Right Top)
        # 3. Sticker B3 (Right Bot)
        # 4. Top Hold 1 (Middle)
        
        image_points = [
            [0.080, 0.420], # B0
            [0.940, 0.380], # B1
            [0.940, 0.580], # B3
            [0.505, 0.145]  # Top Hold 1
        ]
        
        svg_points = [
            [108/2500,  1470/3330], # B0
            [2392/2500, 1316/3330], # B1
            [2392/2500, 1922/3330], # B3
            [1238/2500, 201/3330]   # Top Hold 1
        ]
        
        # Deactivate previous ones
        WallCalibration.objects.filter(wall=w).update(is_active=False)
        
        c_new = WallCalibration.objects.create(
            wall=w,
            name='Precision Quad ID 19',
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
