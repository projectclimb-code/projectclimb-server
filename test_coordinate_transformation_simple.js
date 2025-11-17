#!/usr/bin/env node

/**
 * Simple test script to verify coordinate transformation for touch detection
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

// Mock pose landmarks in relative coordinates (0-1 range)
const mockPoseLandmarks = [
  // Some body landmarks (indices 0-14)
  { x: 0.5, y: 0.2, z: 0, visibility: 0.9 },  // nose
  { x: 0.45, y: 0.25, z: 0, visibility: 0.8 }, // left eye
  { x: 0.55, y: 0.25, z: 0, visibility: 0.8 }, // right eye
  { x: 0.4, y: 0.3, z: 0, visibility: 0.7 },  // left ear
  { x: 0.6, y: 0.3, z: 0, visibility: 0.7 },  // right ear
  { x: 0.45, y: 0.4, z: 0, visibility: 0.9 }, // left shoulder
  { x: 0.55, y: 0.4, z: 0, visibility: 0.9 }, // right shoulder
  { x: 0.35, y: 0.6, z: 0, visibility: 0.8 }, // left elbow
  { x: 0.65, y: 0.6, z: 0, visibility: 0.8 }, // right elbow
  { x: 0.3, y: 0.8, z: 0, visibility: 0.7 },  // left wrist
  { x: 0.7, y: 0.8, z: 0, visibility: 0.7 },  // right wrist
  { x: 0.4, y: 0.5, z: 0, visibility: 0.8 },  // left hip
  { x: 0.6, y: 0.5, z: 0, visibility: 0.8 },  // right hip
  { x: 0.45, y: 0.7, z: 0, visibility: 0.7 }, // left knee
  { x: 0.55, y: 0.7, z: 0, visibility: 0.7 }, // right knee
  
  // Hand landmarks (indices 15-22)
  { x: 0.25, y: 0.85, z: 0, visibility: 0.9 }, // left wrist (15)
  { x: 0.75, y: 0.85, z: 0, visibility: 0.9 }, // right wrist (16)
  { x: 0.2, y: 0.9, z: 0, visibility: 0.8 },  // left pinky (17)
  { x: 0.8, y: 0.9, z: 0, visibility: 0.8 },  // right pinky (18)
  { x: 0.22, y: 0.88, z: 0, visibility: 0.8 }, // left index (19)
  { x: 0.78, y: 0.88, z: 0, visibility: 0.8 }, // right index (20)
  { x: 0.18, y: 0.92, z: 0, visibility: 0.7 }, // left thumb (21)
  { x: 0.82, y: 0.92, z: 0, visibility: 0.7 }, // right thumb (22)
];

function testCoordinateTransformation() {
  console.log('Testing coordinate transformation for touch detection...\n');
  
  // Create SVG parser
  const svgParser = new SVGParser(mockSVGContent);
  
  // Create hold detector
  const holdDetector = new SVGHoldDetector(svgParser, 50.0, 2.0);
  
  console.log('SVG Dimensions:', holdDetector.svgDimensions);
  console.log('Video Dimensions:', holdDetector.videoWidth, 'x', holdDetector.videoHeight);
  
  // Test coordinate transformation
  const svgLandmarks = holdDetector.transformPoseToSVGCoordinates(mockPoseLandmarks);
  
  console.log('\nCoordinate Transformation Test:');
  console.log('================================');
  
  // Check hand landmarks specifically
  const leftWristOriginal = mockPoseLandmarks[15]; // Left wrist
  const rightWristOriginal = mockPoseLandmarks[16]; // Right wrist
  const leftWristTransformed = svgLandmarks[15];
  const rightWristTransformed = svgLandmarks[16];
  
  console.log('Left Wrist:');
  console.log(`  Original (relative): (${leftWristOriginal.x.toFixed(3)}, ${leftWristOriginal.y.toFixed(3)})`);
  console.log(`  Transformed (SVG): (${leftWristTransformed.x.toFixed(1)}, ${leftWristTransformed.y.toFixed(1)})`);
  
  console.log('Right Wrist:');
  console.log(`  Original (relative): (${rightWristOriginal.x.toFixed(3)}, ${rightWristOriginal.y.toFixed(3)})`);
  console.log(`  Transformed (SVG): (${rightWristTransformed.x.toFixed(1)}, ${rightWristTransformed.y.toFixed(1)})`);
  
  // Test hold centers
  console.log('\nHold Centers:');
  console.log('=============');
  Object.entries(holdDetector.holdCenters).forEach(([holdId, center]) => {
    console.log(`${holdId}: (${center.x.toFixed(1)}, ${center.y.toFixed(1)})`);
  });
  
  // Test touch detection
  console.log('\nTouch Detection Test:');
  console.log('=====================');
  const statusChanges = holdDetector.detectHoldsTouched(mockPoseLandmarks);
  console.log('Status changes:', statusChanges);
  
  console.log('\nTest completed!');
}

// Run test
testCoordinateTransformation();