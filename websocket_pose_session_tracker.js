#!/usr/bin/env node

/**
 * WebSocket-based pose session tracker with hold detection for climbing walls
 * 
 * This script connects to an input WebSocket to receive MediaPipe pose data,
 * transforms the landmarks using wall calibration,
 * detects hold touches based on hand proximity to SVG paths,
 * and outputs session data in the specified JSON format.
 * 
 * Features:
 * - Pose transformation using wall calibration
 * - Extended hand landmarks beyond the palm
 * - Hold detection using SVG paths
 * - Configurable output (landmarks and/or SVG paths)
 * - Session tracking with hold status and timestamps
 */

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const { program } = require('commander');
const { XMLParser } = require('fast-xml-parser');
const math = require('mathjs');
const https = require('https');
const http = require('http');
const { URL } = require('url');

// Configure command line options
program
  .requiredOption('--svg <path>', 'Path to SVG file containing climbing wall holds')
  .option('--calibration <path>', 'Path to calibration JSON file or URL to fetch calibration data')
  .option('--input-websocket-url <url>', 'WebSocket URL for receiving pose data', 'ws://localhost:8080')
  .option('--output-websocket-url <url>', 'WebSocket URL for sending session data', 'ws://localhost:8081')
  .option('--no-stream-landmarks', 'Skip streaming transformed landmarks in output')
  .option('--stream-svg-only', 'Stream only SVG paths that are touched')
  .option('--route-data <path>', 'Route data as JSON string or path to JSON file with holds specification')
  .option('--proximity-threshold <number>', 'Distance in pixels to consider hand near hold', '50.0')
  .option('--touch-duration <number>', 'Time in seconds hand must be near hold to count as touch', '2.0')
  .option('--reconnect-delay <number>', 'Delay between reconnection attempts in seconds', '5.0')
  .option('--debug', 'Enable debug output')
  .parse();

const options = program.opts();

// Logger implementation
const logger = {
  info: (msg) => console.log(`[INFO] ${new Date().toISOString()} ${msg}`),
  error: (msg) => console.error(`[ERROR] ${new Date().toISOString()} ${msg}`),
  debug: (msg) => options.debug && console.log(`[DEBUG] ${new Date().toISOString()} ${msg}`),
  warning: (msg) => console.warn(`[WARNING] ${new Date().toISOString()} ${msg}`)
};

/**
 * WebSocket client for receiving MediaPipe pose data
 */
class InputWebSocketClient {
  constructor(url, messageHandler, reconnectDelay = 5.0) {
    this.url = url;
    this.messageHandler = messageHandler;
    this.reconnectDelay = reconnectDelay;
    this.websocket = null;
    this.running = false;
    this.currentReconnectDelay = reconnectDelay;
  }

  async connect() {
    while (this.running) {
      try {
        logger.info(`Connecting to input WebSocket: ${this.url}`);
        
        this.websocket = new WebSocket(this.url, {
          handshakeTimeout: 30000,
          perMessageDeflate: false
        });

        await new Promise((resolve, reject) => {
          this.websocket.on('open', () => {
            logger.info('Successfully connected to input WebSocket');
            this.currentReconnectDelay = this.reconnectDelay;
            resolve();
          });

          this.websocket.on('message', async (data) => {
            try {
              const message = data.toString();
              const jsonData = JSON.parse(message);
              await this.messageHandler(jsonData);
            } catch (error) {
              if (error instanceof SyntaxError) {
                logger.error(`Invalid JSON received: ${error.message}`);
              } else {
                logger.error(`Error processing message: ${error.message}`);
              }
            }
          });

          this.websocket.on('close', () => {
            logger.warning('Input WebSocket connection closed');
            reject(new Error('Connection closed'));
          });

          this.websocket.on('error', (error) => {
            logger.error(`Input WebSocket error: ${error.message}`);
            reject(error);
          });
        });

        // Listen for messages
        await this.listenForMessages();

      } catch (error) {
        logger.error(`Input WebSocket connection error: ${error.message}`);
        if (this.running) {
          await this.waitAndReconnect();
        }
      }
    }
  }

  async waitAndReconnect() {
    logger.info(`Reconnecting in ${this.currentReconnectDelay} seconds...`);
    await new Promise(resolve => setTimeout(resolve, this.currentReconnectDelay * 1000));
    this.currentReconnectDelay = Math.min(this.currentReconnectDelay * 2, 60.0);
  }

  async listenForMessages() {
    return new Promise((resolve, reject) => {
      // Message handling is done in the connect method
      this.websocket.on('close', () => {
        reject(new Error('Connection closed during listening'));
      });
    });
  }

  start() {
    this.running = true;
    return this.connect();
  }

  stop() {
    this.running = false;
    if (this.websocket) {
      this.websocket.close();
    }
  }
}

/**
 * WebSocket client for sending session data
 */
class OutputWebSocketClient {
  constructor(url, reconnectDelay = 5.0) {
    this.url = url;
    this.reconnectDelay = reconnectDelay;
    this.websocket = null;
    this.running = false;
    this.currentReconnectDelay = reconnectDelay;
    this.messageQueue = [];
    this.senderInterval = null;
  }

  async connect() {
    while (this.running) {
      try {
        logger.info(`Connecting to output WebSocket: ${this.url}`);
        
        this.websocket = new WebSocket(this.url, {
          handshakeTimeout: 30000,
          perMessageDeflate: false
        });

        await new Promise((resolve, reject) => {
          this.websocket.on('open', () => {
            logger.info('Successfully connected to output WebSocket');
            this.currentReconnectDelay = this.reconnectDelay;
            this.startMessageSender();
            this.startKeepAlive();
            resolve();
          });

          this.websocket.on('close', () => {
            logger.warning('Output WebSocket connection closed');
            this.stopMessageSender();
            reject(new Error('Connection closed'));
          });

          this.websocket.on('error', (error) => {
            logger.error(`Output WebSocket error: ${error.message}`);
            this.stopMessageSender();
            reject(error);
          });
        });

        // Wait for connection to close
        await new Promise((resolve, reject) => {
          this.websocket.on('close', resolve);
        });

      } catch (error) {
        logger.error(`Output WebSocket connection error: ${error.message}`);
        if (this.running) {
          await this.waitAndReconnect();
        }
      }
    }
  }

  async waitAndReconnect() {
    logger.info(`Reconnecting in ${this.currentReconnectDelay} seconds...`);
    await new Promise(resolve => setTimeout(resolve, this.currentReconnectDelay * 1000));
    this.currentReconnectDelay = Math.min(this.currentReconnectDelay * 2, 60.0);
  }

  startKeepAlive() {
    this.keepAliveInterval = setInterval(() => {
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.ping();
        logger.debug('Ping sent to keep connection alive');
      } else {
        logger.warning('WebSocket is closed, stopping keep-alive');
        this.stopKeepAlive();
      }
    }, 10000);
  }

  stopKeepAlive() {
    if (this.keepAliveInterval) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
  }

  startMessageSender() {
    this.senderInterval = setInterval(() => {
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        while (this.messageQueue.length > 0) {
          const message = this.messageQueue.shift();
          try {
            this.websocket.send(JSON.stringify(message));
            logger.debug('Sent message');
          } catch (error) {
            logger.error(`Error sending message: ${error.message}`);
            // Re-queue message
            this.messageQueue.unshift(message);
            break;
          }
        }
      }
    }, 100);
  }

  stopMessageSender() {
    if (this.senderInterval) {
      clearInterval(this.senderInterval);
      this.senderInterval = null;
    }
  }

  async sendMessage(message) {
    this.messageQueue.push(message);
  }

  start() {
    this.running = true;
    return this.connect();
  }

  stop() {
    this.running = false;
    this.stopMessageSender();
    this.stopKeepAlive();
    if (this.websocket) {
      this.websocket.close();
    }
  }
}

/**
 * SVG parser for extracting climbing hold information
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
      logger.error(`Error parsing SVG: ${error.message}`);
      throw error;
    }
  }

  extractHoldPaths() {
    if (!this.svgData || !this.svgData.svg) {
      logger.error('Invalid SVG structure');
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

    logger.info(`Extracted ${Object.keys(this.holdPaths).length} hold paths from SVG`);
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
    // This is a simplified implementation - you might want to use a more sophisticated SVG path parser
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
 * Detects hold touches based on hand proximity to SVG paths
 */
class SVGHoldDetector {
  constructor(svgParser, proximityThreshold = 50.0, touchDuration = 2.0, routeHolds = null) {
    this.svgParser = svgParser;
    this.proximityThreshold = proximityThreshold;
    this.touchDuration = touchDuration;
    this.routeHolds = routeHolds;
    
    // Extract hold paths from SVG
    this.holdPaths = svgParser.getHoldPaths();
    this.holdCenters = svgParser.getHoldCenters();
    
    // Filter holds based on route if provided
    if (this.routeHolds) {
      this.filterHoldsByRoute();
    }
    
    // Track hold touch state
    this.holdTouchStartTimes = {}; // hold_id -> timestamp when touch started
    this.holdStatus = {}; // hold_id -> status ('untouched', 'completed')
    this.touchedHolds = new Set(); // Track holds that have been touched in current session
    
    // MediaPipe landmark indices for hands
    this.leftHandIndices = [15, 17, 19, 21]; // Left wrist, pinky, index, thumb
    this.rightHandIndices = [16, 18, 20, 22]; // Right wrist, pinky, index, thumb
  }

  filterHoldsByRoute() {
    if (!this.routeHolds) return;
    
    // Filter hold centers
    const filteredCenters = {};
    Object.entries(this.holdCenters).forEach(([holdId, center]) => {
      if (this.routeHolds[holdId]) {
        filteredCenters[holdId] = center;
      }
    });
    this.holdCenters = filteredCenters;
    
    // Filter hold paths
    const filteredPaths = {};
    Object.entries(this.holdPaths).forEach(([holdId, pathData]) => {
      if (this.routeHolds[holdId]) {
        filteredPaths[holdId] = pathData;
      }
    });
    this.holdPaths = filteredPaths;
    
    logger.info(`Filtered to ${Object.keys(this.holdCenters).length} holds from route`);
  }

  detectHoldsTouched(transformedLandmarks) {
    if (!transformedLandmarks || transformedLandmarks.length === 0) {
      logger.debug('No transformed landmarks available');
      return {};
    }
    
    // Extract hand positions
    const leftHandPos = this.getHandPosition(transformedLandmarks, this.leftHandIndices);
    const rightHandPos = this.getHandPosition(transformedLandmarks, this.rightHandIndices);
    
    const currentTime = Date.now() / 1000; // Convert to seconds
    const statusChanges = {};
    
    // Check each hold for proximity to hands
    Object.entries(this.holdCenters).forEach(([holdId, holdCenter]) => {
      // Calculate distances
      const leftDist = leftHandPos ? this.distance(leftHandPos, holdCenter) : Infinity;
      const rightDist = rightHandPos ? this.distance(rightHandPos, holdCenter) : Infinity;
      const minDist = Math.min(leftDist, rightDist);
      
      const isNearLeft = leftHandPos && leftDist < this.proximityThreshold;
      const isNearRight = rightHandPos && rightDist < this.proximityThreshold;
      const isNearAnyHand = isNearLeft || isNearRight;
      
      const currentStatus = this.holdStatus[holdId] || 'untouched';
      
      if (isNearAnyHand) {
        // Hand is near the hold
        if (!(holdId in this.holdTouchStartTimes)) {
          // Just started touching this hold
          this.holdTouchStartTimes[holdId] = currentTime;
          logger.debug(`Hold ${holdId} touch started at ${currentTime}`);
        } else if (currentTime - this.holdTouchStartTimes[holdId] >= this.touchDuration) {
          // Has been touching long enough to count as completed
          if (currentStatus === 'untouched') {
            this.holdStatus[holdId] = 'touched';
            statusChanges[holdId] = 'touched';
            this.touchedHolds.add(holdId);
            logger.info(`Hold ${holdId} completed after ${this.touchDuration}s touch`);
          }
        }
      } else {
        // Hand is not near the hold
        if (holdId in this.holdTouchStartTimes) {
          // Was touching but now stopped
          delete this.holdTouchStartTimes[holdId];
          logger.debug(`Hold ${holdId} touch stopped`);
        }
      }
    });
    
    return statusChanges;
  }

  getTouchedSvgPaths() {
    const touchedPaths = [];
    this.touchedHolds.forEach(holdId => {
      if (this.holdPaths[holdId]) {
        const pathData = { ...this.holdPaths[holdId] };
        pathData.touched = true;
        pathData.touchTime = this.holdTouchStartTimes[holdId];
        touchedPaths.push(pathData);
      }
    });
    return touchedPaths;
  }

  getHandPosition(landmarks, handIndices) {
    const handPositions = [];
    
    handIndices.forEach(idx => {
      if (idx < landmarks.length) {
        const landmark = landmarks[idx];
        if (landmark.visibility > 0.5) { // Only use visible landmarks
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

  getAllHoldStatus() {
    const allHolds = {};
    
    Object.keys(this.holdCenters).forEach(holdId => {
      const status = this.holdStatus[holdId] || 'untouched';
      let completionTime = null;
      
      if (status === 'touched' && this.holdTouchStartTimes[holdId]) {
        completionTime = new Date(
          (this.holdTouchStartTimes[holdId] + this.touchDuration) * 1000
        ).toISOString();
      }
      
      // Determine hold type from route or based on ID
      let holdType = 'normal';
      if (this.routeHolds && this.routeHolds[holdId]) {
        holdType = this.routeHolds[holdId];
      } else {
        // Fallback to ID-based detection
        if (holdId.startsWith('start_')) {
          holdType = 'start';
        } else if (holdId.startsWith('finish_')) {
          holdType = 'finish';
        }
      }
      
      allHolds[holdId] = {
        id: holdId,
        type: holdType,
        status: status,
        time: completionTime
      };
    });
    
    return allHolds;
  }
}

/**
 * Tracks climbing session state and hold progress
 */
class SessionTracker {
  constructor(holdDetector) {
    this.holdDetector = holdDetector;
    
    // Session state
    this.sessionStartTime = new Date();
    this.sessionEndTime = null;
    this.sessionStatus = 'started';
    
    // Track if this is the first pose data
    this.firstPoseReceived = false;
  }

  updateSession(transformedLandmarks) {
    if (!this.firstPoseReceived) {
      this.firstPoseReceived = true;
      logger.info(`Session started at ${this.sessionStartTime.toISOString()}`);
    }
    
    // Detect hold touches
    const statusChanges = this.holdDetector.detectHoldsTouched(transformedLandmarks);
    
    // Get current hold status
    const allHolds = this.holdDetector.getAllHoldStatus();
    
    // Convert to list format
    const holdsList = Object.values(allHolds);
    
    // Create session data
    const sessionData = {
      session: {
        holds: holdsList,
        startTime: this.sessionStartTime.toISOString(),
        endTime: this.sessionEndTime ? this.sessionEndTime.toISOString() : null,
        status: this.sessionStatus
      },
      pose: transformedLandmarks
    };
    
    return sessionData;
  }

  getSessionData(includePose = true, includeSvgPaths = false) {
    // Get current hold status
    const allHolds = this.holdDetector.getAllHoldStatus();
    const holdsList = Object.values(allHolds);
    
    // Create base session data
    const sessionData = {
      session: {
        holds: holdsList,
        startTime: this.sessionStartTime.toISOString(),
        endTime: this.sessionEndTime ? this.sessionEndTime.toISOString() : null,
        status: this.sessionStatus
      }
    };
    
    // Add pose data if requested
    if (includePose) {
      sessionData.pose = []; // Will be populated by caller
    }
    
    // Add SVG paths if requested
    if (includeSvgPaths) {
      sessionData.touched_svg_paths = this.holdDetector.getTouchedSvgPaths();
    }
    
    return sessionData;
  }

  endSession() {
    this.sessionEndTime = new Date();
    this.sessionStatus = 'completed';
    logger.info(`Session ended at ${this.sessionEndTime.toISOString()}`);
  }
}

/**
 * Validates incoming pose data format
 */
function validatePoseData(data) {
  if (!data || typeof data !== 'object') {
    return { valid: false, error: 'Data must be an object' };
  }
  
  if (!data.landmarks || !Array.isArray(data.landmarks)) {
    return { valid: false, error: 'Missing or invalid landmarks field' };
  }
  
  for (let i = 0; i < data.landmarks.length; i++) {
    const landmark = data.landmarks[i];
    if (!landmark || typeof landmark !== 'object') {
      return { valid: false, error: `Landmark ${i} must be an object` };
    }
    
    const requiredFields = ['x', 'y', 'z', 'visibility'];
    for (const field of requiredFields) {
      if (!(field in landmark) || typeof landmark[field] !== 'number') {
        return { valid: false, error: `Landmark ${i} missing or invalid '${field}' field` };
      }
    }
  }
  
  return { valid: true, error: 'Valid' };
}

/**
 * Calculate extended hand landmarks beyond the palm
 */
function calculateExtendedHandLandmarks(landmarks, extensionPercent) {
  // MediaPipe pose landmark indices for hands
  const LEFT_WRIST = 15;
  const LEFT_PINKY = 17;
  const LEFT_INDEX = 19;
  const LEFT_THUMB = 21;
  
  const RIGHT_WRIST = 16;
  const RIGHT_PINKY = 18;
  const RIGHT_INDEX = 20;
  const RIGHT_THUMB = 22;
  
  // Elbow landmarks for direction calculation
  const LEFT_ELBOW = 13;
  const RIGHT_ELBOW = 14;
  
  const newLandmarks = [];
  
  // Calculate left hand extension
  if (LEFT_WRIST < landmarks.length && LEFT_PINKY < landmarks.length && 
      LEFT_INDEX < landmarks.length && LEFT_THUMB < landmarks.length && 
      LEFT_ELBOW < landmarks.length) {
    
    // Get palm center as average of hand landmarks
    const palmCenterX = (landmarks[LEFT_WRIST].x + landmarks[LEFT_PINKY].x + 
                         landmarks[LEFT_INDEX].x + landmarks[LEFT_THUMB].x) / 4;
    const palmCenterY = (landmarks[LEFT_WRIST].y + landmarks[LEFT_PINKY].y + 
                         landmarks[LEFT_INDEX].y + landmarks[LEFT_THUMB].y) / 4;
    const palmCenterZ = (landmarks[LEFT_WRIST].z + landmarks[LEFT_PINKY].z + 
                         landmarks[LEFT_INDEX].z + landmarks[LEFT_THUMB].z) / 4;
    
    // Calculate direction from elbow to palm center
    const elbowToPalmX = palmCenterX - landmarks[LEFT_ELBOW].x;
    const elbowToPalmY = palmCenterY - landmarks[LEFT_ELBOW].y;
    const elbowToPalmZ = palmCenterZ - landmarks[LEFT_ELBOW].z;
    
    // Normalize direction vector
    let magnitude = Math.sqrt(elbowToPalmX ** 2 + elbowToPalmY ** 2 + elbowToPalmZ ** 2);
    if (magnitude > 0) {
      const normalizedX = elbowToPalmX / magnitude;
      const normalizedY = elbowToPalmY / magnitude;
      const normalizedZ = elbowToPalmZ / magnitude;
      
      // Calculate palm size for scaling
      const palmSize = Math.sqrt(
        (landmarks[LEFT_PINKY].x - landmarks[LEFT_INDEX].x) ** 2 +
        (landmarks[LEFT_PINKY].y - landmarks[LEFT_INDEX].y) ** 2 +
        (landmarks[LEFT_PINKY].z - landmarks[LEFT_INDEX].z) ** 2
      );
      
      // Calculate extension distance
      const extensionDistance = palmSize * (extensionPercent / 100.0);
      
      // Create new landmark
      const newLandmark = {
        x: palmCenterX + normalizedX * extensionDistance,
        y: palmCenterY + normalizedY * extensionDistance,
        z: palmCenterZ + normalizedZ * extensionDistance,
        visibility: Math.min(
          landmarks[LEFT_WRIST].visibility,
          landmarks[LEFT_PINKY].visibility,
          landmarks[LEFT_INDEX].visibility,
          landmarks[LEFT_THUMB].visibility
        )
      };
      newLandmarks.push(newLandmark);
    }
  }
  
  // Calculate right hand extension
  if (RIGHT_WRIST < landmarks.length && RIGHT_PINKY < landmarks.length && 
      RIGHT_INDEX < landmarks.length && RIGHT_THUMB < landmarks.length && 
      RIGHT_ELBOW < landmarks.length) {
    
    // Get palm center as average of hand landmarks
    const palmCenterX = (landmarks[RIGHT_WRIST].x + landmarks[RIGHT_PINKY].x + 
                         landmarks[RIGHT_INDEX].x + landmarks[RIGHT_THUMB].x) / 4;
    const palmCenterY = (landmarks[RIGHT_WRIST].y + landmarks[RIGHT_PINKY].y + 
                         landmarks[RIGHT_INDEX].y + landmarks[RIGHT_THUMB].y) / 4;
    const palmCenterZ = (landmarks[RIGHT_WRIST].z + landmarks[RIGHT_PINKY].z + 
                         landmarks[RIGHT_INDEX].z + landmarks[RIGHT_THUMB].z) / 4;
    
    // Calculate direction from elbow to palm center
    const elbowToPalmX = palmCenterX - landmarks[RIGHT_ELBOW].x;
    const elbowToPalmY = palmCenterY - landmarks[RIGHT_ELBOW].y;
    const elbowToPalmZ = palmCenterZ - landmarks[RIGHT_ELBOW].z;
    
    // Normalize direction vector
    let magnitude = Math.sqrt(elbowToPalmX ** 2 + elbowToPalmY ** 2 + elbowToPalmZ ** 2);
    if (magnitude > 0) {
      const normalizedX = elbowToPalmX / magnitude;
      const normalizedY = elbowToPalmY / magnitude;
      const normalizedZ = elbowToPalmZ / magnitude;
      
      // Calculate palm size for scaling
      const palmSize = Math.sqrt(
        (landmarks[RIGHT_PINKY].x - landmarks[RIGHT_INDEX].x) ** 2 +
        (landmarks[RIGHT_PINKY].y - landmarks[RIGHT_INDEX].y) ** 2 +
        (landmarks[RIGHT_PINKY].z - landmarks[RIGHT_INDEX].z) ** 2
      );
      
      // Calculate extension distance
      const extensionDistance = palmSize * (extensionPercent / 100.0);
      
      // Create new landmark
      const newLandmark = {
        x: palmCenterX + normalizedX * extensionDistance,
        y: palmCenterY + normalizedY * extensionDistance,
        z: palmCenterZ + normalizedZ * extensionDistance,
        visibility: Math.min(
          landmarks[RIGHT_WRIST].visibility,
          landmarks[RIGHT_PINKY].visibility,
          landmarks[RIGHT_INDEX].visibility,
          landmarks[RIGHT_THUMB].visibility
        )
      };
      newLandmarks.push(newLandmark);
    }
  }
  
  return newLandmarks;
}

/**
 * Apply homography transformation to MediaPipe pose data
 */
function applyHomographyToMediaPipeJSON(poseData, transformMatrix) {
  if (!poseData.landmarks || !Array.isArray(poseData.landmarks)) {
    return poseData;
  }
  
  const transformedLandmarks = poseData.landmarks.map(landmark => {
    const point = [landmark.x, landmark.y, 1];
    const transformed = math.multiply(transformMatrix, point);
    
    return {
      ...landmark,
      x: transformed[0] / transformed[2],
      y: transformed[1] / transformed[2]
    };
  });
  
  return {
    ...poseData,
    landmarks: transformedLandmarks
  };
}

/**
 * Main WebSocket pose session tracker class
 */
class WebSocketPoseSessionTracker {
  constructor(svgPath, calibrationPath = null, inputWebSocketUrl, outputWebSocketUrl,
              proximityThreshold = 50.0, touchDuration = 2.0,
              reconnectDelay = 5.0, debug = false,
              noStreamLandmarks = false, streamSvgOnly = false, routeData = null) {
    
    this.svgPath = svgPath;
    this.calibrationPath = calibrationPath;
    this.inputWebSocketUrl = inputWebSocketUrl;
    this.outputWebSocketUrl = outputWebSocketUrl;
    this.proximityThreshold = proximityThreshold;
    this.touchDuration = touchDuration;
    this.reconnectDelay = reconnectDelay;
    this.debug = debug;
    this.noStreamLandmarks = noStreamLandmarks;
    this.streamSvgOnly = streamSvgOnly;
    this.routeData = routeData;
    
    // Components
    this.svgParser = null;
    this.holdDetector = null;
    this.sessionTracker = null;
    this.calibrationMatrix = null;
    this.handExtensionPercent = 20.0;
    
    // WebSocket clients
    this.inputClient = null;
    this.outputClient = null;
    
    // State
    this.running = false;
    this.messageCount = 0;
    this.startTime = Date.now();
  }

  /**
   * Fetch calibration data from URL
   */
  async fetchCalibrationFromUrl(url) {
    return new Promise((resolve, reject) => {
      const protocol = url.startsWith('https://') ? https : http;
      
      const request = protocol.get(url, (response) => {
        let data = '';
        
        response.on('data', (chunk) => {
          data += chunk;
        });
        
        response.on('end', () => {
          try {
            const calibration = JSON.parse(data);
            resolve(calibration);
          } catch (error) {
            reject(new Error(`Failed to parse calibration JSON: ${error.message}`));
          }
        });
      });
      
      request.on('error', (error) => {
        reject(new Error(`Failed to fetch calibration: ${error.message}`));
      });
      
      request.setTimeout(10000, () => {
        request.destroy();
        reject(new Error('Calibration fetch timeout after 10 seconds'));
      });
    });
  }

  async setup() {
    try {
      // Load SVG file
      const svgContent = fs.readFileSync(this.svgPath, 'utf8');
      this.svgParser = new SVGParser(svgContent);
      logger.info(`Loaded SVG file: ${this.svgPath}`);
      
      // Load calibration if provided
      if (this.calibrationPath) {
        let calibration;
        
        if (this.calibrationPath.startsWith('http://') || this.calibrationPath.startsWith('https://')) {
          // Fetch calibration from URL
          try {
            calibration = await this.fetchCalibrationFromUrl(this.calibrationPath);
            logger.info(`Loaded calibration from URL: ${this.calibrationPath}`);
          } catch (error) {
            logger.error(`Failed to fetch calibration from URL: ${error.message}`);
            throw error;
          }
        } else {
          // Load calibration from file
          try {
            const calibrationContent = fs.readFileSync(this.calibrationPath, 'utf8');
            calibration = JSON.parse(calibrationContent);
            logger.info(`Loaded calibration from file: ${this.calibrationPath}`);
          } catch (error) {
            logger.error(`Failed to load calibration from file: ${error.message}`);
            throw error;
          }
        }
        
        if (calibration.perspective_transform) {
          this.calibrationMatrix = calibration.perspective_transform;
          logger.info('Loaded calibration matrix');
        }
        
        if (calibration.hand_extension_percent) {
          this.handExtensionPercent = calibration.hand_extension_percent;
          logger.info(`Using hand extension percent: ${this.handExtensionPercent}%`);
        }
      }
      
      // Get route holds if route data is provided
      let routeHolds = null;
      if (this.routeData) {
        routeHolds = this.extractRouteHolds(this.routeData);
      }
      
      // Setup hold detector with route filtering
      this.holdDetector = new SVGHoldDetector(
        this.svgParser,
        this.proximityThreshold,
        this.touchDuration,
        routeHolds
      );
      
      // Setup session tracker
      this.sessionTracker = new SessionTracker(this.holdDetector);
      
      // Setup WebSocket clients
      this.inputClient = new InputWebSocketClient(
        this.inputWebSocketUrl,
        this.handlePoseData.bind(this),
        this.reconnectDelay
      );
      
      this.outputClient = new OutputWebSocketClient(
        this.outputWebSocketUrl,
        this.reconnectDelay
      );
      
      return true;
    } catch (error) {
      logger.error(`Setup failed: ${error.message}`);
      return false;
    }
  }

  extractRouteHolds(routeData) {
    if (!routeData || !routeData.problem || !routeData.problem.holds) {
      return null;
    }
    
    const routeHolds = {};
    routeData.problem.holds.forEach(hold => {
      if (hold.id) {
        routeHolds[hold.id.toString()] = hold.type || 'normal';
      }
    });
    
    logger.info(`Loaded route with ${Object.keys(routeHolds).length} holds: ${Object.keys(routeHolds)}`);
    return routeHolds;
  }

  async handlePoseData(poseData) {
    try {
      // Validate pose data
      const validation = validatePoseData(poseData);
      if (!validation.valid) {
        logger.warning(`Invalid pose data: ${validation.error}`);
        return;
      }
      
      // Apply transformation if calibration matrix is available
      let transformedData = poseData;
      if (this.calibrationMatrix) {
        transformedData = applyHomographyToMediaPipeJSON(
          poseData,
          this.calibrationMatrix
        );
      }
      
      // Add extended hand landmarks
      const landmarks = transformedData.landmarks || [];
      if (landmarks.length > 0) {
        const extendedLandmarks = calculateExtendedHandLandmarks(
          landmarks,
          this.handExtensionPercent
        );
        
        // Add the new landmarks to the data
        if (!transformedData.extended_hand_landmarks) {
          transformedData.extended_hand_landmarks = [];
        }
        transformedData.extended_hand_landmarks.push(...extendedLandmarks);
        
        // Also add them to the main landmarks list for compatibility
        landmarks.push(...extendedLandmarks);
        transformedData.landmarks = landmarks;
      }
      
      // Update session with transformed landmarks
      const sessionData = this.sessionTracker.updateSession(landmarks);
      
      // Format output based on flags
      const outputData = this.sessionTracker.getSessionData(
        !this.noStreamLandmarks,
        this.streamSvgOnly
      );
      
      // Add pose data if included
      if (!this.noStreamLandmarks) {
        outputData.pose = landmarks;
      }
      
      // Send session data
      await this.sendSessionData(outputData);
      
      this.messageCount++;
      
      // Log progress every 100 messages
      if (this.messageCount % 100 === 0) {
        const elapsed = (Date.now() - this.startTime) / 1000;
        const rate = this.messageCount / elapsed;
        logger.info(`Processed ${this.messageCount} messages (${rate.toFixed(2)} msg/sec)`);
      }
      
      if (this.debug) {
        logger.info(`Processed pose data with ${landmarks.length} landmarks`);
      }
      
    } catch (error) {
      logger.error(`Error handling pose data: ${error.message}`);
    }
  }

  async sendSessionData(sessionData) {
    await this.outputClient.sendMessage(sessionData);
    logger.debug('Sent session data');
  }

  async run() {
    if (!await this.setup()) {
      logger.error('Setup failed, exiting');
      return;
    }
    
    logger.info('Starting WebSocket pose session tracker...');
    this.running = true;
    this.startTime = Date.now();
    
    try {
      // Start WebSocket clients
      const inputTask = this.inputClient.start();
      const outputTask = this.outputClient.start();
      
      // Wait for tasks to complete (they should run indefinitely)
      await Promise.all([inputTask, outputTask]);
      
    } catch (error) {
      logger.error(`Error in main loop: ${error.message}`);
    } finally {
      await this.cleanup();
    }
  }

  async cleanup() {
    logger.info('Cleaning up...');
    this.running = false;
    
    if (this.inputClient) {
      this.inputClient.stop();
    }
    
    if (this.outputClient) {
      this.outputClient.stop();
    }
    
    // Log final statistics
    const elapsed = (Date.now() - this.startTime) / 1000;
    logger.info(`Processed ${this.messageCount} messages in ${elapsed.toFixed(2)} seconds`);
    if (elapsed > 0) {
      logger.info(`Average rate: ${(this.messageCount / elapsed).toFixed(2)} messages/second`);
    }
    
    logger.info('Cleanup complete');
  }
}

// Main execution
async function main() {
  try {
    // Parse route data if provided
    let routeData = null;
    if (options.routeData) {
      try {
        // First try to parse as JSON string
        try {
          routeData = JSON.parse(options.routeData);
          logger.info(`Loaded route data from JSON string: ${JSON.stringify(routeData)}`);
        } catch (stringParseError) {
          // If string parsing fails, try to read as file path
          try {
            const routeFileContent = fs.readFileSync(options.routeData, 'utf8');
            routeData = JSON.parse(routeFileContent);
            logger.info(`Loaded route data from file: ${options.routeData}`);
          } catch (fileError) {
            throw new Error(`Failed to parse route data as JSON string or read from file: ${stringParseError.message} | ${fileError.message}`);
          }
        }
      } catch (error) {
        logger.error(`Invalid route data: ${error.message}`);
        process.exit(1);
      }
    }
    
    // Create and run session tracker
    const tracker = new WebSocketPoseSessionTracker(
      options.svg,
      options.calibration,
      options.inputWebsocketUrl,
      options.outputWebsocketUrl,
      parseFloat(options.proximityThreshold),
      parseFloat(options.touchDuration),
      parseFloat(options.reconnectDelay),
      options.debug,
      options.noStreamLandmarks,
      options.streamSvgOnly,
      routeData
    );
    
    // Handle graceful shutdown
    process.on('SIGINT', () => {
      logger.info('Interrupted by user');
      if (tracker.sessionTracker) {
        tracker.sessionTracker.endSession();
      }
      tracker.cleanup().then(() => {
        process.exit(0);
      });
    });
    
    // Run tracker
    await tracker.run();
    
  } catch (error) {
    logger.error(`Fatal error: ${error.message}`);
    process.exit(1);
  }
}

// Run main function
if (require.main === module) {
  main();
}

module.exports = {
  WebSocketPoseSessionTracker,
  SVGParser,
  SVGHoldDetector,
  SessionTracker,
  applyHomographyToMediaPipeJSON,
  calculateExtendedHandLandmarks
};