import pytest
import json
import base64
from app.services.kms_service import KMSService
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class TestKMSService:
    @pytest.fixture
    def kms(self):
        return KMSService()

    def test_derive_kek_success(self, kms):
        password = "test_password"
        salt = b"test_salt_16_byte"
        
        kek1 = kms.derive_kek(password, salt)
        kek2 = kms.derive_kek(password, salt)
        
        assert len(kek1) == 32
        assert kek1 == kek2  # Deterministic check

    def test_encrypt_decrypt_payload_success(self, kms):
        secret = "test_secret_key_32_bytes_exactly"
        data = {"message": "hello world", "id": 123}
        
        encrypted = kms.encrypt_payload(data, secret)
        assert isinstance(encrypted, str)
        
        decrypted = kms.decrypt_payload(encrypted, secret)
        assert decrypted == data

    def test_decrypt_payload_failure(self, kms):
        secret = "test_secret_key_32_bytes_exactly"
        bad_hex = "00" * 20  # Invalid ciphertext
        
        with pytest.raises(Exception):
            kms.decrypt_payload(bad_hex, secret)

    def test_decrypt_private_key_success(self, kms, mocker):
        password = "my_password"
        salt = b"salt123456789012"
        iv = b"iv1234567890"
        plaintext_key = "-----BEGIN PRIVATE KEY-----\n..."
        
        # Manually encrypt to test decryption
        kek = kms.derive_kek(password, salt)
        aesgcm = AESGCM(kek)
        ciphertext = aesgcm.encrypt(iv, plaintext_key.encode(), None)
        
        # Prepare inputs in b64
        encrypted_b64 = base64.b64encode(ciphertext).decode()
        salt_b64 = base64.b64encode(salt).decode()
        iv_b64 = base64.b64encode(iv).decode()
        
        result = kms.decrypt_private_key(encrypted_b64, password, salt_b64, iv_b64)
        assert result == plaintext_key

    def test_decrypt_private_key_failure(self, kms):
        with pytest.raises(Exception, match="Invalid password or corrupted key data"):
            kms.decrypt_private_key("bad_data", "wrong_pass", "bad_salt", "bad_iv")

    def test_decrypt_medical_record_failure_missing_components(self, kms):
        # Missing 'epk', 'iv', etc.
        bad_blob = json.dumps({"ct": "some_data"})
        private_key_pem = "fake_pem"
        
        result = kms.decrypt_medical_record(bad_blob, private_key_pem)
        assert "Error decrypting" in result
