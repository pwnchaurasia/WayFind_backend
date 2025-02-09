# services/redis_connection_manager.py
import json
import redis
from fastapi import WebSocket
from typing import Dict, List

from utils.redis_helper import RedisInstance


class RedisConnectionManager:
    def __init__(self):
        self.redis_client = RedisInstance()
        self.pubsub = self.redis_client.pubsub()

    async def connect(self, websocket: WebSocket, group_id: str, user_id: str):
        await websocket.accept()
        # Store the connection in Redis
        self.redis_client.hset(f"user:{user_id}", "websocket", str(websocket))
        self.redis_client.sadd(f"group:{group_id}:users", user_id)

    def disconnect(self, user_id: str, group_id: str):
        # Remove the connection from Redis
        self.redis_client.hdel(f"user:{user_id}", "websocket")
        self.redis_client.srem(f"group:{group_id}:users", user_id)

    async def broadcast(self, message: str, group_id: str):
        # Get all users in the group
        user_ids = self.redis_client.smembers(f"group:{group_id}:users")
        for user_id in user_ids:
            user_id = user_id.decode()
            websocket_str = self.redis_client.hget(f"user:{user_id}", "websocket")
            if websocket_str:
                # Send the message to the WebSocket (you'll need to implement this)
                pass

    async def listen_for_messages(self):
        # Subscribe to a Redis channel for broadcast messages
        self.pubsub.subscribe("broadcast")
        for message in self.pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.broadcast(data["message"], data["group_id"])

# Create a global instance of the Redis connection manager
redis_manager = RedisConnectionManager()