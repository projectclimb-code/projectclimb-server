"""
Calibration utilities for computing transformation matrices

This module provides functions to compute perspective transformations
between camera coordinates and SVG wall coordinates using ArUco markers.
"""

import cv2
import numpy as np
import json
from typing import Dict, List, Tuple, Optional, Any
import logging

from .aruco_detector import ArUcoDetector

logger = logging.getLogger(__name__)


class CalibrationUtils:
    """Utilities for computing and managing calibration transformations"""
    
    def __init__(self):
        self.aruco_detector = None
    
    def compute_perspective_transformation(
        self,
        image_points: List[Tuple[float, float]],
        svg_points: List[Tuple[float, float]],
        image_size: Tuple[int, int]
    ) -> Tuple[np.ndarray, float]:
        """
        Compute perspective transformation matrix from corresponding points
        
        Args:
            image_points: List of (x, y) points in image coordinates
            svg_points: List of (x, y) points in SVG coordinates
            image_size: Size of the image (width, height)
            
        Returns:
            Tuple of (transformation_matrix, reprojection_error)
        """
        try:
            if len(image_points) < 4 or len(svg_points) < 4:
                raise ValueError("At least 4 corresponding points required for perspective transformation")
            
            if len(image_points) != len(svg_points):
                raise ValueError("Number of image points must match number of SVG points")
            
            # Convert to numpy arrays
            image_pts = np.array(image_points, dtype=np.float32)
            svg_pts = np.array(svg_points, dtype=np.float32)
            
            # Compute perspective transformation from image to SVG coordinates
            transform_matrix = cv2.getPerspectiveTransform(image_pts, svg_pts)
            
            # Calculate reprojection error
            projected_pts = cv2.perspectiveTransform(
                image_pts.reshape(1, -1, 2),
                transform_matrix
            ).reshape(-1, 2)
            
            errors = np.sqrt(np.sum((projected_pts - svg_pts) ** 2, axis=1))
            reprojection_error = np.mean(errors)
            
            logger.info(f"Computed perspective transformation with error: {reprojection_error:.2f} pixels")
            
            return transform_matrix, reprojection_error
            
        except Exception as e:
            logger.error(f"Error computing perspective transformation: {e}")
            return np.eye(3), float('inf')
    
    def compute_manual_calibration(
        self,
        image_points: List[Tuple[float, float]],
        svg_points: List[Tuple[float, float]],
        image_size: Tuple[int, int]
    ) -> Tuple[np.ndarray, float]:
        """
        Compute perspective transformation from manually selected points
        
        Args:
            image_points: List of (x, y) points in image coordinates
            svg_points: List of (x, y) points in SVG coordinates
            image_size: Size of the image (width, height)
            
        Returns:
            Tuple of (transformation_matrix, reprojection_error)
        """
        return self.compute_perspective_transformation(image_points, svg_points, image_size)
    
    def validate_manual_points(
        self,
        image_points: List[Tuple[float, float]],
        svg_points: List[Tuple[float, float]],
        min_points: int = 4
    ) -> Tuple[bool, str]:
        """
        Validate manually selected points for calibration
        
        Args:
            image_points: List of (x, y) points in image coordinates
            svg_points: List of (x, y) points in SVG coordinates
            min_points: Minimum number of points required
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(image_points) != len(svg_points):
            return False, "Number of image points must match number of SVG points"
        
        if len(image_points) < min_points:
            return False, f"At least {min_points} points required for calibration"
        
        # Check for duplicate points
        # if len(image_points) != len(set(image_points)):
        #     return False, "Duplicate image points detected"
        
        # if len(svg_points) != len(set(svg_points)):
        #     return False, "Duplicate SVG points detected"
        
        # Check for collinear points (which would make the transformation invalid)
        if len(image_points) >= 4:
            try:
                image_pts = np.array(image_points, dtype=np.float32)
                # Calculate area of the polygon formed by the points
                # If area is very small, points are likely collinear
                if len(image_pts) >= 4:
                    # Use first 4 points to check collinearity
                    test_pts = image_pts[:4]
                    area = 0.5 * abs(
                        test_pts[0][0]*(test_pts[1][1]-test_pts[3][1]) +
                        test_pts[1][0]*(test_pts[3][1]-test_pts[2][1]) +
                        test_pts[2][0]*(test_pts[3][1]-test_pts[0][1]) +
                        test_pts[3][0]*(test_pts[0][1]-test_pts[1][1])
                    )
                    if area < 1000:  # Arbitrary small threshold (increased from 100)
                        return False, "Selected points are too close to being collinear"
            except Exception as e:
                logger.warning(f"Error checking point collinearity: {e}")
        
        return True, ""
    
    def calibrate_camera(
        self,
        calibration_images: List[np.ndarray],
        marker_size_meters: float = 0.1,
        aruco_dict_name: str = 'DICT_4X4_50'
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float]:
        """
        Calibrate camera using multiple images with ArUco markers
        
        Args:
            calibration_images: List of calibration images
            marker_size_meters: Physical size of ArUco markers
            aruco_dict_name: ArUco dictionary name
            
        Returns:
            Tuple of (camera_matrix, distortion_coeffs, reprojection_error)
        """
        try:
            detector = ArUcoDetector(aruco_dict_name, marker_size_meters)
            
            # Prepare calibration data
            all_corners = []  # 3D points in real world space
            all_image_points = []  # 2D points in image plane
            
            # Generate object points (corners of ArUco markers)
            obj_points = np.zeros((4, 3), np.float32)
            obj_points[:, :2] = np.mgrid[0:2, 0:2].T.reshape(-1, 2) * marker_size_meters
            
            for image in calibration_images:
                # Detect markers
                ids, corners, _ = detector.detect_markers(image)
                
                if len(ids) >= 4:  # Need at least 4 markers for calibration
                    for i, marker_id in enumerate(ids):
                        if i < len(corners):
                            all_corners.append(obj_points)
                            all_image_points.append(corners[i][0])
            
            if len(all_corners) < 10:
                logger.warning(f"Insufficient calibration data: {len(all_corners)} marker detections")
                return None, None, float('inf')
            
            # Perform camera calibration
            ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                all_corners,
                all_image_points,
                calibration_images[0].shape[:2][::-1],
                None,
                None
            )
            
            if ret:
                # Calculate calibration error
                total_error = 0
                for i in range(len(all_corners)):
                    image_points, _ = cv2.projectPoints(
                        all_corners[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs
                    )
                    error = cv2.norm(all_image_points[i], image_points, cv2.NORM_L2) / len(image_points)
                    total_error += error
                
                mean_error = total_error / len(all_corners)
                logger.info(f"Camera calibration completed with error: {mean_error:.2f} pixels")
                
                return camera_matrix, dist_coeffs, mean_error
            else:
                logger.error("Camera calibration failed")
                return None, None, float('inf')
                
        except Exception as e:
            logger.error(f"Error during camera calibration: {e}")
            return None, None, float('inf')
    
    def extract_aruco_markers_from_svg(self, svg_content: str) -> Dict[int, Dict[str, Any]]:
        """
        Extract ArUco marker definitions from SVG content
        
        Args:
            svg_content: SVG file content as string
            
        Returns:
            Dictionary mapping marker IDs to their properties
        """
        try:
            import xml.etree.ElementTree as ET
            
            # Parse SVG
            root = ET.fromstring(svg_content)
            
            # Define namespace
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            
            markers = {}
            
            # Look for elements with ArUco marker information
            # We'll use a naming convention: aruco_marker_<id>
            for elem in root.findall('.//*[@id]', ns):
                elem_id = elem.get('id')
                if elem_id and elem_id.startswith('aruco_marker_'):
                    try:
                        marker_id = int(elem_id.split('_')[-1])
                        
                        # Extract position and size from the element
                        if elem.tag.endswith('rect'):
                            x = float(elem.get('x', 0))
                            y = float(elem.get('y', 0))
                            width = float(elem.get('width', 0))
                            height = float(elem.get('height', 0))
                            
                            markers[marker_id] = {
                                'type': 'rect',
                                'x': x,
                                'y': y,
                                'width': width,
                                'height': height,
                                'center': (x + width/2, y + height/2)
                            }
                        elif elem.tag.endswith('circle'):
                            cx = float(elem.get('cx', 0))
                            cy = float(elem.get('cy', 0))
                            r = float(elem.get('r', 0))
                            
                            markers[marker_id] = {
                                'type': 'circle',
                                'cx': cx,
                                'cy': cy,
                                'r': r,
                                'center': (cx, cy)
                            }
                        
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Invalid ArUco marker definition: {elem_id} - {e}")
            
            logger.info(f"Extracted {len(markers)} ArUco markers from SVG")
            return markers
            
        except Exception as e:
            logger.error(f"Error extracting ArUco markers from SVG: {e}")
            return {}
    
    def transform_point_to_svg(
        self,
        point: Tuple[float, float],
        transform_matrix: np.ndarray
    ) -> Tuple[float, float]:
        """
        Transform a point from image coordinates to SVG coordinates
        
        Args:
            point: Point in image coordinates (x, y)
            transform_matrix: 3x3 perspective transformation matrix
            
        Returns:
            Point in SVG coordinates (x, y)
        """
        try:
            # Convert point to homogeneous coordinates
            homogeneous_point = np.array([point[0], point[1], 1.0])
            
            # Apply transformation
            transformed = transform_matrix @ homogeneous_point
            
            # Convert back from homogeneous coordinates
            if transformed[2] != 0:
                return (transformed[0] / transformed[2], transformed[1] / transformed[2])
            else:
                return (float('inf'), float('inf'))
                
        except Exception as e:
            logger.error(f"Error transforming point: {e}")
            return point
    
    def transform_points_to_svg(
        self,
        points: List[Tuple[float, float]],
        transform_matrix: np.ndarray
    ) -> List[Tuple[float, float]]:
        """
        Transform multiple points from image coordinates to SVG coordinates
        
        Args:
            points: List of points in image coordinates
            transform_matrix: 3x3 perspective transformation matrix
            
        Returns:
            List of points in SVG coordinates
        """
        return [self.transform_point_to_svg(point, transform_matrix) for point in points]
    
    def transform_point_from_svg(
        self,
        point: Tuple[float, float],
        transform_matrix: np.ndarray
    ) -> Tuple[float, float]:
        """
        Transform a point from SVG coordinates to image coordinates
        
        Args:
            point: Point in SVG coordinates (x, y)
            transform_matrix: 3x3 perspective transformation matrix
            
        Returns:
            Point in image coordinates (x, y)
        """
        try:
            # Convert point to homogeneous coordinates
            homogeneous_point = np.array([point[0], point[1], 1.0])
            
            # Invert the transformation matrix
            success, inv_transform_matrix = cv2.invert(transform_matrix)
            
            if not success:
                logger.error("Failed to invert transformation matrix")
                return point
            
            # Apply inverse transformation
            transformed = inv_transform_matrix @ homogeneous_point
            
            # Convert back from homogeneous coordinates
            if transformed[2] != 0:
                return (transformed[0] / transformed[2], transformed[1] / transformed[2])
            else:
                return (float('inf'), float('inf'))
                
        except Exception as e:
            logger.error(f"Error transforming point from SVG: {e}")
            return point
    
    def transform_points_from_svg(
        self,
        points: List[Tuple[float, float]],
        transform_matrix: np.ndarray
    ) -> List[Tuple[float, float]]:
        """
        Transform multiple points from SVG coordinates to image coordinates
        
        Args:
            points: List of points in SVG coordinates
            transform_matrix: 3x3 perspective transformation matrix
            
        Returns:
            List of points in image coordinates
        """
        return [self.transform_point_from_svg(point, transform_matrix) for point in points]
    
    def save_calibration_data(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        perspective_transform: np.ndarray,
        aruco_markers: Dict[int, Dict[str, Any]],
        reprojection_error: float,
        file_path: str
    ) -> bool:
        """
        Save calibration data to JSON file
        
        Args:
            camera_matrix: Camera intrinsic matrix
            dist_coeffs: Camera distortion coefficients
            perspective_transform: Perspective transformation matrix
            aruco_markers: ArUco marker data
            reprojection_error: Calibration reprojection error
            file_path: Path to save the calibration file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            calibration_data = {
                'camera_matrix': camera_matrix.tolist(),
                'distortion_coeffs': dist_coeffs.tolist(),
                'perspective_transform': perspective_transform.tolist(),
                'aruco_markers': aruco_markers,
                'reprojection_error': reprojection_error,
                'created': str(np.datetime64('now'))
            }
            
            with open(file_path, 'w') as f:
                json.dump(calibration_data, f, indent=2)
            
            logger.info(f"Calibration data saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving calibration data: {e}")
            return False
    
    def load_calibration_data(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load calibration data from JSON file
        
        Args:
            file_path: Path to the calibration file
            
        Returns:
            Calibration data dictionary or None if failed
        """
        try:
            with open(file_path, 'r') as f:
                calibration_data = json.load(f)
            
            # Convert lists back to numpy arrays
            calibration_data['camera_matrix'] = np.array(calibration_data['camera_matrix'])
            calibration_data['distortion_coeffs'] = np.array(calibration_data['distortion_coeffs'])
            calibration_data['perspective_transform'] = np.array(calibration_data['perspective_transform'])
            
            logger.info(f"Calibration data loaded from {file_path}")
            return calibration_data
            
        except Exception as e:
            logger.error(f"Error loading calibration data: {e}")
            return None