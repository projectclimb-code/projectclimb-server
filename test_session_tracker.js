#!/usr/bin/env node

/**
 * Test script for the WebSocket pose session tracker
 * 
 * This script demonstrates how to use the JavaScript WebSocket pose session tracker
 * with sample data and command line arguments.
 */

const WebSocket = require('ws');
const { program } = require('commander');

// Configure command line options
program
  .option('--svg <path>', 'Path to SVG file containing climbing wall holds', './code/data/wall.svg')
  .option('--calibration <path>', 'Path to calibration JSON file', './sample_calibration.json')
  .option('--input-port <number>', 'Port for input WebSocket server', '8080')
  .option('--output-port <number>', 'Port for output WebSocket server', '8081')
  .option('--test-data <path>', 'Path to test pose data JSON file', './in.json')
  .option('--route-data <path>', 'Route data as JSON string or path to JSON file with holds specification')
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
 * Simple WebSocket server to simulate pose data input
 */
class PoseDataServer {
  constructor(port, testDataPath) {
    this.port = port;
    this.testDataPath = testDataPath;
    this.wss = null;
    this.testData = null;
    this.currentIndex = 0;
    this.interval = null;
  }

  async start() {
    try {
      // Load test data
      const fs = require('fs');
      const testDataContent = fs.readFileSync(this.testDataPath, 'utf8');
      this.testData = JSON.parse(testDataContent);
      
      if (!Array.isArray(this.testData)) {
        this.testData = [this.testData];
      }
      
      logger.info(`Loaded ${this.testData.length} test pose data entries`);
      
      // Create WebSocket server
      this.wss = new WebSocket.Server({ port: this.port });
      
      this.wss.on('connection', (ws) => {
        logger.info(`Client connected to input WebSocket server on port ${this.port}`);
        
        // Start sending test data
        this.startSendingTestData(ws);
        
        ws.on('close', () => {
          logger.info('Client disconnected from input WebSocket server');
          this.stopSendingTestData();
        });
        
        ws.on('error', (error) => {
          logger.error(`WebSocket error: ${error.message}`);
        });
      });
      
      logger.info(`Input WebSocket server started on port ${this.port}`);
      
    } catch (error) {
      logger.error(`Error starting pose data server: ${error.message}`);
      throw error;
    }
  }

  startSendingTestData(ws) {
    this.currentIndex = 0;
    
    this.interval = setInterval(() => {
      if (this.currentIndex >= this.testData.length) {
        this.currentIndex = 0; // Loop back to start
      }
      
      const poseData = this.testData[this.currentIndex];
      
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(poseData));
        logger.debug(`Sent pose data ${this.currentIndex + 1}/${this.testData.length}`);
      }
      
      this.currentIndex++;
    }, 100); // Send data every 100ms
  }

  stopSendingTestData() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  stop() {
    this.stopSendingTestData();
    if (this.wss) {
      this.wss.close();
    }
  }
}

/**
 * Simple WebSocket server to capture session data output
 */
class SessionDataServer {
  constructor(port) {
    this.port = port;
    this.wss = null;
    this.receivedData = [];
  }

  async start() {
    this.wss = new WebSocket.Server({ port: this.port });
    
    this.wss.on('connection', (ws) => {
      logger.info(`Client connected to output WebSocket server on port ${this.port}`);
      
      ws.on('message', (data) => {
        try {
          const sessionData = JSON.parse(data.toString());
          this.receivedData.push(sessionData);
          
          logger.info(`Received session data: ${JSON.stringify({
            timestamp: sessionData.session?.startTime,
            holdsCount: sessionData.session?.holds?.length || 0,
            poseLandmarks: sessionData.pose?.length || 0,
            status: sessionData.session?.status
          })}`);
          
          // Log hold status changes
          if (sessionData.session?.holds) {
            const touchedHolds = sessionData.session.holds.filter(hold => hold.status === 'touched');
            if (touchedHolds.length > 0) {
              logger.info(`Touched holds: ${touchedHolds.map(hold => hold.id).join(', ')}`);
            }
          }
          
        } catch (error) {
          logger.error(`Error parsing session data: ${error.message}`);
        }
      });
      
      ws.on('close', () => {
        logger.info('Client disconnected from output WebSocket server');
      });
      
      ws.on('error', (error) => {
        logger.error(`WebSocket error: ${error.message}`);
      });
    });
    
    logger.info(`Output WebSocket server started on port ${this.port}`);
  }

  getReceivedData() {
    return this.receivedData;
  }

  stop() {
    if (this.wss) {
      this.wss.close();
    }
  }
}

/**
 * Main test function
 */
async function runTest() {
  logger.info('Starting WebSocket pose session tracker test...');
  
  const poseDataServer = new PoseDataServer(parseInt(options.inputPort), options.testData);
  const sessionDataServer = new SessionDataServer(parseInt(options.outputPort));
  
  try {
    // Start servers
    await poseDataServer.start();
    await sessionDataServer.start();
    
    // Wait a moment for servers to start
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Build command line arguments for the session tracker
    const args = [
      'node', 'websocket_pose_session_tracker.js',
      '--svg', options.svg,
      '--input-websocket-url', `ws://localhost:${options.inputPort}`,
      '--output-websocket-url', `ws://localhost:${options.outputPort}`
    ];
    
    if (options.calibration) {
      args.push('--calibration', options.calibration);
    }
    
    if (options.routeData) {
      args.push('--route-data', options.routeData);
    }
    
    if (options.debug) {
      args.push('--debug');
    }
    
    logger.info(`Starting session tracker with command: ${args.join(' ')}`);
    
    // Start the session tracker as a child process
    const { spawn } = require('child_process');
    const sessionTrackerProcess = spawn('node', ['websocket_pose_session_tracker.js', ...args.slice(2)], {
      stdio: 'inherit'
    });
    
    // Let it run for a while to collect data
    logger.info('Running test for 30 seconds...');
    await new Promise(resolve => setTimeout(resolve, 30000));
    
    // Stop the session tracker
    logger.info('Stopping session tracker...');
    sessionTrackerProcess.kill('SIGINT');
    
    // Wait for graceful shutdown
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Print summary
    const receivedData = sessionDataServer.getReceivedData();
    logger.info(`Test completed. Received ${receivedData.length} session data messages.`);
    
    if (receivedData.length > 0) {
      const lastData = receivedData[receivedData.length - 1];
      const totalHolds = lastData.session?.holds?.length || 0;
      const touchedHolds = lastData.session?.holds?.filter(hold => hold.status === 'touched').length || 0;
      
      logger.info(`Summary:`);
      logger.info(`  Total holds: ${totalHolds}`);
      logger.info(`  Touched holds: ${touchedHolds}`);
      logger.info(`  Session status: ${lastData.session?.status || 'unknown'}`);
      
      if (touchedHolds > 0) {
        const touchedHoldIds = lastData.session.holds
          .filter(hold => hold.status === 'touched')
          .map(hold => hold.id);
        logger.info(`  Touched hold IDs: ${touchedHoldIds.join(', ')}`);
      }
    }
    
  } catch (error) {
    logger.error(`Test failed: ${error.message}`);
  } finally {
    // Cleanup
    poseDataServer.stop();
    sessionDataServer.stop();
    logger.info('Test cleanup completed');
  }
}

// Run the test
if (require.main === module) {
  runTest().catch(error => {
    logger.error(`Fatal error: ${error.message}`);
    process.exit(1);
  });
}

module.exports = {
  PoseDataServer,
  SessionDataServer
};