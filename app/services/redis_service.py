import redis.asyncio as redis
from app.core.config import settings

class RedisService:
    def __init__(self):
        # Increased max_connections to 200 to handle many concurrent Pub/Sub listeners during load tests
        self.redis_client = redis.from_url(
            settings.REDIS_URL, 
            decode_responses=True,
            max_connections=50, # Reduced to 50 as we now use Shared PubSub (saving connection pool)
            health_check_interval=30
        )

    async def set_kek(self, session_id: str, kek: str, ttl: int = 3600):
        """Cache KEK in Redis for the duration of the session."""
        await self.redis_client.set(f"kek:{session_id}", kek, ex=ttl)

    async def get_kek(self, session_id: str) -> str:
        """Retrieve KEK from Redis."""
        return await self.redis_client.get(f"kek:{session_id}")

    async def delete_kek(self, session_id: str):
        """Force delete KEK on disconnect."""
        await self.redis_client.delete(f"kek:{session_id}")

    async def set_derived_key(self, session_id: str, derived_key_b64: str, salt_b64: str, ttl: int = 600):
        """Cache session-scoped derived key in Redis for 10 minutes."""
        import json
        data = {"key": derived_key_b64, "salt": salt_b64}
        await self.redis_client.set(f"derived_key:{session_id}", json.dumps(data), ex=ttl)

    async def get_derived_key(self, session_id: str) -> dict:
        """Retrieve session-scoped derived key from Redis."""
        import json
        data = await self.redis_client.get(f"derived_key:{session_id}")
        return json.loads(data) if data else None

    async def delete_derived_key(self, session_id: str):
        """Force delete derived key on disconnect."""
        await self.redis_client.delete(f"derived_key:{session_id}")

    async def publish_chunk(self, session_id: str, correlation_id: str, chunk: str, msg_type: str = "chunk", is_final: bool = False):
        """Broadcast a streaming chunk back to the WebSocket via Pub/Sub."""
        channel = f"chat:{session_id}"
        message = {
            "type": msg_type,
            "correlation_id": correlation_id,
            "chunk": chunk,
            "is_final": is_final
        }
        import json
        await self.redis_client.publish(channel, json.dumps(message))

# Singleton
redis_service = RedisService()
