
# client/src/redisUtils.py - FIXED VERSION
import os
import json
import asyncio
from redis.asyncio import Redis
from logUtils import logger

class RedisClient:
    """Client-side Redis integration for real-time notifications."""
    
    def __init__(self, redis_url=None):
        """Initialize the Redis client with connection parameters."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = None
        self.pubsub = None
        self.connection_status = "disconnected"
        self.notification_callback = None
        self.presence_callback = None
        self._listener_task = None
        
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
    
    async def subscribe_to_notifications(self, username, callback):
        """Subscribe to personal notifications for the given username."""
        if not self.redis or self.connection_status != "connected":
            logger.warning("Cannot subscribe: Redis not connected")
            return False
            
        try:
            self.notification_callback = callback
            channel = f"notifications:{username}"
            await self.pubsub.subscribe(channel)
            logger.info(f"Subscribed to notifications channel: {channel}")
            
            # Also subscribe to presence updates
            await self.pubsub.subscribe("presence_updates")
            logger.info("Subscribed to presence updates channel")
            
            # Start listener if not already running
            if not self._listener_task or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._message_listener())
                
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to notifications: {e}")
            return False
    
    async def set_presence_callback(self, callback):
        """Set a callback for presence updates."""
        self.presence_callback = callback
        
    async def update_presence(self, username, status="online"):
        """Update user presence status."""
        if not self.redis or self.connection_status != "connected":
            logger.warning("Cannot update presence: Redis not connected")
            return False
            
        try:
            if status == "online":
                await self.redis.setex(f"presence:{username}", 300, "online")
            else:
                await self.redis.delete(f"presence:{username}")
            return True
        except Exception as e:
            logger.error(f"Failed to update presence: {e}")
            return False
    
    async def get_online_users(self):
        """Get a list of all online users."""
        if not self.redis or self.connection_status != "connected":
            return []
            
        try:
            keys = await self.redis.keys("presence:*")
            online_users = [key.split(":", 1)[1] for key in keys]
            return online_users
        except Exception as e:
            logger.error(f"Failed to get online users: {e}")
            return []
    
    async def is_user_online(self, username):
        """Check if a specific user is online."""
        if not self.redis or self.connection_status != "connected":
            return False
            
        try:
            status = await self.redis.get(f"presence:{username}")
            return status == "online"
        except Exception as e:
            logger.error(f"Failed to check if user is online: {e}")
            return False
    
    async def _message_listener(self):
        """Background task that listens for messages on subscribed channels."""
        try:
            logger.info("Redis message listener started")
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
                    
                    # Handle based on channel type
                    if channel == "presence_updates" and self.presence_callback:
                        await self.presence_callback(data)
                    elif channel.startswith("notifications:") and self.notification_callback:
                        await self.notification_callback(data)
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            # Attempt to restart the listener if it fails
            await asyncio.sleep(5)
            if self.connection_status == "connected":
                self._listener_task = asyncio.create_task(self._message_listener())
    
    async def heartbeat(self, username):
        """Send periodic heartbeat to keep presence alive."""
        if not self.redis or self.connection_status != "connected":
            return
            
        try:
            # Refresh presence with 5-minute expiry
            await self.redis.setex(f"presence:{username}", 300, "online")
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    async def close(self):
        """Close the Redis connection."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
                
        if self.pubsub:
            await self.pubsub.unsubscribe()
        if self.redis:
            await self.redis.close()
            self.connection_status = "disconnected"
            logger.info("Redis connection closed")
