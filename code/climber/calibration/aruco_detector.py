"""
ArUco marker detection for wall calibration

This module provides functionality to detect ArUco markers in images
and extract their corner coordinates for calibration purposes.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ArUcoDetector:
    """Detects and processes ArUco markers for calibration"""
    
    def __init__(self, dictionary_name: str = 'DICT_4X4_50', marker_size_meters: float = 0.1):
        """
        Initialize the ArUco detector
        
        Args:
            dictionary_name: Name of the ArUco dictionary to use
            marker_size_meters: Physical size of markers in meters
        """
        self.dictionary_name = dictionary_name
        self.marker_size_meters = marker_size_meters
        
        # Get the ArUco dictionary
        self.aruco_dict = getattr(cv2.aruco, dictionary_name)
        self.aruco_params = cv2.aruco.DetectorParameters()
        
        # Optimize detector parameters for better detection
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 23
        self.aruco_params.adaptiveThreshWinSizeStep = 10
        self.aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.aruco_params.cornerRefinementWinSize = 5
        self.aruco_params.cornerRefinementMaxIterations = 30
        self.aruco_params.cornerRefinementMinAccuracy = 0.01
    
    def detect_markers(self, image: np.ndarray) -> Tuple[List[int], List[np.ndarray], List[np.ndarray]]:
        """
        Detect ArUco markers in an image
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Tuple of (marker_ids, corners, rejected_img_points)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect markers
            corners, ids, rejected = cv2.aruco.detectMarkers(
                gray, 
                self.aruco_dict, 
                parameters=self.aruco_params
            )
            
            if ids is not None:
                ids = ids.flatten()
                logger.info(f"Detected {len(ids)} ArUco markers: {ids.tolist()}")
            else:
                logger.warning("No ArUco markers detected in the image")
                
            return ids.tolist() if ids is not None else [], corners, rejected
            
        except Exception as e:
            logger.error(f"Error detecting ArUco markers: {e}")
            return [], [], []
    
    def estimate_pose_single_markers(
        self, 
        corners: List[np.ndarray], 
        camera_matrix: np.ndarray, 
        dist_coeffs: np.ndarray
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Estimate pose of individual markers
        
        Args:
            corners: List of corner arrays for detected markers
            camera_matrix: Camera intrinsic matrix
            dist_coeffs: Camera distortion coefficients
            
        Returns:
            Tuple of (rvecs, tvecs) - rotation and translation vectors for each marker
        """
        try:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners,
                self.marker_size_meters,
                camera_matrix,
                dist_coeffs
            )
            return rvecs, tvecs
        except Exception as e:
            logger.error(f"Error estimating marker pose: {e}")
            return [], []
    
    def draw_detected_markers(
        self, 
        image: np.ndarray, 
        corners: List[np.ndarray], 
        ids: List[int]
    ) -> np.ndarray:
        """
        Draw detected markers on the image
        
        Args:
            image: Input image
            corners: List of corner arrays
            ids: List of marker IDs
            
        Returns:
            Image with detected markers drawn
        """
        output_image = image.copy()
        
        if len(corners) > 0 and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(output_image, corners, np.array(ids))
        
        return output_image
    
    def draw_pose_markers(
        self,
        image: np.ndarray,
        corners: List[np.ndarray],
        ids: List[int],
        rvecs: List[np.ndarray],
        tvecs: List[np.ndarray],
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray
    ) -> np.ndarray:
        """
        Draw pose axes for detected markers
        
        Args:
            image: Input image
            corners: List of corner arrays
            ids: List of marker IDs
            rvecs: Rotation vectors
            tvecs: Translation vectors
            camera_matrix: Camera intrinsic matrix
            dist_coeffs: Camera distortion coefficients
            
        Returns:
            Image with pose axes drawn
        """
        output_image = image.copy()
        
        if len(corners) > 0 and len(rvecs) > 0:
            for i in range(len(corners)):
                cv2.drawFrameAxes(
                    output_image,
                    camera_matrix,
                    dist_coeffs,
                    rvecs[i],
                    tvecs[i],
                    self.marker_size_meters * 0.5  # Scale axes to half marker size
                )
        
        return output_image
    
    def get_marker_centers(self, corners: List[np.ndarray]) -> Dict[int, Tuple[float, float]]:
        """
        Calculate center points of detected markers
        
        Args:
            corners: List of corner arrays for detected markers
            
        Returns:
            Dictionary mapping marker IDs to center coordinates (x, y)
        """
        centers = {}
        
        for i, corner in enumerate(corners):
            if corner is not None and len(corner) > 0:
                # Calculate center as mean of 4 corners
                center = np.mean(corner[0], axis=0)
                centers[i] = (float(center[0]), float(center[1]))
        
        return centers
    
    def validate_marker_detection(
        self, 
        expected_ids: List[int], 
        detected_ids: List[int],
        min_required: int = 4
    ) -> bool:
        """
        Validate that enough expected markers were detected
        
        Args:
            expected_ids: List of expected marker IDs
            detected_ids: List of detected marker IDs
            min_required: Minimum number of markers required for calibration
            
        Returns:
            True if detection is valid for calibration
        """
        detected_set = set(detected_ids)
        expected_set = set(expected_ids)
        
        # Check if we have enough markers
        if len(detected_ids) < min_required:
            logger.warning(f"Insufficient markers detected: {len(detected_ids)} < {min_required}")
            return False
        
        # Check if detected markers are in expected list
        unexpected_markers = detected_set - expected_set
        if unexpected_markers:
            logger.warning(f"Unexpected markers detected: {list(unexpected_markers)}")
        
        # Calculate overlap percentage
        overlap = len(detected_set & expected_set) / len(expected_set)
        logger.info(f"Marker detection overlap: {overlap:.2%}")
        
        return overlap >= 0.5  # At least 50% of expected markers detected