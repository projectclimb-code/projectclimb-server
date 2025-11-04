import xml.etree.ElementTree as ET
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)




def apply_homography_to_mediapipe_json(data_or_path, H, output_path=None):
    """
    Apply a homography transformation to all (x, y) coordinates in a MediaPipe landmarks JSON.

    Args:
        data_or_path (dict | str): JSON object or path to a JSON file with MediaPipe landmarks.
        H (array-like): 3x3 homography transformation matrix.
        output_path (str, optional): If provided, saves transformed JSON to this path.

    Returns:
        dict: Transformed JSON structure with updated (x, y) coordinates.
    """
    # Load JSON from file if string path given
    if isinstance(data_or_path, str):
        with open(data_or_path, 'r') as f:
            data = json.load(f)
    else:
        data = json.loads(json.dumps(data_or_path))  # deep copy

    H = np.array(H, dtype=float)

    def transform_point(x, y):
        """Apply homography to a single (x, y) pair."""
        p = np.array([x, y, 1.0])
        p_t = H @ p
        if p_t[2] != 0:
            p_t /= p_t[2]
        return float(p_t[0]), float(p_t[1])

    def process_landmark(lm):
        """Transform a landmark dict while keeping other fields."""
        if 'x' in lm and 'y' in lm:
            lm['x'], lm['y'] = transform_point(lm['x'], lm['y'])
        return lm

    if isinstance(data, list):
        transformed = [process_landmark(lm.copy()) for lm in data]
    elif isinstance(data, dict):
        transformed = {}
        for key, value in data.items():
            if isinstance(value, list):
                transformed[key] = [process_landmark(lm.copy()) for lm in value]
            else:
                transformed[key] = value
    else:
        raise ValueError("Unexpected JSON structure. Expected list or dict with landmark lists.")

    if output_path:
        with open(output_path, 'w') as f:
            json.dump(transformed, f, indent=2)

    return transformed
