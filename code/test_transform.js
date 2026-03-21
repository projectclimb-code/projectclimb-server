// Test transform matrix calculation
function testTransformCalculation() {
    // Sample calibration data (from our wall)
    const calibrationInv = [[0.9232489466667175, 0.21816162765026093, 0.04774051532149315], [0.0022997416090220213, 0.9543613791465759, 0.1005730926990509], [-0.04386656731367111, 0.35788896679878235, 1.036515474319458]];
    
    // Sample SVG dimensions (from our wall)
    const W_svg = 2500;
    const H_svg = 3330;
    
    // Sample wall image dimensions (approximate)
    const imgRect = {
        width: 800,  // Approximate width based on aspect ratio
        height: 1066 // 800 * (3330/2500)
    };
    
    const h11 = calibrationInv[0][0], h12 = calibrationInv[0][1], h13 = calibrationInv[0][2];
    const h21 = calibrationInv[1][0], h22 = calibrationInv[1][1], h23 = calibrationInv[1][2];
    const h31 = calibrationInv[2][0], h32 = calibrationInv[2][1], h33 = calibrationInv[2][2];
    
    // Calculate scale factors to map SVG coordinates to wall image coordinates
    const scaleX = imgRect.width / W_svg;
    const scaleY = imgRect.height / H_svg;
    
    // Apply scale to the transform matrix
    const m11 = h11 * scaleX, m12 = h12 * scaleY, m13 = h13 * imgRect.width;
    const m21 = h21 * scaleX, m22 = h22 * scaleY, m23 = h23 * imgRect.height;
    const m31 = h31 * scaleX, m32 = h32 * scaleY, m33 = h33;
    
    // CSS matrix3d expects COLUMN-MAJOR order!
    const matrixStr = `${m11}, ${m21}, 0, ${m31}, ${m12}, ${m22}, 0, ${m32}, 0, 0, 1, 0, ${m13}, ${m23}, 0, ${m33}`;
    
    console.log('Test transformation calculation:');
    console.log(`SVG dimensions: ${W_svg}x${H_svg}`);
    console.log(`Image dimensions: ${imgRect.width}x${imgRect.height}`);
    console.log(`Scale factors: x=${scaleX.toFixed(4)}, y=${scaleY.toFixed(4)}`);
    console.log('Transformation matrix:', matrixStr);
    
    // Test point transformation
    const testPoints = [
        { x: 0, y: 0 },      // Top-left corner
        { x: W_svg, y: 0 },  // Top-right corner
        { x: 0, y: H_svg },  // Bottom-left corner
        { x: W_svg, y: H_svg } // Bottom-right corner
    ];
    
    console.log('\nTesting corner points:');
    testPoints.forEach((point, index) => {
        // Transform using matrix3d
        const transformed = transformPoint(point, [
            m11, m21, 0, m31,
            m12, m22, 0, m32,
            0, 0, 1, 0,
            m13, m23, 0, m33
        ]);
        
        console.log(`Point ${index+1}: (${point.x}, ${point.y}) -> (${transformed.x.toFixed(1)}, ${transformed.y.toFixed(1)})`);
    });
}

// Transform a point using homogeneous coordinates and matrix3d
function transformPoint(point, matrix) {
    // Convert to homogeneous coordinates
    const x = point.x;
    const y = point.y;
    const z = 0;
    const w = 1;
    
    // Matrix multiplication
    const tx = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12] * w;
    const ty = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13] * w;
    const tz = matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14] * w;
    const tw = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15] * w;
    
    // Convert back to 2D coordinates
    return {
        x: tx / tw,
        y: ty / tw
    };
}

// Run test
testTransformCalculation();