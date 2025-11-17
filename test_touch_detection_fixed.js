#!/usr/bin/env node

/**
 * Test script to verify touch detection with coordinate transformation
 */

const { XMLParser } = require('fast-xml-parser');

/**
 * SVG parser for extracting climbing hold information (simplified version)
 */
class SVGParser {
  constructor(svgContent) {
    this.svgContent = svgContent;
    this.parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: "@_"
    });
    this.svgData = null;
    this.holdPaths = {};
    this.parseSVG();
  }

  parseSVG() {
    try {
      this.svgData = this.parser.parse(this.svgContent);
      this.extractHoldPaths();
    } catch (error) {
      console.error(`Error parsing SVG: ${error.message}`);
      throw error;
    }
  }

  extractHoldPaths() {
    if (!this.svgData || !this.svgData.svg) {
      console.error('Invalid SVG structure');
      return;
    }

    const svg = this.svgData.svg;
    const paths = Array.isArray(svg.path) ? svg.path : [svg.path].filter(Boolean);
    
    paths.forEach((path, index) => {
      if (path && path['@_id']) {
        const holdId = path['@_id'];
        this.holdPaths[holdId] = {
          id: holdId,
          d: path['@_d'] || '',
          fill: path['@_fill'] || '#000000',
          stroke: path['@_stroke'] || '#000000',
          strokeWidth: path['@_stroke-width'] || '1'
        };
      }
    });

    console.log(`Extracted ${Object.keys(this.holdPaths).length} hold paths from SVG`);
  }

  getHoldPaths() {
    return this.holdPaths;
  }

  getHoldCenters() {
    const holdCenters = {};
    
    Object.entries(this.holdPaths).forEach(([holdId, pathData]) => {
      const center = this.calculatePathCenter(pathData.d);
      if (center) {
        holdCenters[holdId] = center;
      }
    });

    return holdCenters;
  }

  calculatePathCenter(pathData) {
    if (!pathData) return null;

    // Simple path parsing for basic shapes
    const numbers = pathData.match(/-?\d+\.?\d*/g);
    if (!numbers || numbers.length < 2) return null;

    let sumX = 0, sumY = 0, count = 0;
    
    for (let i = 0; i < numbers.length - 1; i += 2) {
      sumX += parseFloat(numbers[i]);
      sumY += parseFloat(numbers[i + 1]);
      count++;
    }

    if (count === 0) return null;

    return {
      x: sumX / count,
      y: sumY / count
    };
  }
}

/**
 * Simplified SVG Hold Detector for testing coordinate transformation
 */
class SVGHoldDetector {
  constructor(svgParser, proximityThreshold = 50.0, touchDuration = 2.0) {
    this.svgParser = svgParser;
    this.proximityThreshold = proximityThreshold;
    this.touchDuration = touchDuration;
    
    // Extract hold paths from SVG
    this.holdPaths = svgParser.getHoldPaths();
    this.holdCenters = svgParser.getHoldCenters();
    
    // Extract SVG dimensions for coordinate transformation
    this.svgDimensions = this.extractSVGDimensions();
    
    // Track hold touch state
    this.holdTouchStartTimes = {};
    this.holdStatus = {};
    this.touchedHolds = new Set();
    
    // MediaPipe landmark indices for hands
    this.leftHandIndices = [15, 17, 19, 21];
    this.rightHandIndices = [16, 18, 20, 22];
    
    // Video dimensions for coordinate transformation
    this.videoWidth = 640;
    this.videoHeight = 480;
  }

  extractSVGDimensions() {
    if (!this.svgParser.svgData || !this.svgParser.svgData.svg) {
      console.warn('Could not extract SVG dimensions, using defaults');
      return { width: 1000, height: 1000 };
    }
    
    const svg = this.svgParser.svgData.svg;
    const width = parseFloat(svg['@_width']) || 1000;
    const height = parseFloat(svg['@_height']) || 1000;
    
    console.log(`SVG dimensions: ${width}x${height}`);
    return { width, height };
  }

  /**
   * Transform pose coordinates from relative space (0-1) to SVG coordinate space
   */
  transformPoseToSVGCoordinates(landmarks) {
    if (!landmarks || landmarks.length === 0) {
      return [];
    }
    
    // Calculate scaling factors to maintain aspect ratio
    const videoAspectRatio = this.videoWidth / this.videoHeight; // 640/480 = 4/3
    const svgAspectRatio = this.svgDimensions.width / this.svgDimensions.height;
    
    let scaleX, scaleY, offsetX, offsetY;
    
    if (videoAspectRatio > svgAspectRatio) {
      // Video is wider than SVG, scale by height and center horizontally
      scaleY = this.svgDimensions.height;
      scaleX = scaleY * videoAspectRatio;
      offsetX = (this.svgDimensions.width - scaleX) / 2;
      offsetY = 0;
    } else {
      // Video is taller than SVG or same aspect ratio, scale by width and center vertically
      scaleX = this.svgDimensions.width;
      scaleY = scaleX / videoAspectRatio;
      offsetX = 0;
      offsetY = (this.svgDimensions.height - scaleY) / 2;
    }
    
    // Transform each landmark
    return landmarks.map(landmark => {
      // Convert from relative coordinates (0-1) to video coordinates (640x480)
      const videoX = landmark.x * this.videoWidth;
      const videoY = landmark.y * this.videoHeight;
      
      // Scale to SVG dimensions with centering
      const svgX = (videoX / this.videoWidth) * scaleX + offsetX;
      const svgY = (videoY / this.videoHeight) * scaleY + offsetY;
      
      return {
        ...landmark,
        x: svgX,
        y: svgY
      };
    });
  }

  getHandPosition(landmarks, handIndices) {
    const handPositions = [];
    
    handIndices.forEach(idx => {
      if (idx < landmarks.length) {
        const landmark = landmarks[idx];
        if (landmark.visibility > 0.5) {
          handPositions.push({ x: landmark.x, y: landmark.y });
        }
      }
    });
    
    if (handPositions.length > 0) {
      // Return average position
      const avgX = handPositions.reduce((sum, pos) => sum + pos.x, 0) / handPositions.length;
      const avgY = handPositions.reduce((sum, pos) => sum + pos.y, 0) / handPositions.length;
      return { x: avgX, y: avgY };
    }
    
    return null;
  }

  distance(pos1, pos2) {
    return Math.sqrt(Math.pow(pos1.x - pos2.x, 2) + Math.pow(pos1.y - pos2.y, 2));
  }

  detectHoldsTouched(landmarks) {
    if (!landmarks || landmarks.length === 0) {
      console.debug('No landmarks available');
      return {};
    }
    
    // Transform landmarks to SVG coordinate space for touch detection
    const svgLandmarks = this.transformPoseToSVGCoordinates(landmarks);
    
    // Extract hand positions using SVG coordinates for touch detection
    const leftHandPos = this.getHandPosition(svgLandmarks, this.leftHandIndices);
    const rightHandPos = this.getHandPosition(svgLandmarks, this.rightHandIndices);
    
    const currentTime = Date.now() / 1000;
    const statusChanges = {};
    
    // Check each hold for proximity to hands
    Object.entries(this.holdCenters).forEach(([holdId, holdCenter]) => {
      // Calculate distances using SVG coordinates
      const leftDist = leftHandPos ? this.distance(leftHandPos, holdCenter) : Infinity;
      const rightDist = rightHandPos ? this.distance(rightHandPos, holdCenter) : Infinity;
      
      const isNearLeft = leftHandPos && leftDist < this.proximityThreshold;
      const isNearRight = rightHandPos && rightDist < this.proximityThreshold;
      const isNearAnyHand = isNearLeft || isNearRight;
      
      if (isNearAnyHand) {
        if (!(holdId in this.holdTouchStartTimes)) {
          this.holdTouchStartTimes[holdId] = currentTime;
          console.log(`Hold ${holdId} touch started at ${currentTime}`);
        } else if (currentTime - this.holdTouchStartTimes[holdId] >= this.touchDuration) {
          // Has been touching long enough to count as completed
          if ((this.holdStatus[holdId] || 'untouched') === 'untouched') {
            this.holdStatus[holdId] = 'touched';
            statusChanges[holdId] = 'touched';
            this.touchedHolds.add(holdId);
            console.log(`Hold ${holdId} completed after ${this.touchDuration}s touch`);
          }
        }
      } else {
        if (holdId in this.holdTouchStartTimes) {
          delete this.holdTouchStartTimes[holdId];
          console.log(`Hold ${holdId} touch stopped`);
        }
      }
    });
    
    return statusChanges;
  }
}

// Mock SVG content for testing
const mockSVGContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1000" height="1000" xmlns="http://www.w3.org/2000/svg">
  <path id="hold1" d="M 100 100 L 150 100 L 150 150 L 100 150 Z" fill="#ff0000" />
  <path id="hold2" d="M 300 300 L 350 300 L 350 350 L 300 350 Z" fill="#00ff00" />
  <path id="hold3" d="M 500 500 L 550 500 L 550 550 L 500 550 Z" fill="#0000ff" />
</svg>`;

// Create a function to generate pose landmarks with hands at specific positions
function createPoseLandmarks(leftHandX, leftHandY, rightHandX, rightHandY) {
  const landmarks = [];
  
  // Add body landmarks (indices 0-14)
  for (let i = 0; i < 15; i++) {
    landmarks.push({ x: 0.5, y: 0.5, z: 0, visibility: 0.9 });
  }
  
  // Add hand landmarks (indices 15-22)
  landmarks[15] = { x: leftHandX, y: leftHandY, z: 0, visibility: 0.9 }; // left wrist
  landmarks[16] = { x: rightHandX, y: rightHandY, z: 0, visibility: 0.9 }; // right wrist
  landmarks[17] = { x: leftHandX, y: leftHandY, z: 0, visibility: 0.8 }; // left pinky
  landmarks[18] = { x: rightHandX, y: rightHandY, z: 0, visibility: 0.8 }; // right pinky
  landmarks[19] = { x: leftHandX, y: leftHandY, z: 0, visibility: 0.8 }; // left index
  landmarks[20] = { x: rightHandX, y: rightHandY, z: 0, visibility: 0.8 }; // right index
  landmarks[21] = { x: leftHandX, y: leftHandY, z: 0, visibility: 0.7 }; // left thumb
  landmarks[22] = { x: rightHandX, y: rightHandY, z: 0, visibility: 0.7 }; // right thumb
  
  return landmarks;
}

function calculateRelativePositionForSVG(svgX, svgY, holdDetector) {
  // Calculate scaling factors to maintain aspect ratio
  const videoAspectRatio = holdDetector.videoWidth / holdDetector.videoHeight;
  const svgAspectRatio = holdDetector.svgDimensions.width / holdDetector.svgDimensions.height;
  
  let scaleX, scaleY, offsetX, offsetY;
  
  if (videoAspectRatio > svgAspectRatio) {
    scaleY = holdDetector.svgDimensions.height;
    scaleX = scaleY * videoAspectRatio;
    offsetX = (holdDetector.svgDimensions.width - scaleX) / 2;
    offsetY = 0;
  } else {
    scaleX = holdDetector.svgDimensions.width;
    scaleY = scaleX / videoAspectRatio;
    offsetX = 0;
    offsetY = (holdDetector.svgDimensions.height - scaleY) / 2;
  }
  
  // Convert SVG coordinates back to relative coordinates
  const relativeX = ((svgX - offsetX) / scaleX);
  const relativeY = ((svgY - offsetY) / scaleY);
  
  return { x: relativeX, y: relativeY };
}

function testTouchDetection() {
  console.log('Testing touch detection with coordinate transformation...\n');
  
  // Create SVG parser
  const svgParser = new SVGParser(mockSVGContent);
  
  // Create hold detector with shorter touch duration for testing
  const holdDetector = new SVGHoldDetector(svgParser, 50.0, 0.5);
  
  console.log('SVG Dimensions:', holdDetector.svgDimensions);
  console.log('Video Dimensions:', holdDetector.videoWidth, 'x', holdDetector.videoHeight);
  
  // Test hold centers
  console.log('\nHold Centers:');
  console.log('=============');
  Object.entries(holdDetector.holdCenters).forEach(([holdId, center]) => {
    console.log(`${holdId}: (${center.x.toFixed(1)}, ${center.y.toFixed(1)})`);
  });
  
  // Test 1: Hands far from holds (no touch)
  console.log('\nTest 1: Hands far from holds');
  console.log('==============================');
  const landmarks1 = createPoseLandmarks(0.2, 0.2, 0.8, 0.8); // Hands in corners
  const statusChanges1 = holdDetector.detectHoldsTouched(landmarks1);
  console.log('Status changes:', statusChanges1);
  
  // Test 2: Left hand near hold1
  console.log('\nTest 2: Left hand near hold1');
  console.log('==============================');
  
  // Hold1 is at (125, 125) in SVG coordinates
  const hold1Relative = calculateRelativePositionForSVG(125, 125, holdDetector);
  console.log(`Calculated relative position for hold1: (${hold1Relative.x.toFixed(3)}, ${hold1Relative.y.toFixed(3)})`);
  
  const landmarks2 = createPoseLandmarks(hold1Relative.x, hold1Relative.y, 0.8, 0.8);
  const svgLandmarks2 = holdDetector.transformPoseToSVGCoordinates(landmarks2);
  const leftHandSVG2 = svgLandmarks2[15];
  console.log(`Transformed back to SVG: (${leftHandSVG2.x.toFixed(1)}, ${leftHandSVG2.y.toFixed(1)})`);
  
  const statusChanges2 = holdDetector.detectHoldsTouched(landmarks2);
  console.log('Status changes:', statusChanges2);
  
  // Simulate time passing for touch to complete
  setTimeout(() => {
    const statusChanges2b = holdDetector.detectHoldsTouched(landmarks2);
    console.log('Status changes after time:', statusChanges2b);
    
    // Test 3: Right hand near hold2
    console.log('\nTest 3: Right hand near hold2');
    console.log('===============================');
    // Hold2 is at (325, 325) in SVG coordinates
    const hold2Relative = calculateRelativePositionForSVG(325, 325, holdDetector);
    console.log(`Calculated relative position for hold2: (${hold2Relative.x.toFixed(3)}, ${hold2Relative.y.toFixed(3)})`);
    
    const landmarks3 = createPoseLandmarks(0.2, 0.2, hold2Relative.x, hold2Relative.y);
    const svgLandmarks3 = holdDetector.transformPoseToSVGCoordinates(landmarks3);
    const rightHandSVG3 = svgLandmarks3[16];
    console.log(`Transformed back to SVG: (${rightHandSVG3.x.toFixed(1)}, ${rightHandSVG3.y.toFixed(1)})`);
    
    const statusChanges3 = holdDetector.detectHoldsTouched(landmarks3);
    console.log('Status changes:', statusChanges3);
    
    // Simulate time passing for touch to complete
    setTimeout(() => {
      const statusChanges3b = holdDetector.detectHoldsTouched(landmarks3);
      console.log('Status changes after time:', statusChanges3b);
      
      console.log('\nTest completed!');
    }, 600);
  }, 600);
}

// Run test
testTouchDetection();