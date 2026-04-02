from typing import Optional
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from app.core.config import settings
import logging

logger = logging.getLogger("uvicorn.error")

class RedisPool:
    def __init__(self):
        self.pool: Optional[ArqRedis] = None

    async def connect(self):
        """Initialize global ARQ pool once."""
        if not self.pool:
            try:
                self.pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                logger.info("Global Redis ARQ Pool initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Global Redis Pool: {e}")
                raise

    async def disconnect(self):
        """Close global pool on shutdown."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Global Redis ARQ Pool closed.")

    def get_pool(self) -> ArqRedis:
        """Get the active pool instance."""
        if not self.pool:
            raise RuntimeError("RedisPool is not connected. Call connect() first.")
        return self.pool

# Singleton instance
redis_pool_manager = RedisPool()
