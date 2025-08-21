from channels.generic.websocket import AsyncWebsocketConsumer
import json

class PoseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'pose_stream'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print("WebSocket connection established.")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket connection closed: {close_code}")

    # Receive message from WebSocket (from the streamer)
    async def receive(self, text_data):
        # Broadcast the received data to the web client group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'pose_message',
                'message': text_data
            }
        )

    # Receive message from room group (to send to the web client)
    async def pose_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=message)