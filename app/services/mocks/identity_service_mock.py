import asyncio
from typing import Dict
import logging

logger = logging.getLogger("uvicorn.error")

class MockIdentityService:
    async def get_user_crypto_data(self, access_token: str) -> Dict:
        """Simulasikan fetching data crypto tetap."""
        await asyncio.sleep(0.1)
        # Data dummy ini valid secara struktur untuk didekripsi oleh kms_service (dengan password tes)
        return {
            "user_id": "test_user_load",
            "encrypted_priv_key": "MOCK_ENCRYPTED_KEY_HEX",
            "key_derivation_salt": "MOCK_SALT_HEX",
            "key_iv": "MOCK_IV_HEX"
        }
