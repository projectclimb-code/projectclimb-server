#!/usr/bin/env node

/**
 * Test script to verify coordinate transformation for touch detection
 */

// Mock commander to avoid command line parsing issues
const mockProgram = { opts: () => ({ debug: false }) };
const originalRequire = require;
require = function(id) {
  if (id === 'commander') {
    return { program: mockProgram };
  }
  return originalRequire.apply(this, arguments);
};

const { SVGParser, SVGHoldDetector } = originalRequire('./websocket_pose_session_tracker.js');
const fs = originalRequire('fs');

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
  
  // Get all hold status
  const allStatus = holdDetector.getAllHoldStatus();
  console.log('All hold status:');
  Object.entries(allStatus).forEach(([holdId, status]) => {
    console.log(`  ${holdId}: ${status.status}`);
  });
  
  console.log('\nTest completed!');
}

// Run the test
testCoordinateTransformation();