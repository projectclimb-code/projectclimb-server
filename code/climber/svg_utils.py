import xml.etree.ElementTree as ET
import numpy as np
import re
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SVGParser:
    """Parse and extract information from SVG files"""
    
    def __init__(self, svg_content: str = None, svg_file_path: str = None):
        """
        Initialize SVG parser
        
        Args:
            svg_content: SVG content as string
            svg_file_path: Path to SVG file
        """
        if svg_content:
            self.content = svg_content
        elif svg_file_path:
            with open(svg_file_path, 'r',encoding="utf-8") as f:
                self.content = f.read()
        else:
            raise ValueError("Either svg_content or svg_file_path must be provided")
        
        self.root = ET.fromstring(self.content)
        self.namespaces = {'svg': 'http://www.w3.org/2000/svg'}
    
    def extract_paths(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract all path elements from the SVG
        
        Returns:
            Dictionary mapping path IDs to their properties
        """
        paths = {}
        
        for path in self.root.findall('.//svg:path', self.namespaces):
            path_id = path.get('id', '')
            if not path_id:
                continue
            
            d = path.get('d', '')
            style = path.get('style', '')
            
            # Extract style properties
            style_props = self._parse_style(style)
            
            paths[path_id] = {
                'id': path_id,
                'd': d,
                'style': style_props,
                'element': path
            }
        
        logger.info(f"Extracted {len(paths)} paths from SVG")
        return paths
    
    def extract_aruco_markers(self) -> Dict[int, Dict[str, Any]]:
        """
        Extract ArUco marker definitions from SVG
        
        Returns:
            Dictionary mapping marker IDs to their properties
        """
        markers = {}
        
        # Look for elements with ArUco marker information
        # We'll use a naming convention: aruco_marker_<id>
        for elem in self.root.findall('.//*[@id]', self.namespaces):
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
    
    def get_svg_dimensions(self) -> Tuple[float, float]:
        """
        Get SVG dimensions from viewBox or width/height attributes
        
        Returns:
            Tuple of (width, height) in SVG units
        """
        # Try viewBox first
        viewbox = self.root.get('viewBox')
        if viewbox:
            try:
                values = list(map(float, viewbox.split()))
                return values[2], values[3]  # width, height
            except (ValueError, IndexError):
                pass
        
        # Fall back to width/height attributes
        width = self.root.get('width', '0')
        height = self.root.get('height', '0')
        
        # Remove units if present
        width = float(re.sub(r'[a-zA-Z]+', '', width))
        height = float(re.sub(r'[a-zA-Z]+', '', height))
        
        return width, height
    
    def parse_path_d(self, path_d: str) -> List[Tuple[str, List[float]]]:
        """
        Parse SVG path d attribute into commands and coordinates
        
        Args:
            path_d: SVG path d attribute string
            
        Returns:
            List of (command, coordinates) tuples
        """
        # Regular expression to match path commands and coordinates
        pattern = r'([MmLlHhVvCcSsQqTtAaZz])\s*([^MmLlHhVvCcSsQqTtAaZz]*)'
        matches = re.findall(pattern, path_d)
        
        path_commands = []
        for command, coords_str in matches:
            # Extract numbers from coordinates string
            coords = list(map(float, re.findall(r'-?\d*\.?\d+', coords_str)))
            path_commands.append((command, coords))
        
        return path_commands
    
    def path_to_polygon(self, path_d: str, num_points: int = 100) -> np.ndarray:
        """
        Convert SVG path to polygon points
        
        Args:
            path_d: SVG path d attribute
            num_points: Number of points to sample along the path
            
        Returns:
            Array of (x, y) points
        """
        try:
            import matplotlib.path as mpath
            
            # Create matplotlib path from SVG path
            path = mpath.Path(self._parse_path_to_matplotlib_format(path_d))
            
            # Sample points along the path
            t = np.linspace(0, 1, num_points)
            points = path.interpolated(num_points).vertices
            
            return points
            
        except ImportError:
            # Fallback to simple path parsing
            return self._simple_path_to_polygon(path_d, num_points)
        except Exception as e:
            logger.error(f"Error converting path to polygon: {e}")
            return np.array([])
    
    def point_in_path(self, point: Tuple[float, float], path_d: str) -> bool:
        """
        Check if a point is inside a path
        
        Args:
            point: Point to check (x, y)
            path_d: SVG path d attribute
            
        Returns:
            True if point is inside the path
        """
        try:
            import matplotlib.path as mpath
            
            # Create matplotlib path
            path = mpath.Path(self._parse_path_to_matplotlib_format(path_d))
            
            # Check if point is inside
            return path.contains_point(point)
            
        except ImportError:
            # Fallback to ray casting algorithm
            return self._point_in_polygon_ray_casting(point, self.path_to_polygon(path_d))
        except Exception as e:
            logger.error(f"Error checking if point is in path: {e}")
            return False
    
    def _parse_style(self, style_str: str) -> Dict[str, str]:
        """Parse CSS style string into dictionary"""
        style_props = {}
        if not style_str:
            return style_props
        
        for prop in style_str.split(';'):
            if ':' in prop:
                key, value = prop.split(':', 1)
                style_props[key.strip()] = value.strip()
        
        return style_props
    
    def _parse_path_to_matplotlib_format(self, path_d: str) -> List[Tuple[float, float]]:
        """Convert SVG path format to matplotlib path format"""
        commands = self.parse_path_d(path_d)
        points = []
        current_pos = [0, 0]
        
        for command, coords in commands:
            if command.upper() == 'M':  # Move to
                if command.islower():  # Relative coordinates
                    current_pos[0] += coords[0]
                    current_pos[1] += coords[1]
                else:  # Absolute coordinates
                    current_pos[0] = coords[0]
                    current_pos[1] = coords[1]
                points.append(tuple(current_pos))
                
            elif command.upper() == 'L':  # Line to
                for i in range(0, len(coords), 2):
                    if command.islower():  # Relative coordinates
                        current_pos[0] += coords[i]
                        current_pos[1] += coords[i+1]
                    else:  # Absolute coordinates
                        current_pos[0] = coords[i]
                        current_pos[1] = coords[i+1]
                    points.append(tuple(current_pos))
            
            elif command.upper() == 'C':  # Cubic Bezier curve
                # Process cubic Bezier curves by sampling points along the curve
                for i in range(0, len(coords), 6):
                    if i + 5 < len(coords):
                        cp1x, cp1y, cp2x, cp2y, endx, endy = coords[i:i+6]
                        
                        if command.islower():  # Relative coordinates
                            cp1x += current_pos[0]
                            cp1y += current_pos[1]
                            cp2x += current_pos[0]
                            cp2y += current_pos[1]
                            endx += current_pos[0]
                            endy += current_pos[1]
                        
                        # Sample points along the Bezier curve
                        curve_points = self._sample_bezier_curve(
                            current_pos[0], current_pos[1], cp1x, cp1y, cp2x, cp2y, endx, endy, 20
                        )
                        points.extend(curve_points)
                        
                        current_pos[0] = endx
                        current_pos[1] = endy
            
            elif command.upper() == 'Q':  # Quadratic Bezier curve
                # Process quadratic Bezier curves
                for i in range(0, len(coords), 4):
                    if i + 3 < len(coords):
                        cpx, cpy, endx, endy = coords[i:i+4]
                        
                        if command.islower():  # Relative coordinates
                            cpx += current_pos[0]
                            cpy += current_pos[1]
                            endx += current_pos[0]
                            endy += current_pos[1]
                        
                        # Sample points along the quadratic Bezier curve
                        curve_points = self._sample_quadratic_bezier_curve(
                            current_pos[0], current_pos[1], cpx, cpy, endx, endy, 15
                        )
                        points.extend(curve_points)
                        
                        current_pos[0] = endx
                        current_pos[1] = endy
            
            elif command.upper() == 'A':  # Elliptical arc
                # For simplicity, approximate arcs with line segments
                for i in range(0, len(coords), 7):
                    if i + 6 < len(coords):
                        rx, ry, x_axis_rotation, large_arc_flag, sweep_flag, endx, endy = coords[i:i+7]
                        
                        if command.islower():  # Relative coordinates
                            endx += current_pos[0]
                            endy += current_pos[1]
                        
                        # Simple approximation: just draw a line to the end point
                        # In a more complete implementation, we would sample the actual arc
                        points.append((endx, endy))
                        current_pos[0] = endx
                        current_pos[1] = endy
            
            elif command.upper() == 'Z':  # Close path
                if points:
                    points.append(points[0])  # Close to first point
        
        return points
    
    def _simple_path_to_polygon(self, path_d: str, num_points: int) -> np.ndarray:
        """Simple path to polygon conversion without matplotlib"""
        points = self._parse_path_to_matplotlib_format(path_d)
        
        if not points:
            return np.array([])
        
        # If we have fewer points than requested, return as is
        if len(points) >= num_points:
            return np.array(points)
        
        # Otherwise, interpolate between points
        result = []
        for i in range(len(points)):
            result.append(points[i])
            if i < len(points) - 1:
                # Add interpolated points
                next_point = points[i + 1]
                for j in range(1, num_points // len(points)):
                    t = j / (num_points // len(points))
                    interp_x = points[i][0] + t * (next_point[0] - points[i][0])
                    interp_y = points[i][1] + t * (next_point[1] - points[i][1])
                    result.append((interp_x, interp_y))
        
        return np.array(result)
    
    def _point_in_polygon_ray_casting(self, point: Tuple[float, float], polygon: np.ndarray) -> bool:
        """Ray casting algorithm for point in polygon test"""
        if len(polygon) < 3:
            return False
        
        x, y = point
        n = len(polygon)
        inside = False
        
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        
        return inside
    
    def _sample_bezier_curve(self, p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y, num_points):
        """Sample points along a cubic Bezier curve"""
        points = []
        for i in range(1, num_points + 1):
            t = i / num_points
            # Cubic Bezier formula
            x = (1-t)**3 * p0x + 3*(1-t)**2*t * p1x + 3*(1-t)*t**2 * p2x + t**3 * p3x
            y = (1-t)**3 * p0y + 3*(1-t)**2*t * p1y + 3*(1-t)*t**2 * p2y + t**3 * p3y
            points.append((x, y))
        return points
    
    def _sample_quadratic_bezier_curve(self, p0x, p0y, p1x, p1y, p2x, p2y, num_points):
        """Sample points along a quadratic Bezier curve"""
        points = []
        for i in range(1, num_points + 1):
            t = i / num_points
            # Quadratic Bezier formula
            x = (1-t)**2 * p0x + 2*(1-t)*t * p1x + t**2 * p2x
            y = (1-t)**2 * p0y + 2*(1-t)*t * p1y + t**2 * p2y
            points.append((x, y))
        return points
    
    def extract_path_coordinates(self, path_d: str) -> List[Tuple[float, float]]:
        """
        Extract coordinates from SVG path d attribute
        
        Args:
            path_d: SVG path d attribute string
            
        Returns:
            List of (x, y) coordinate tuples
        """
        return self._parse_path_to_matplotlib_format(path_d)


def parse_svg_file(svg_file_path: str) -> SVGParser:
    """
    Convenience function to parse an SVG file
    
    Args:
        svg_file_path: Path to SVG file
        
    Returns:
        SVGParser instance
    """
    return SVGParser(svg_file_path=svg_file_path)


def get_hold_centers(svg_parser: SVGParser) -> Dict[str, Tuple[float, float]]:
    """
    Extract center points of all holds (paths) from SVG
    
    Args:
        svg_parser: SVGParser instance
        
    Returns:
        Dictionary mapping hold IDs to center coordinates
    """
    paths = svg_parser.extract_paths()
    hold_centers = {}
    
    for path_id, path_data in paths.items():
        try:
            polygon = svg_parser.path_to_polygon(path_data['d'])
            if len(polygon) > 0:
                # Calculate center as mean of all points
                center = np.mean(polygon, axis=0)
                hold_centers[path_id] = (float(center[0]), float(center[1]))
        except Exception as e:
            logger.warning(f"Error calculating center for path {path_id}: {e}")
    
    return hold_centers