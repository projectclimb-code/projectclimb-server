"""
Web interface views for wall calibration

This module provides Django views for managing wall calibration,
including upload of calibration images/videos and processing.
"""

import json
import cv2
import numpy as np
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.uploadedfile import UploadedFile
from django.core.files.base import ContentFile
from django.urls import reverse
import tempfile
import os
from datetime import datetime

from climber.models import Wall, WallCalibration
from .aruco_detector import ArUcoDetector
from .calibration_utils import CalibrationUtils
from climber.svg_utils import parse_svg_file


#@login_required
def wall_calibration_list(request, wall_id):
    """
    List all calibrations for a wall
    """
    wall = get_object_or_404(Wall, id=wall_id)
    calibrations = wall.calibrations.all().order_by('-created')
    
    return render(request, 'climber/calibration/wall_calibration_list.html', {
        'wall': wall,
        'calibrations': calibrations,
    })


#@login_required
def calibration_create(request, wall_id):
    """
    Create a new calibration for a wall
    """
    wall = get_object_or_404(Wall, id=wall_id)
    
    if request.method == 'POST':
        # Handle form submission
        name = request.POST.get('name', f'Calibration {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        description = request.POST.get('description', '')
        aruco_dict = request.POST.get('aruco_dictionary', 'DICT_4X4_50')
        marker_size = float(request.POST.get('marker_size', 0.1))
        
        # Check if SVG file is available
        if not wall.svg_file:
            messages.error(request, 'No SVG file associated with this wall. Please upload an SVG file first.')
            return redirect('wall_detail', pk=wall.uuid)
        
        # Check if calibration image/video was uploaded
        if 'calibration_file' not in request.FILES:
            messages.error(request, 'Please upload a calibration image or video.')
            return render(request, 'climber/calibration/calibration_create.html', {
                'wall': wall,
                'aruco_dictionaries': [
                    'DICT_4X4_50', 'DICT_4X4_100', 'DICT_4X4_250', 'DICT_4X4_1000',
                    'DICT_5X5_50', 'DICT_5X5_100', 'DICT_5X5_250', 'DICT_5X5_1000',
                    'DICT_6X6_50', 'DICT_6X6_100', 'DICT_6X6_250', 'DICT_6X6_1000',
                    'DICT_7X7_50', 'DICT_7X7_100', 'DICT_7X7_250', 'DICT_7X7_1000',
                ]
            })
        
        calibration_file = request.FILES['calibration_file']
        
        try:
            # Process calibration file
            calibration_result = process_calibration_file(
                calibration_file, wall, aruco_dict, marker_size
            )
            
            if calibration_result['success']:
                # Create calibration record
                calibration = WallCalibration.objects.create(
                    wall=wall,
                    name=name,
                    description=description,
                    camera_matrix=calibration_result['camera_matrix'],
                    distortion_coeffs=calibration_result['distortion_coeffs'],
                    perspective_transform=calibration_result['perspective_transform'],
                    aruco_markers=calibration_result['aruco_markers'],
                    aruco_dictionary=aruco_dict,
                    marker_size_meters=marker_size,
                    reprojection_error=calibration_result['reprojection_error'],
                    calibration_image=calibration_result.get('calibration_image')
                )
                
                messages.success(request, f'Calibration "{name}" created successfully!')
                return redirect('calibration_detail', wall_id=wall_id, calibration_id=calibration.id)
            else:
                messages.error(request, f'Calibration failed: {calibration_result["error"]}')
                
        except Exception as e:
            messages.error(request, f'Error processing calibration: {str(e)}')
    
    return render(request, 'climber/calibration/calibration_create.html', {
        'wall': wall,
        'aruco_dictionaries': [
            'DICT_4X4_50', 'DICT_4X4_100', 'DICT_4X4_250', 'DICT_4X4_1000',
            'DICT_5X5_50', 'DICT_5X5_100', 'DICT_5X5_250', 'DICT_5X5_1000',
            'DICT_6X6_50', 'DICT_6X6_100', 'DICT_6X6_250', 'DICT_6X6_1000',
            'DICT_7X7_50', 'DICT_7X7_100', 'DICT_7X7_250', 'DICT_7X7_1000',
        ]
    })


#@login_required
def calibration_detail(request, wall_id, calibration_id):
    """
    Show details of a specific calibration
    """
    wall = get_object_or_404(Wall, id=wall_id)
    calibration = get_object_or_404(WallCalibration, id=calibration_id, wall=wall)
    
    return render(request, 'climber/calibration/calibration_detail.html', {
        'wall': wall,
        'calibration': calibration,
    })


#@login_required
@require_http_methods(['POST'])
def calibration_activate(request, wall_id, calibration_id):
    """
    Activate a specific calibration (deactivate others)
    """
    wall = get_object_or_404(Wall, id=wall_id)
    calibration = get_object_or_404(WallCalibration, id=calibration_id, wall=wall)
    
    # Deactivate all other calibrations
    wall.calibrations.exclude(id=calibration_id).update(is_active=False)
    
    # Activate this calibration
    calibration.is_active = True
    calibration.save()
    
    messages.success(request, f'Calibration "{calibration.name}" activated!')
    return redirect('calibration_detail', wall_id=wall_id, calibration_id=calibration_id)


#@login_required
@require_http_methods(['POST'])
def calibration_delete(request, wall_id, calibration_id):
    """
    Delete a calibration
    """
    wall = get_object_or_404(Wall, id=wall_id)
    calibration = get_object_or_404(WallCalibration, id=calibration_id, wall=wall)
    
    name = calibration.name
    calibration.delete()
    
    messages.success(request, f'Calibration "{name}" deleted!')
    return redirect('wall_calibration_list', wall_id=wall_id)


@csrf_exempt
@require_http_methods(['POST'])
def api_detect_markers(request, wall_id):
    """
    API endpoint to detect ArUco markers in an uploaded image
    """
    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No image uploaded'})
    
    wall = get_object_or_404(Wall, id=wall_id)
    image_file = request.FILES['image']
    aruco_dict = request.POST.get('aruco_dictionary', 'DICT_4X4_50')
    marker_size = float(request.POST.get('marker_size', 0.1))
    
    try:
        # Read image
        image_bytes = image_file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return JsonResponse({'success': False, 'error': 'Invalid image file'})
        
        # Detect markers
        detector = ArUcoDetector(aruco_dict, marker_size)
        marker_ids, corners, _ = detector.detect_markers(image)
        
        # Draw detected markers
        annotated_image = detector.draw_detected_markers(image, corners, marker_ids)
        
        # Convert annotated image back to bytes
        _, buffer = cv2.imencode('.jpg', annotated_image)
        annotated_image_bytes = buffer.tobytes()
        
        # Extract ArUco markers from SVG if available
        svg_markers = {}
        if wall.svg_file:
            try:
                svg_parser = parse_svg_file(wall.svg_file.path)
                svg_markers = svg_parser.extract_aruco_markers()
            except Exception as e:
                print(f"Error parsing SVG: {e}")
        
        # Calculate marker centers
        marker_centers = detector.get_marker_centers(corners)
        
        return JsonResponse({
            'success': True,
            'detected_markers': marker_ids,
            'marker_centers': marker_centers,
            'svg_markers': svg_markers,
            'annotated_image': annotated_image_bytes.hex()  # Convert to hex for JSON
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def process_calibration_file(
    calibration_file: UploadedFile,
    wall: Wall,
    aruco_dict: str,
    marker_size: float
) -> dict:
    """
    Process calibration file (image or video) and compute calibration data
    
    Args:
        calibration_file: Uploaded file (image or video)
        wall: Wall object
        aruco_dict: ArUco dictionary name
        marker_size: Marker size in meters
        
    Returns:
        Dictionary with calibration results
    """
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4' if calibration_file.content_type.startswith('video') else '.jpg') as tmp_file:
            for chunk in calibration_file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name
        
        # Extract frames from video or use single image
        frames = extract_frames(tmp_file_path, max_frames=10)
        
        if not frames:
            return {'success': False, 'error': 'No valid frames found in calibration file'}
        
        # Initialize calibration utilities
        calib_utils = CalibrationUtils()
        detector = ArUcoDetector(aruco_dict, marker_size)
        
        # Extract ArUco markers from SVG
        svg_markers = {}
        if wall.svg_file:
            svg_parser = parse_svg_file(wall.svg_file.path)
            svg_markers = svg_parser.extract_aruco_markers()
        
        if not svg_markers:
            return {'success': False, 'error': 'No ArUco markers found in SVG file'}
        
        # Process each frame to find corresponding points
        image_points = []
        svg_points = []
        calibration_image = None
        
        for frame in frames:
            marker_ids, corners, _ = detector.detect_markers(frame)
            
            if len(marker_ids) >= 4:  # Need at least 4 markers for calibration
                # Get marker centers
                marker_centers = detector.get_marker_centers(corners)
                
                # Match detected markers with SVG markers
                matched_image_points = []
                matched_svg_points = []
                
                for marker_id in marker_ids:
                    if marker_id in svg_markers and marker_id in marker_centers:
                        matched_image_points.append(marker_centers[marker_id])
                        matched_svg_points.append(svg_markers[marker_id]['center'])
                
                if len(matched_image_points) >= 4:
                    image_points.extend(matched_image_points)
                    svg_points.extend(matched_svg_points)
                    
                    if calibration_image is None:
                        # Save first valid frame as calibration image
                        annotated_frame = detector.draw_detected_markers(frame, corners, marker_ids)
                        _, buffer = cv2.imencode('.jpg', annotated_frame)
                        calibration_image = ContentFile(buffer.tobytes(), name='calibration.jpg')
        
        # Clean up temporary file
        os.unlink(tmp_file_path)
        
        if len(image_points) < 4:
            return {'success': False, 'error': 'Insufficient corresponding points found for calibration'}
        
        # Compute perspective transformation
        transform_matrix, reprojection_error = calib_utils.compute_perspective_transformation(
            image_points, svg_points, frames[0].shape[:2][::-1]
        )
        
        # For now, use default camera calibration (can be enhanced later)
        camera_matrix = np.array([
            [frames[0].shape[1], 0, frames[0].shape[1]/2],
            [0, frames[0].shape[1], frames[0].shape[0]/2],
            [0, 0, 1]
        ], dtype=np.float32)
        distortion_coeffs = np.zeros(5)
        
        return {
            'success': True,
            'camera_matrix': camera_matrix.tolist(),
            'distortion_coeffs': distortion_coeffs.tolist(),
            'perspective_transform': transform_matrix.tolist(),
            'aruco_markers': svg_markers,
            'reprojection_error': float(reprojection_error),
            'calibration_image': calibration_image
        }
        
    except Exception as e:
        # Clean up temporary file if it exists
        if 'tmp_file_path' in locals():
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
        return {'success': False, 'error': str(e)}


def extract_frames(video_path: str, max_frames: int = 10) -> list:
    """
    Extract frames from video file or return single image
    
    Args:
        video_path: Path to video or image file
        max_frames: Maximum number of frames to extract
        
    Returns:
        List of frames as numpy arrays
    """
    frames = []
    
    # Check if it's an image
    if video_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        image = cv2.imread(video_path)
        if image is not None:
            frames.append(image)
        return frames
    
    # Process as video
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return frames
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(1, total_frames // max_frames)
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            frames.append(frame)
            if len(frames) >= max_frames:
                break
        
        frame_count += 1
    
    cap.release()
    return frames



@csrf_exempt
@require_http_methods(['POST'])
def api_upload_calibration_image(request, wall_id):
    """
    API endpoint to upload and display a calibration image for manual point selection
    """
    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No image uploaded'})
    
    wall = get_object_or_404(Wall, id=wall_id)
    image_file = request.FILES['image']
    
    try:
        # Read image
        image_bytes = image_file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return JsonResponse({'success': False, 'error': 'Invalid image file'})
        
        # Resize image if too large (for web display)
        max_dimension = 1200
        height, width = image.shape[:2]
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height))
        
        # Convert image to base64 for web display
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = buffer.tobytes()
        
        return JsonResponse({
            'success': True,
            'image': image_base64.hex(),
            'width': image.shape[1],
            'height': image.shape[0]
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(['POST'])
def api_save_manual_calibration(request, wall_id):
    """
    API endpoint to save manual calibration data
    """
    wall = get_object_or_404(Wall, id=wall_id)
    
    try:
        # Get data from request
        name = request.POST.get('name', f'Manual Calibration {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        description = request.POST.get('description', '')
        image_points_str = request.POST.get('image_points', '[]')
        svg_points_str = request.POST.get('svg_points', '[]')
        
        image_points = json.loads(image_points_str)
        svg_points = json.loads(svg_points_str)
        
        # Validate points
        calib_utils = CalibrationUtils()
        is_valid, error_msg = calib_utils.validate_manual_points(image_points, svg_points)
        
        if not is_valid:
            return JsonResponse({'success': False, 'error': error_msg})
        
        # Compute perspective transformation
        image_size = (1920, 1080)  # Default size
        transform_matrix, reprojection_error = calib_utils.compute_manual_calibration(
            image_points, svg_points, image_size
        )
        
        # Default camera calibration
        camera_matrix = np.array([
            [image_size[0], 0, image_size[0]/2],
            [0, image_size[1], image_size[1]/2],
            [0, 0, 1]
        ], dtype=np.float32)
        distortion_coeffs = np.zeros(5)
        
        # Convert numpy arrays to regular Python lists
        transform_matrix = transform_matrix.tolist() if hasattr(transform_matrix, 'tolist') else transform_matrix
        camera_matrix = camera_matrix.tolist() if hasattr(camera_matrix, 'tolist') else camera_matrix
        distortion_coeffs = distortion_coeffs.tolist() if hasattr(distortion_coeffs, 'tolist') else distortion_coeffs
        
        # Create calibration record
        calibration = WallCalibration.objects.create(
            wall=wall,
            name=name,
            description=description,
            calibration_type='manual',
            camera_matrix=camera_matrix,
            distortion_coeffs=distortion_coeffs,
            perspective_transform=transform_matrix,
            manual_image_points=image_points,
            manual_svg_points=svg_points,
            reprojection_error=float(reprojection_error)
        )
        
        return JsonResponse({
            'success': True,
            'calibration_id': calibration.id,
            'reprojection_error': reprojection_error
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid point data format'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def wall_svg_overlay(request, wall_id):
    """
    Serve SVG content with calibration transformation for overlay display
    
    Args:
        request: HTTP request object
        wall_id: ID of the wall
        
    Returns:
        HttpResponse with SVG content or JSON error
    """
    wall = get_object_or_404(Wall, id=wall_id)
    
    # Check if wall has an SVG file
    if not wall.svg_file:
        return JsonResponse({'error': 'No SVG file associated with this wall'}, status=404)
    
    # Check if wall has an active calibration
    calibration = wall.active_calibration
    if not calibration:
        return JsonResponse({'error': 'No active calibration for this wall'}, status=404)
    
    try:
        # Parse SVG file
        svg_parser = parse_svg_file(wall.svg_file.path)
        
        # Get SVG dimensions
        svg_width, svg_height = svg_parser.get_svg_dimensions()
        
        # Read original SVG content
        with open(wall.svg_file.path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        # Create a modified SVG with calibration data
        # We'll add the calibration transformation matrix as a data attribute
        import xml.etree.ElementTree as ET
        
        # Parse SVG
        root = ET.fromstring(svg_content)
        root.set('data-calibration-matrix', str(calibration.perspective_transform))
        root.set('data-svg-width', str(svg_width))
        root.set('data-svg-height', str(svg_height))
        root.set('data-wall-id', str(wall.id))
        
        # Convert back to string
        modified_svg = ET.tostring(root, encoding='unicode')
        
        # Return as SVG content type
        return HttpResponse(modified_svg, content_type='image/svg+xml')
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing SVG: {str(e)}'}, status=500)


def wall_calibrated_svg_data(request, wall_id):
    """
    API endpoint to get SVG data with calibration transformation matrix
    
    Args:
        request: HTTP request object
        wall_id: ID of the wall
        
    Returns:
        JsonResponse with SVG data and calibration information
    """
    wall = get_object_or_404(Wall, id=wall_id)
    
    # Check if wall has an SVG file
    if not wall.svg_file:
        return JsonResponse({'error': 'No SVG file associated with this wall'}, status=404)
    
    # Check if wall has an active calibration
    calibration = wall.active_calibration
    if not calibration:
        return JsonResponse({'error': 'No active calibration for this wall'}, status=404)
    
    try:
        # Parse SVG file
        svg_parser = parse_svg_file(wall.svg_file.path)
        
        # Get SVG dimensions
        svg_width, svg_height = svg_parser.get_svg_dimensions()
        
        # Get wall image URL if available
        wall_image_url = None
        if wall.wall_image:
            wall_image_url = wall.wall_image.url
        elif calibration.calibration_image:
            wall_image_url = calibration.calibration_image.url
        
        # Extract paths and markers
        paths = svg_parser.extract_paths()
        aruco_markers = svg_parser.extract_aruco_markers()
        
        # Remove non-serializable elements from paths
        serializable_paths = {}
        for path_id, path_data in paths.items():
            serializable_paths[path_id] = {
                'id': path_data.get('id'),
                'd': path_data.get('d'),
                'style': path_data.get('style')
            }
        
        return JsonResponse({
            'success': True,
            'svg_url': wall.svg_file.url,
            'svg_width': svg_width,
            'svg_height': svg_height,
            'wall_image_url': wall_image_url,
            'calibration': {
                'id': calibration.id,
                'name': calibration.name,
                'perspective_transform': calibration.perspective_transform,
                'calibration_type': calibration.calibration_type,
                'reprojection_error': calibration.reprojection_error
            },
            'paths': serializable_paths,
            'aruco_markers': aruco_markers,
            'wall_dimensions': {
                'width_mm': wall.width_mm,
                'height_mm': wall.height_mm
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing SVG data: {str(e)}'}, status=500)



#@login_required
def calibration_manual_points(request, wall_id):
    """
    Create a manual point calibration for a wall by selecting corresponding points
    Similar to the proof of concept demo but integrated with the wall model
    """
    wall = get_object_or_404(Wall, id=wall_id)
    
    if request.method == 'POST':
        # Handle form submission
        name = request.POST.get('name', f'Manual Point Calibration {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        description = request.POST.get('description', '')
        
        # Get point data from form
        image_points_str = request.POST.get('image_points', '[]')
        svg_points_str = request.POST.get('svg_points', '[]')
        
        try:
            image_points = json.loads(image_points_str)
            svg_points = json.loads(svg_points_str)
            
            # Validate points
            calib_utils = CalibrationUtils()
            is_valid, error_msg = calib_utils.validate_manual_points(image_points, svg_points, min_points=3)
            
            if not is_valid:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg})
                else:
                    messages.error(request, f'Invalid points: {error_msg}')
                    return render(request, 'climber/calibration/calibration_manual_points.html', {
                        'wall': wall,
                        'image_points': image_points_str,
                        'svg_points': svg_points_str,
                    })
            
            # Use wall image as calibration image if available
            calibration_image = wall.wall_image
            
            # Compute image size from wall image
            image_size = (1920, 1080)  # Default size
            if wall.wall_image:
                try:
                    # Read image to get actual size
                    from django.core.files.storage import default_storage
                    if default_storage.exists(wall.wall_image.path):
                        image = cv2.imread(wall.wall_image.path)
                        if image is not None:
                            image_size = image.shape[:2][::-1]  # width, height
                except Exception as e:
                    print(f"Error reading wall image for size: {e}")
            
            # Compute perspective transformation
            transform_matrix, reprojection_error = calib_utils.compute_manual_calibration(
                image_points, svg_points, image_size
            )
            
            # For now, use default camera calibration
            camera_matrix = np.array([
                [image_size[0], 0, image_size[0]/2],
                [0, image_size[1], image_size[1]/2],
                [0, 0, 1]
            ], dtype=np.float32)
            distortion_coeffs = np.zeros(5)
            
            # Convert numpy arrays to regular Python lists
            transform_matrix = transform_matrix.tolist() if hasattr(transform_matrix, 'tolist') else transform_matrix
            camera_matrix = camera_matrix.tolist() if hasattr(camera_matrix, 'tolist') else camera_matrix
            distortion_coeffs = distortion_coeffs.tolist() if hasattr(distortion_coeffs, 'tolist') else distortion_coeffs
            
            # Create calibration record
            calibration = WallCalibration.objects.create(
                wall=wall,
                name=name,
                description=description,
                calibration_type='manual_points',
                camera_matrix=camera_matrix,
                distortion_coeffs=distortion_coeffs,
                perspective_transform=transform_matrix,
                manual_image_points=image_points,
                manual_svg_points=svg_points,
                reprojection_error=float(reprojection_error),
                calibration_image=calibration_image
            )

            # Generate and save the overlay image
            calib_utils.generate_overlay_image(calibration)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'calibration_id': calibration.id,
                    'redirect_url': reverse('calibration_detail', kwargs={'wall_id': wall_id, 'calibration_id': calibration.id})
                })
            else:
                messages.success(request, f'Manual point calibration "{name}" created successfully!')
                return redirect('calibration_detail', wall_id=wall_id, calibration_id=calibration.id)
            
        except json.JSONDecodeError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid point data format'})
            else:
                messages.error(request, 'Invalid point data format')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f'Error creating calibration: {str(e)}')
    
    return render(request, 'climber/calibration/calibration_manual_points.html', {
        'wall': wall,
        'image_points': '[]',
        'svg_points': '[]',
    })