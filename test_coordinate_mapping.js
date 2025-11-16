const fs = require('fs');

// Simple test to verify coordinate mapping
function testCoordinateMapping() {
    console.log('Testing coordinate mapping...');
    
    // Load the test SVG
    const svgContent = fs.readFileSync('./test_wall.svg', 'utf8');
    
    // Extract viewBox
    const viewBoxMatch = svgContent.match(/viewBox="([^"]+)"/);
    if (!viewBoxMatch) {
        console.error('No viewBox found');
        return;
    }
    
    const [vbX, vbY, vbWidth, vbHeight] = viewBoxMatch[1].split(' ').map(Number);
    console.log(`SVG viewBox: ${vbX}, ${vbY}, ${vbWidth}, ${vbHeight}`);
    
    // Extract width/height
    const widthMatch = svgContent.match(/width="([^"]+)"/);
    const heightMatch = svgContent.match(/height="([^"]+)"/);
    
    let svgWidth = vbWidth;
    let svgHeight = vbHeight;
    
    if (widthMatch) svgWidth = parseFloat(widthMatch[1]);
    if (heightMatch) svgHeight = parseFloat(heightMatch[1]);
    
    console.log(`SVG dimensions: ${svgWidth}x${svgHeight}`);
    
    // Test coordinate transformation
    const imageWidth = 480;
    const imageHeight = 640;
    
    console.log(`Image dimensions: ${imageWidth}x${imageHeight}`);
    
    // Test a point that should be in the first hold (center of first path)
    // First hold is at M 100 100 L 200 100 L 200 200 L 100 200 Z
    // Center should be at (150, 150)
    const testPoint = { x: 150, y: 150 };
    
    // Convert to normalized coordinates (as if from MediaPipe)
    const normalizedX = testPoint.x / imageWidth;
    const normalizedY = testPoint.y / imageHeight;
    
    console.log(`Test point: (${testPoint.x}, ${testPoint.y})`);
    console.log(`Normalized: (${normalizedX}, ${normalizedY})`);
    
    // Convert back to SVG coordinates using our algorithm
    const scaleX = svgWidth / imageWidth;
    const scaleY = svgHeight / imageHeight;
    
    const svgX = normalizedX * imageWidth * scaleX;
    const svgY = normalizedY * imageHeight * scaleY;
    
    console.log(`Scale factors: ${scaleX}, ${scaleY}`);
    console.log(`Converted back to SVG: (${svgX}, ${svgY})`);
    
    // Check if point is in first hold
    const firstHoldPoints = [
        { x: 100, y: 100 },
        { x: 200, y: 100 },
        { x: 200, y: 200 },
        { x: 100, y: 200 }
    ];
    
    function isPointInPolygon(point, polygon) {
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].x, yi = polygon[i].y;
            const xj = polygon[j].x, yj = polygon[j].y;
            
            const intersect = ((yi > point.y) !== (yj > point.y))
                && (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }
    
    const isInFirstHold = isPointInPolygon({ x: svgX, y: svgY }, firstHoldPoints);
    console.log(`Is point in first hold: ${isInFirstHold}`);
    
    // Test with the actual pose data from the test
    console.log('\nTesting with actual pose data:');
    const poseData = {
        leftWrist: { x: 0.25, y: 0.2 },  // From test data
        rightWrist: { x: 0.5, y: 0.4 }
    };
    
    const leftSvgX = poseData.leftWrist.x * imageWidth * scaleX;
    const leftSvgY = poseData.leftWrist.y * imageHeight * scaleY;
    
    const rightSvgX = poseData.rightWrist.x * imageWidth * scaleX;
    const rightSvgY = poseData.rightWrist.y * imageHeight * scaleY;
    
    console.log(`Left wrist in SVG: (${leftSvgX}, ${leftSvgY})`);
    console.log(`Right wrist in SVG: (${rightSvgX}, ${rightSvgY})`);
    
    const leftInFirstHold = isPointInPolygon({ x: leftSvgX, y: leftSvgY }, firstHoldPoints);
    const rightInFirstHold = isPointInPolygon({ x: rightSvgX, y: rightSvgY }, firstHoldPoints);
    
    console.log(`Left wrist in first hold: ${leftInFirstHold}`);
    console.log(`Right wrist in first hold: ${rightInFirstHold}`);
    
    // Test with all holds
    const holds = [
        { id: 'hold_0', points: [{x: 100, y: 100}, {x: 200, y: 100}, {x: 200, y: 200}, {x: 100, y: 200}] },
        { id: 'hold_1', points: [{x: 300, y: 100}, {x: 400, y: 100}, {x: 400, y: 200}, {x: 300, y: 200}] },
        { id: 'hold_2', points: [{x: 500, y: 100}, {x: 600, y: 100}, {x: 600, y: 200}, {x: 500, y: 200}] },
        { id: 'hold_3', points: [{x: 200, y: 300}, {x: 300, y: 300}, {x: 300, y: 400}, {x: 200, y: 400}] },
        { id: 'hold_101', points: [{x: 400, y: 300}, {x: 500, y: 300}, {x: 500, y: 400}, {x: 400, y: 400}] }
    ];
    
    console.log('\nChecking all holds:');
    holds.forEach(hold => {
        const leftInHold = isPointInPolygon({ x: leftSvgX, y: leftSvgY }, hold.points);
        const rightInHold = isPointInPolygon({ x: rightSvgX, y: rightSvgY }, hold.points);
        if (leftInHold || rightInHold) {
            console.log(`${hold.id}: LEFT=${leftInHold}, RIGHT=${rightInHold}`);
        }
    });
}

testCoordinateMapping();