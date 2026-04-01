from app.core.config import settings
import logging
from app.core.http import get_http_client

logger = logging.getLogger("uvicorn.error")

class IdentityService:
    async def get_user_crypto_data(self, access_token: str) -> dict:
        """
        Fetch user's encrypted private key, salt, and IV from Identity API.
        """
        url = f"{settings.IDENTITY_API_URL}/api/users/me/crypto-data"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            client = get_http_client()
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", {})
                logger.info(f"DEBUG IDENTITY DATA: {data}")
                return data
            else:
                logger.error(f"Identity API Error {response.status_code}: {response.text}")
                raise Exception(f"Failed to fetch crypto data: {response.text}")
        except Exception as e:
            logger.error(f"Connection to Identity API failed: {str(e)}")
            raise

# Singleton
identity_service = IdentityService()
