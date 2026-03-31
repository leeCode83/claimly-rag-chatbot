import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
from app.core.config import settings

class KMSService:
    @staticmethod
    def derive_kek(password: str, salt: bytes) -> bytes:
        """Derive Key Encryption Key using Argon2id."""
        kdf = Argon2id(
            salt=salt,
            length=32,
            iterations=2,
            memory_cost=65536,
            lanes=4,
        )
        return kdf.derive(password.encode())

    @staticmethod
    def encrypt_payload(data: dict, secret: str) -> str:
        """Encrypt JSON payload using internal App Secret (AES-GCM)."""
        aesgcm = AESGCM(secret.encode().ljust(32)[:32]) # Ensure 32 bytes
        nonce = os.urandom(12)
        plaintext = json.dumps(data).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return (nonce + ciphertext).hex()

    @staticmethod
    def decrypt_payload(encrypted_hex: str, secret: str) -> dict:
        """Decrypt hex payload using internal App Secret (AES-GCM)."""
        data = bytes.fromhex(encrypted_hex)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(secret.encode().ljust(32)[:32])
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())

# Singleton instance
kms_service = KMSService()
