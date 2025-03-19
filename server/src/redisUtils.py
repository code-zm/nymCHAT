# server/src/redisUtils.py - FIXED VERSION
import os
import json
import asyncio
from redis.asyncio import Redis
from logConfig import logger
from envLoader import load_env

load_env()

class RedisManager:
    """Handles Redis connections and operations for the server."""
    
    def __init__(self, redis_url=None):
        """Initialize the Redis manager with connection parameters."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = None
        self.pubsub = None
        self.connection_status = "disconnected"
        
    async def connect(self):
        """Establish connection to Redis server."""
        try:
            self.redis = Redis.from_url(
                self.redis_url,
                decode_responses=True  # Automatically decode Redis responses to strings
            )
            # Test connection
            await self.redis.ping()
            
            self.pubsub = self.redis.pubsub()
            self.connection_status = "connected"
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connection_status = "failed"
            return False
    
    async def publish(self, channel, message):
        """Publish a message to a specified channel."""
        if not self.redis or self.connection_status != "connected":
            logger.warning("Cannot publish: Redis not connected")
            return False
            
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self.redis.publish(channel, message)
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    async def subscribe(self, channel, callback):
        """Subscribe to a channel and set up message handling."""
        if not self.redis or self.connection_status != "connected":
            logger.warning("Cannot subscribe: Redis not connected")
            return False
            
        try:
            await self.pubsub.subscribe(channel)
            # Start the message listener
            asyncio.create_task(self._message_listener(callback))
            logger.info(f"Subscribed to channel: {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to channel {channel}: {e}")
            return False
    
    async def _message_listener(self, callback):
        """Background task that listens for messages on subscribed channels."""
        try:
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]
                    
                    # Try to parse as JSON if it's a string
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            pass  # Keep as string if not valid JSON
                    
                    # Pass to callback
                    await callback(channel, data)
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
    
    async def set_presence(self, username, status="online", expiry=300):
        """Set user presence with automatic expiry."""
        if not self.redis:
            logger.warning("Cannot set presence: Redis not connected")
            return False
            
        try:
            key = f"presence:{username}"
            if status == "online":
                await self.redis.setex(key, expiry, "online")
            else:
                await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to set presence for {username}: {e}")
            return False
    
    async def get_presence(self, username):
        """Check if a user is online."""
        if not self.redis:
            return False
            
        try:
            status = await self.redis.get(f"presence:{username}")
            return status == "online"
        except Exception as e:
            logger.error(f"Failed to get presence for {username}: {e}")
            return False
    
    async def get_all_online_users(self):
        """Get a list of all online users."""
        if not self.redis:
            return []
            
        try:
            keys = await self.redis.keys("presence:*")
            online_users = [key.split(":", 1)[1] for key in keys]
            return online_users
        except Exception as e:
            logger.error(f"Failed to get online users: {e}")
            return []
    
    async def close(self):
        """Close the Redis connection."""
        if self.pubsub:
            await self.pubsub.unsubscribe()
        if self.redis:
            await self.redis.close()
            self.connection_status = "disconnected"
            logger.info("Redis connection closed")


