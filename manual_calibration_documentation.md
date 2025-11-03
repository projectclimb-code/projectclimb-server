# Manual Calibration for Climbing Walls

This document describes the manual calibration feature that allows users to calibrate climbing walls without ArUco markers or when ArUco markers are not available.

## Overview

Manual calibration allows users to select corresponding points between a wall image and the SVG diagram to compute a perspective transformation. This is useful when:

- The wall doesn't have ArUco markers
- ArUco markers are damaged or missing
- Users prefer a more direct calibration approach
- The wall has distinctive features that can be easily identified

## Architecture

```
Wall Image → User selects points → Manual Calibration → Perspective Transformation
SVG Diagram → User selects points →
```

## Components

### 1. Model Changes

The `WallCalibration` model has been updated with new fields:

```python
# Calibration type
calibration_type = models.CharField(
    max_length=20,
    choices=[
        ('aruco', 'ArUco Markers'),
        ('manual', 'Manual Points'),
    ],
    default='aruco'
)

# Manual calibration data
manual_image_points = models.JSONField(default=list, blank=True)
manual_svg_points = models.JSONField(default=list, blank=True)
```

### 2. Calibration Utils

The `CalibrationUtils` class has been extended with:

- `compute_manual_calibration()` - Computes perspective transformation from manually selected points
- `validate_manual_points()` - Validates selected points for quality

### 3. Views and Templates


- Updated `calibration_create.html` - Added option to choose calibration type

### 4. JavaScript Features

- Interactive point selection on images
- Visual feedback with numbered markers
- Point removal functionality
- Real-time validation

## Usage

### 1. Access Manual Calibration

From the wall calibration list page:
1. Click "Manual Calibration" button
2. Or select "Manual Point Selection" on the create calibration page

### 2. Calibration Process

1. **Upload Wall Image**
   - Click "Choose File" to upload a clear image of the wall
   - The image should show distinctive features (holds, bolts, corners)

2. **Select Corresponding Points**
   - Click on distinctive features in the wall image (red markers)
   - Click on the same features in the SVG diagram (blue markers)
   - Select at least 4 point pairs (6-8 recommended for better accuracy)

3. **Review Points**
   - Selected points are listed on both sides
   - Click "Remove" to delete incorrect points
   - Click "Clear All Points" to start over

4. **Save Calibration**
   - Enter a name and optional description
   - Click "Save Calibration" when ready
   - The system will compute the perspective transformation

### 3. Point Selection Guidelines

**Good Points:**
- Wall corners
- Permanent bolts or anchors
- Distinctive hold shapes
- Features that won't move or change

**Avoid:**
- Temporary holds or markings
- Features that might be obscured
- Points that are too close together
- Moving parts or ropes

## API Endpoints

### Upload Calibration Image
```
POST /calibration/wall/{wall_id}/upload-calibration-image/
Content-Type: multipart/form-data

Response:
{
  "success": true,
  "image": "<hex_encoded_image>",
  "width": 800,
  "height": 600
}
```

### Save Manual Calibration
```
POST /calibration/wall/{wall_id}/save-manual-calibration/
Content-Type: application/x-www-form-urlencoded

Parameters:
- name: Calibration name
- description: Optional description
- image_points: JSON array of image points [[x1,y1], [x2,y2], ...]
- svg_points: JSON array of SVG points [[x1,y1], [x2,y2], ...]

Response:
{
  "success": true,
  "calibration_id": 123,
  "reprojection_error": 1.23
}
```

## Data Format

### Image Points
```json
[
  [100.5, 200.3],
  [300.2, 150.7],
  [500.8, 400.1],
  [700.3, 350.9]
]
```

### SVG Points
```json
[
  [50.0, 50.0],
  [750.0, 50.0],
  [50.0, 550.0],
  [750.0, 550.0]
]
```

## Validation

The system validates selected points to ensure:

1. **Minimum Points**: At least 4 point pairs are required
2. **Matching Points**: Same number of points in both image and SVG
3. **No Duplicates**: Points must be unique
4. **Non-Collinear**: Points should not be too close to being collinear

## Error Handling

Common errors and solutions:

1. **"Insufficient corresponding points"**
   - Select at least 4 point pairs
   - Ensure points are selected in both image and SVG

2. **"Points are too close to being collinear"**
   - Select points that are more spread out
   - Avoid points that form a straight line

3. **"Duplicate points detected"**
   - Don't click the same location twice
   - Use "Remove" to delete incorrect points

## Testing

Run the test script to verify functionality:

```bash
cd code
uv run python test_manual_calibration.py
```

This tests:
- Calibration utilities
- Model fields
- URL patterns
- Point validation

## Troubleshooting

### Points Not Appearing
- Check that the image has loaded completely
- Ensure you're clicking within the image boundaries
- Refresh the page and try again

### Calibration Not Saving
- Verify all required fields are filled
- Check that you have at least 4 point pairs
- Look for error messages in the browser console

### Poor Calibration Quality
- Select points that are spread across the entire wall
- Use more than 4 point pairs for better accuracy
- Choose distinctive, permanent features

## Comparison with ArUco Calibration

| Feature | ArUco Calibration | Manual Calibration |
|---------|------------------|-------------------|
| Setup | Requires markers | No setup required |
| Accuracy | High (sub-pixel) | Good (depends on point selection) |
| Speed | Fast (automatic) | Slower (manual) |
| Reliability | Consistent | Varies with user skill |
| Requirements | Markers + clear view | Clear image + distinctive features |

## Future Enhancements

Potential improvements:
1. Automatic feature detection and suggestion
2. Zoom functionality for precise point selection
3. Calibration quality indicators
4. Point selection templates for common wall types
5. Batch calibration for multiple walls