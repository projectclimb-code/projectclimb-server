# SVG Overlay Transformation Fix

## Problem
The SVG overlay in the pose touch detector was not displaying correctly. The issue was with the transformation matrix used to convert SVG coordinates to camera coordinates.

## Root Cause
The original code was trying to manually invert the calibration transformation matrix to convert SVG coordinates to camera coordinates, but this approach was not working correctly. The calibration utilities only provided methods to transform points from image coordinates to SVG coordinates, but not the reverse.

## Solution
1. Added new methods to the `CalibrationUtils` class to handle the reverse transformation:
   - `transform_point_from_svg()` - Transforms a single point from SVG coordinates to image coordinates
   - `transform_points_from_svg()` - Transforms multiple points from SVG coordinates to image coordinates

2. Updated the `PoseTouchDetector` class to use the new methods for transforming SVG points to camera coordinates.

## Changes Made

### 1. Updated `code/climber/calibration/calibration_utils.py`
Added two new methods:
- `transform_point_from_svg()` - Handles the transformation of a single point from SVG to image coordinates
- `transform_points_from_svg()` - Handles the transformation of multiple points from SVG to image coordinates

These methods properly handle the matrix inversion and homogeneous coordinate conversion.

### 2. Updated `code/climber/management/commands/pose_touch_detector.py`
Modified the `_setup_svg_overlay()` method to:
- Use the new `transform_points_from_svg()` method instead of manually inverting the matrix
- Simplified the transformation logic by delegating to the calibration utilities

## Testing
1. Created a test script `test_svg_overlay_fix.py` to verify the SVG overlay transformation
2. Created a test script `test_pose_touch_detector_svg.py` to test the pose touch detector with SVG overlay
3. Successfully tested with wall ID 1 and video file `data/IMG_2568.mp4`
4. Confirmed that the pose touch detector is correctly detecting touches on holds (e.g., 'hold_84', 'hold_139')

## Results
The SVG overlay now displays correctly aligned with the video feed, and the pose touch detector can accurately detect touches on the climbing holds. The transformation from SVG coordinates to camera coordinates is now working properly.

## Files Modified
- `code/climber/calibration/calibration_utils.py` - Added new transformation methods
- `code/climber/management/commands/pose_touch_detector.py` - Updated to use new transformation methods

## Files Added
- `code/test_svg_overlay_fix.py` - Test script for SVG overlay transformation
- `code/test_pose_touch_detector_svg.py` - Test script for pose touch detector with SVG overlay