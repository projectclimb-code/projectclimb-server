
import xml.etree.ElementTree as ET
import re
import numpy as np

def parse_transform_matrix(transform_str):
    """Parse a transform attribute to extract the matrix values."""
    matrix_match = re.search(r'matrix\(([-\d.e\s,]+)\)', transform_str)
    if matrix_match:
        values = [float(x) for x in re.findall(r'[-\d.e]+', matrix_match.group(1))]
        if len(values) == 6:
            return np.array([
                [values[0], values[2], values[4]],
                [values[1], values[3], values[5]],
                [0, 0, 1]
            ])
    return None

def invert_matrix(matrix):
    """Invert a 3x3 transformation matrix."""
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        print("Warning: Matrix is singular and cannot be inverted!")
        return None

def transform_point(point, matrix):
    """Transform a 2D point using a 3x3 transformation matrix."""
    x, y = point
    homogeneous = np.array([x, y, 1])
    transformed = matrix @ homogeneous
    return transformed[0], transformed[1]

def parse_path_data(path_d):
    """Parse SVG path data into commands and coordinates."""
    # Split path data into tokens
    tokens = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', path_d)
    return tokens

def transform_path_data(path_d, matrix):
    """Transform all coordinates in a path data string."""
    tokens = parse_path_data(path_d)
    result = []
    i = 0
    current_pos = [0, 0]
    
    while i < len(tokens):
        token = tokens[i]
        
        # Check if token is a command
        if token in 'MmLlHhVvCcSsQqTtAaZz':
            cmd = token
            result.append(cmd)
            i += 1
            
            # Handle different path commands
            if cmd in 'Zz':
                # Close path - no coordinates
                continue
            elif cmd in 'Mm':
                # MoveTo - 2 coordinates (x, y)
                x, y = float(tokens[i]), float(tokens[i+1])
                if cmd == 'm':  # relative
                    x, y = current_pos[0] + x, current_pos[1] + y
                tx, ty = transform_point((x, y), matrix)
                if cmd == 'm':  # convert back to relative
                    tx, ty = tx - current_pos[0], ty - current_pos[1]
                result.extend([f'{tx:.6f}', f'{ty:.6f}'])
                current_pos = [tx if cmd == 'M' else current_pos[0] + tx,
                              ty if cmd == 'M' else current_pos[1] + ty]
                i += 2
            elif cmd in 'Ll':
                # LineTo - 2 coordinates (x, y)
                x, y = float(tokens[i]), float(tokens[i+1])
                if cmd == 'l':
                    x, y = current_pos[0] + x, current_pos[1] + y
                tx, ty = transform_point((x, y), matrix)
                if cmd == 'l':
                    tx, ty = tx - current_pos[0], ty - current_pos[1]
                result.extend([f'{tx:.6f}', f'{ty:.6f}'])
                current_pos = [tx if cmd == 'L' else current_pos[0] + tx,
                              ty if cmd == 'L' else current_pos[1] + ty]
                i += 2
            elif cmd in 'Hh':
                # Horizontal line - 1 coordinate (x)
                x = float(tokens[i])
                if cmd == 'h':
                    x = current_pos[0] + x
                tx, ty = transform_point((x, current_pos[1]), matrix)
                if cmd == 'h':
                    tx = tx - current_pos[0]
                result.append(f'{tx:.6f}')
                current_pos[0] = tx if cmd == 'H' else current_pos[0] + tx
                i += 1
            elif cmd in 'Vv':
                # Vertical line - 1 coordinate (y)
                y = float(tokens[i])
                if cmd == 'v':
                    y = current_pos[1] + y
                tx, ty = transform_point((current_pos[0], y), matrix)
                if cmd == 'v':
                    ty = ty - current_pos[1]
                result.append(f'{ty:.6f}')
                current_pos[1] = ty if cmd == 'V' else current_pos[1] + ty
                i += 1
            elif cmd in 'Cc':
                # Cubic Bezier - 6 coordinates (x1, y1, x2, y2, x, y)
                coords = []
                for j in range(3):
                    x, y = float(tokens[i + j*2]), float(tokens[i + j*2 + 1])
                    if cmd == 'c':
                        x, y = current_pos[0] + x, current_pos[1] + y
                    tx, ty = transform_point((x, y), matrix)
                    if cmd == 'c':
                        tx, ty = tx - current_pos[0], ty - current_pos[1]
                    coords.extend([f'{tx:.6f}', f'{ty:.6f}'])
                result.extend(coords)
                if cmd == 'C':
                    current_pos = [float(coords[-2]), float(coords[-1])]
                else:
                    current_pos = [current_pos[0] + float(coords[-2]), 
                                  current_pos[1] + float(coords[-1])]
                i += 6
            elif cmd in 'Ss':
                # Smooth cubic Bezier - 4 coordinates (x2, y2, x, y)
                coords = []
                for j in range(2):
                    x, y = float(tokens[i + j*2]), float(tokens[i + j*2 + 1])
                    if cmd == 's':
                        x, y = current_pos[0] + x, current_pos[1] + y
                    tx, ty = transform_point((x, y), matrix)
                    if cmd == 's':
                        tx, ty = tx - current_pos[0], ty - current_pos[1]
                    coords.extend([f'{tx:.6f}', f'{ty:.6f}'])
                result.extend(coords)
                if cmd == 'S':
                    current_pos = [float(coords[-2]), float(coords[-1])]
                else:
                    current_pos = [current_pos[0] + float(coords[-2]), 
                                  current_pos[1] + float(coords[-1])]
                i += 4
            elif cmd in 'Qq':
                # Quadratic Bezier - 4 coordinates (x1, y1, x, y)
                coords = []
                for j in range(2):
                    x, y = float(tokens[i + j*2]), float(tokens[i + j*2 + 1])
                    if cmd == 'q':
                        x, y = current_pos[0] + x, current_pos[1] + y
                    tx, ty = transform_point((x, y), matrix)
                    if cmd == 'q':
                        tx, ty = tx - current_pos[0], ty - current_pos[1]
                    coords.extend([f'{tx:.6f}', f'{ty:.6f}'])
                result.extend(coords)
                if cmd == 'Q':
                    current_pos = [float(coords[-2]), float(coords[-1])]
                else:
                    current_pos = [current_pos[0] + float(coords[-2]), 
                                  current_pos[1] + float(coords[-1])]
                i += 4
            elif cmd in 'Tt':
                # Smooth quadratic Bezier - 2 coordinates (x, y)
                x, y = float(tokens[i]), float(tokens[i+1])
                if cmd == 't':
                    x, y = current_pos[0] + x, current_pos[1] + y
                tx, ty = transform_point((x, y), matrix)
                if cmd == 't':
                    tx, ty = tx - current_pos[0], ty - current_pos[1]
                result.extend([f'{tx:.6f}', f'{ty:.6f}'])
                current_pos = [tx if cmd == 'T' else current_pos[0] + tx,
                              ty if cmd == 'T' else current_pos[1] + ty]
                i += 2
            elif cmd in 'Aa':
                # Arc - 7 values (rx, ry, rotation, large-arc, sweep, x, y)
                rx, ry = float(tokens[i]), float(tokens[i+1])
                rotation = float(tokens[i+2])
                large_arc = tokens[i+3]
                sweep = tokens[i+4]
                x, y = float(tokens[i+5]), float(tokens[i+6])
                
                # Transform radii (approximate - doesn't handle skew perfectly)
                trx, _ = transform_point((rx, 0), matrix)
                _, try_ = transform_point((0, ry), matrix)
                
                if cmd == 'a':
                    x, y = current_pos[0] + x, current_pos[1] + y
                tx, ty = transform_point((x, y), matrix)
                if cmd == 'a':
                    tx, ty = tx - current_pos[0], ty - current_pos[1]
                
                result.extend([f'{abs(trx):.6f}', f'{abs(try_):.6f}', 
                              f'{rotation}', large_arc, sweep,
                              f'{tx:.6f}', f'{ty:.6f}'])
                current_pos = [tx if cmd == 'A' else current_pos[0] + tx,
                              ty if cmd == 'A' else current_pos[1] + ty]
                i += 7
        else:
            i += 1
    
    return ' '.join(result)

def apply_inverse_transform_to_paths(svg_file, output_file, transform_matrix):
    """
    Apply inverse transformation to all path coordinates in an SVG file.
    
    Args:
        svg_file: Path to input SVG file
        output_file: Path to output SVG file
        transform_matrix: 3x3 numpy array
    """
    # Parse SVG
    tree = ET.parse(svg_file)
    root = tree.getroot()
    
    # Define SVG namespace
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    
    # Invert the matrix
    inverse_matrix = invert_matrix(transform_matrix)
    
    if inverse_matrix is None:
        print("Cannot proceed with singular matrix.")
        return
    
    print("Original matrix:")
    print(transform_matrix)
    print("\nInverse matrix:")
    print(inverse_matrix)
    
    # Find and transform all path elements
    paths_transformed = 0
    for elem in root.iter():
        # Handle path elements
        if elem.tag.endswith('path'):
            d = elem.get('d')
            if d:
                transformed_d = transform_path_data(d, inverse_matrix)
                elem.set('d', transformed_d)
                paths_transformed += 1
        
        # Also handle other shape elements with coordinates
        elif elem.tag.endswith('circle'):
            cx, cy = float(elem.get('cx', 0)), float(elem.get('cy', 0))
            tx, ty = transform_point((cx, cy), inverse_matrix)
            elem.set('cx', f'{tx:.6f}')
            elem.set('cy', f'{ty:.6f}')
            paths_transformed += 1
        
        elif elem.tag.endswith('ellipse'):
            cx, cy = float(elem.get('cx', 0)), float(elem.get('cy', 0))
            tx, ty = transform_point((cx, cy), inverse_matrix)
            elem.set('cx', f'{tx:.6f}')
            elem.set('cy', f'{ty:.6f}')
            paths_transformed += 1
        
        elif elem.tag.endswith('rect'):
            x, y = float(elem.get('x', 0)), float(elem.get('y', 0))
            tx, ty = transform_point((x, y), inverse_matrix)
            elem.set('x', f'{tx:.6f}')
            elem.set('y', f'{ty:.6f}')
            paths_transformed += 1
        
        elif elem.tag.endswith('line'):
            x1, y1 = float(elem.get('x1', 0)), float(elem.get('y1', 0))
            x2, y2 = float(elem.get('x2', 0)), float(elem.get('y2', 0))
            tx1, ty1 = transform_point((x1, y1), inverse_matrix)
            tx2, ty2 = transform_point((x2, y2), inverse_matrix)
            elem.set('x1', f'{tx1:.6f}')
            elem.set('y1', f'{ty1:.6f}')
            elem.set('x2', f'{tx2:.6f}')
            elem.set('y2', f'{ty2:.6f}')
            paths_transformed += 1
        
        elif elem.tag.endswith('polygon') or elem.tag.endswith('polyline'):
            points = elem.get('points', '')
            coords = [float(x) for x in re.findall(r'[-+]?[0-9]*\.?[0-9]+', points)]
            transformed_points = []
            for i in range(0, len(coords), 2):
                tx, ty = transform_point((coords[i], coords[i+1]), inverse_matrix)
                transformed_points.append(f'{tx:.6f},{ty:.6f}')
            elem.set('points', ' '.join(transformed_points))
            paths_transformed += 1
    
    # Save the modified SVG
    tree.write(output_file, encoding='unicode', xml_declaration=True)
    print(f"\nTransformed {paths_transformed} elements")
    print(f"Output saved to: {output_file}")

# Example usage
if __name__ == "__main__":
    # Example transformation matrix: scale(2, 2), translate(10, 20)
    custom_matrix = np.array([
        [1.1037377050955517, -0.22196538482187758, -0.04186759207349692],
        [-0.019138685211431035, 1.124706453274771, -0.0969283271140223], 
        [0.03754716822851461, -0.3389801608093725, 1.0]
    ])
    
    custom_matrix_inversed = [
        [  0.9093881838682129,   0.17950695136206572,  0.05292424608126101 ],
        [  0.007339651885013383,  0.8945989972074514,   0.09481174080297359 ],
        [ -0.028089640817732796,  0.30769730981743294,  0.9963414330830225  ]

    ]
    
    try:
        apply_inverse_transform_to_paths(
            'data/wall.svg',
            'data/output2.svg',
            transform_matrix=custom_matrix_inversed
            

        )
    except FileNotFoundError:
        print("Error: input.svg not found!")
        print("\nTo use this script:")
        print("1. Place your SVG file in the same directory and name it 'input.svg'")
        print("2. Define your transformation matrix")
        print("3. Run the script")
        print("\nExample matrices:")
        print("Identity: np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])")
        print("Scale 2x: np.array([[2, 0, 0], [0, 2, 0], [0, 0, 1]])")
        print("Translate: np.array([[1, 0, 100], [0, 1, 50], [0, 0, 1]])")
    except Exception as e:
        print(f"Error: {e}")