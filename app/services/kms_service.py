import json
import base64
import os
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ec
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

class KMSService:
    @staticmethod
    def derive_kek(password: str, salt: bytes) -> bytes:
        """
        Derive Key Encryption Key using PBKDF2-SHA256.
        Synced with Node.js: 310,000 iterations.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=310000,
        )
        return kdf.derive(password.encode())

    @staticmethod
    def encrypt_payload(data: dict, secret: str) -> str:
        """Encrypt JSON payload using internal App Secret (AES-GCM)."""
        aesgcm = AESGCM(secret.encode().ljust(32)[:32])
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

    @staticmethod
    def decrypt_private_key(encrypted_priv_key_b64: str, password: str, salt_b64: str, iv_b64: str) -> str:
        """
        Decrypt the user's private key using their password.
        Uses PBKDF2-SHA256 for KEK derivation and AES-256-GCM for decryption.
        """
        try:
            salt = base64.b64decode(salt_b64)
            iv = base64.b64decode(iv_b64)
            data = base64.b64decode(encrypted_priv_key_b64)
            
            # Derive KEK (PBKDF2 310k iter)
            kek = KMSService.derive_kek(password, salt)
            
            # Decrypt (AES-GCM)
            aesgcm = AESGCM(kek)
            # data is ciphertext + tag
            plaintext = aesgcm.decrypt(iv, data, None)
            
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt private key: {str(e)}")
            raise Exception("Invalid password or corrupted key data")

    @staticmethod
    def decrypt_medical_record(encrypted_blob: str, private_key_pem: str) -> str:
        """
        Decrypt medical record notes using P-256 ECIES.
        Logic: ECDH -> SHA256 KDF -> AES-256-GCM Decrypt
        """
        try:
            data = json.loads(encrypted_blob)
            epk_b64 = data.get("epk")
            iv_b64 = data.get("iv")
            ct_b64 = data.get("ct")
            tag_b64 = data.get("tag")

            if not all([epk_b64, iv_b64, ct_b64, tag_b64]):
                raise ValueError("Missing ECIES components in blob")

            # 1. Load Keys
            # Load User's Private Key (P-256)
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            
            # Load Ephemeral Public Key (SPKI format expected)
            ephemeral_public_bytes = base64.b64decode(epk_b64)
            ephemeral_public_key = serialization.load_der_public_key(ephemeral_public_bytes)

            # 2. ECDH Shared Secret
            shared_secret = private_key.exchange(ec.ECDH(), ephemeral_public_key)

            # 3. KDF (Simple SHA256 of shared secret per Node.js spec)
            digest = hashes.Hash(hashes.SHA256())
            digest.update(shared_secret)
            aes_key = digest.finalize()

            # 4. Decrypt (AES-256-GCM)
            iv = base64.b64decode(iv_b64)
            ct = base64.b64decode(ct_b64)
            tag = base64.b64decode(tag_b64)
            
            aesgcm = AESGCM(aes_key)
            # AESGCM.decrypt expects ciphertext + tag as the data parameter
            plaintext = aesgcm.decrypt(iv, ct + tag, None)
            
            return plaintext.decode()
            
        except Exception as e:
            logger.error(f"Error decrypting medical record: {str(e)}")
            return f"Error decrypting: {str(e)}"

# Singleton
kms_service = KMSService()
