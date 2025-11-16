const WebSocket = require('ws');
const http = require('http');
const url = require('url');

const PORT = 8080;
const server = http.createServer();
const wss = new WebSocket.Server({ server });

// Store rooms and their clients
const rooms = new Map();

console.log(`WebSocket server started on port ${PORT}`);

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

server.listen(PORT);

console.log(`
Server ready! Connect with:
ws://localhost:${PORT}/channel/room_name
or
ws://localhost:${PORT}/ws/room_name

All messages are broadcasted to other clients in the same channel.
`);