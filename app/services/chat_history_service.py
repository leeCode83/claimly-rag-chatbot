import json
import logging
from typing import List, Dict
from app.services.redis_service import redis_service

logger = logging.getLogger("uvicorn.error")

class ChatHistoryService:
    def __init__(self, max_history: int = 20, ttl: int = 7200):
        """
        Service to manage chat history in Redis.
        max_history: Max number of messages (default 20 = 10 pairs).
        ttl: Time to live in seconds (default 2 hours).
        """
        self.max_history = max_history
        self.ttl = ttl
        self.redis = redis_service.redis_client

    def _get_key(self, session_id: str) -> str:
        return f"chat_history:{session_id}"

    async def add_message(self, session_id: str, role: str, text: str):
        """
        Adds a message to the chat history and trims to max_history.
        role: 'user' or 'model'
        """
        if not text:
            return

        key = self._get_key(session_id)
        message = {
            "role": role,
            "parts": [{"text": text}]
        }
        
        try:
            # RPUSH adds to the end of the list
            await self.redis.rpush(key, json.dumps(message))
            # LTRIM keeps the last max_history elements
            await self.redis.ltrim(key, -self.max_history, -1)
            # Refresh TTL
            await self.redis.expire(key, self.ttl)
        except Exception as e:
            logger.error(f"Failed to add message to history: {e}")

    async def get_history(self, session_id: str) -> List[Dict]:
        """
        Retrieves the chat history for a session.
        Returns a list of messages formatted for Gemini API.
        """
        key = self._get_key(session_id)
        try:
            history_raw = await self.redis.lrange(key, 0, -1)
            return [json.loads(msg) for msg in history_raw]
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def clear_history(self, session_id: str):
        """Removes the chat history for a session."""
        key = self._get_key(session_id)
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

# Singleton
chat_history_service = ChatHistoryService()
