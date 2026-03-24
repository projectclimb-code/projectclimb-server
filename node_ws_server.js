const WebSocket = require('ws');
const http = require('http');
const https = require('https');
const url = require('url');
const fs = require('fs');

// Simple arg parser
const args = process.argv.slice(2);
let PORT = process.env.PORT ? parseInt(process.env.PORT) : 8080;
let SSL_PORT = process.env.SSL_PORT ? parseInt(process.env.SSL_PORT) : 8443;
let SSL_KEY = process.env.SSL_KEY;
let SSL_CERT = process.env.SSL_CERT;

// If first arg is a number, treat as port (backward compatibility)
if (args[0] && !isNaN(parseInt(args[0]))) {
  PORT = parseInt(args[0]);
}

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--port' && args[i+1]) PORT = parseInt(args[i+1]);
  if (args[i] === '--ssl-port' && args[i+1]) SSL_PORT = parseInt(args[i+1]);
  if (args[i] === '--key' && args[i+1]) SSL_KEY = args[i+1];
  if (args[i] === '--cert' && args[i+1]) SSL_CERT = args[i+1];
}

const wss = new WebSocket.Server({ noServer: true });

const httpServer = http.createServer();
httpServer.on('upgrade', (request, socket, head) => {
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});

httpServer.listen(PORT, () => {
  console.log(`WS server started on port ${PORT}`);
});

let httpsServer = null;
if (SSL_KEY && SSL_CERT) {
  try {
    const key = fs.readFileSync(SSL_KEY);
    const cert = fs.readFileSync(SSL_CERT);
    httpsServer = https.createServer({ key, cert });
    
    httpsServer.on('upgrade', (request, socket, head) => {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    });

    httpsServer.listen(SSL_PORT, () => {
      console.log(`WSS server started on port ${SSL_PORT}`);
    });
  } catch (err) {
    console.error('Failed to load SSL certificates or start WSS server:', err.message);
  }
}

// Store rooms and their clients
const rooms = new Map();

wss.on('connection', (ws, req) => {
  // Parse room name from URL path
  const pathname = url.parse(req.url).pathname;
  const match = pathname.match(/^\/(channel|ws)\/(.+)$/);
  
  if (!match) {
    ws.close(1008, 'Invalid URL format. Use: /channel/room_name or /ws/room_name');
    return;
  }

  const roomName = decodeURIComponent(match[2]);

  // Create room if it doesn't exist
  if (!rooms.has(roomName)) {
    rooms.set(roomName, new Set());
  }

  // Add client to room
  rooms.get(roomName).add(ws);
  console.log(`Client joined room: ${roomName} (${rooms.get(roomName).size} users)`);

  ws.on('message', (data) => {
    // Convert to string if binary
    const message = data instanceof Buffer ? data.toString('utf8') : data;
    
    // Broadcast message to all other clients in the same room
    const room = rooms.get(roomName);
    if (room) {
      room.forEach((client) => {
        if (client !== ws && client.readyState === WebSocket.OPEN) {
          client.send(message);
        }
      });
    }
  });

  ws.on('close', () => {
    const room = rooms.get(roomName);
    if (room) {
      room.delete(ws);

      // Delete empty rooms
      if (room.size === 0) {
        rooms.delete(roomName);
        console.log(`Room ${roomName} deleted (empty)`);
      } else {
        console.log(`Client left room: ${roomName} (${room.size} users)`);
      }
    }
  });
});

console.log(`
Server ready! Connect with:
ws://localhost:${PORT}/channel/room_name
or
ws://localhost:${PORT}/ws/room_name

Optional: If WSS is configured:
wss://localhost:${SSL_PORT}/channel/room_name
or
wss://localhost:${SSL_PORT}/ws/room_name

All messages are broadcasted to other clients in the same channel.
`);