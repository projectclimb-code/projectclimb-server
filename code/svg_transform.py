import xml.etree.ElementTree as ET
import re
import numpy as np

def parse_transform_matrix(transform_str):
    """Parse a transform attribute to extract the matrix values."""
    matrix_match = re.search(r'matrix\(([-\d.e\s,]+)\)', transform_str)
    if matrix_match:
        values = [float(x) for x in re.findall(r'[-\d.e]+', matrix_match.group(1))]
        if len(values) == 6:
            # SVG matrix(a, b, c, d, e, f) represents:
            # | a c e |
            # | b d f |
            # | 0 0 1 |
            return np.array([
                [values[0], values[2], values[4]],
                [values[1], values[3], values[5]],
                [0, 0, 1]
            ])
    return None

def matrix_to_svg_string(matrix):
    """Convert a 3x3 transformation matrix to SVG matrix string."""
    # Extract a, b, c, d, e, f from the matrix
    a, c, e = matrix[0]
    b, d, f = matrix[1]
    return f"matrix({a},{b},{c},{d},{e},{f})"

def invert_matrix(matrix):
    """Invert a 3x3 transformation matrix."""
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        print("Warning: Matrix is singular and cannot be inverted!")
        return None

def apply_inverse_transform(svg_file, output_file, transform_matrix=None):
    """
    Apply inverse transformation to an SVG file.
    
    Args:
        svg_file: Path to input SVG file
        output_file: Path to output SVG file
        transform_matrix: 3x3 numpy array or None (if None, extracts from root element)
    """
    # Parse SVG
    tree = ET.parse(svg_file)
    root = tree.getroot()
    
    # Define SVG namespace
    namespaces = {'svg': 'http://www.w3.org/2000/svg'}
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    
    # Get transformation matrix
    if transform_matrix is None:
        # Try to extract from root transform attribute
        transform_attr = root.get('transform')
        if transform_attr:
            transform_matrix = parse_transform_matrix(transform_attr)
        else:
            print("No transform matrix provided or found in SVG!")
            return
    
    # Invert the matrix
    inverse_matrix = invert_matrix(transform_matrix)
    
    if inverse_matrix is None:
        print("Cannot proceed with singular matrix.")
        return
    
    print("Original matrix:")
    print(transform_matrix)
    print("\nInverse matrix:")
    print(inverse_matrix)
    
    # Apply inverse transform to root or all elements
    svg_transform = matrix_to_svg_string(inverse_matrix)
    
    # Option 1: Apply to root element
    root.set('transform', svg_transform)
    
    # Save the modified SVG
    tree.write(output_file, encoding='unicode', xml_declaration=True)
    print(f"\nTransformed SVG saved to: {output_file}")

# Example usage
if __name__ == "__main__":
    # Example 1: Use a custom transformation matrix
    # This matrix represents: scale(2, 2), translate(10, 20)
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

    # Example 2: Process an SVG file with custom matrix
    try:
        apply_inverse_transform(
            'data/wall.svg',
            'data/output_inversed.svg',
            transform_matrix=custom_matrix_inversed
        )
    except FileNotFoundError:
        print("Error: input.svg not found!")
        print("\nTo use this script:")
        print("1. Place your SVG file in the same directory and name it 'input.svg'")
        print("2. Or modify the script to use your specific file paths")
        print("3. Optionally provide a custom transformation matrix")
        print("\nExample custom matrix (identity transform):")
        print("np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])")