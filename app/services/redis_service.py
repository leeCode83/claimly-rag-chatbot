import redis.asyncio as redis
from app.core.config import settings

class RedisService:
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def set_kek(self, session_id: str, kek: str, ttl: int = 3600):
        """Cache KEK in Redis for the duration of the session."""
        await self.redis_client.set(f"kek:{session_id}", kek, ex=ttl)

    async def get_kek(self, session_id: str) -> str:
        """Retrieve KEK from Redis."""
        return await self.redis_client.get(f"kek:{session_id}")

    async def delete_kek(self, session_id: str):
        """Force delete KEK on disconnect."""
        await self.redis_client.delete(f"kek:{session_id}")

    async def publish_chunk(self, session_id: str, correlation_id: str, chunk: str, is_final: bool = False):
        """Broadcast a streaming chunk back to the WebSocket via Pub/Sub."""
        channel = f"chat:{session_id}"
        message = {
            "correlation_id": correlation_id,
            "chunk": chunk,
            "is_final": is_final
        }
        import json
        await self.redis_client.publish(channel, json.dumps(message))

# Singleton
redis_service = RedisService()
