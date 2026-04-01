import httpx
from typing import Optional

class AsyncHttpClient:
    client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Returns the global singleton client."""
        if cls.client is None:
            # Initialize with default settings
            cls.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        return cls.client

    @classmethod
    async def close_client(cls):
        """Closes the singleton client."""
        if cls.client:
            await cls.client.aclose()
            cls.client = None

# Helper accessor
def get_http_client() -> httpx.AsyncClient:
    return AsyncHttpClient.get_client()
