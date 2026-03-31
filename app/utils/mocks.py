import uuid
from datetime import datetime, date
from app.models.schemas import MedicalRecord, UserKeys

class APIMock:
    """Mock Service for Identity and Medical Record APIs."""
    
    @staticmethod
    async def get_user_keys(user_id: str) -> UserKeys:
        # Dummy encrypted key and salt (Simulasi Argon2id)
        # In a real app, this would be fetched from the Identity API
        return UserKeys(
            user_id=uuid.UUID(user_id),
            encrypted_private_key="ENC_PRIV_KEY_DUMMY_BASE64",
            salt="SALT_DUMMY_HEX"
        )

    @staticmethod
    async def get_medical_records(user_id: str) -> list[MedicalRecord]:
        # Dummy medical record exactly as requested by user
        return [
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=uuid.UUID(user_id),
                hospital_institution_id=uuid.uuid4(),
                diagnosis_id=uuid.uuid4(),
                diagnosis_date=date(2024, 3, 20),
                diagnosis_date_encoded=12345,
                attending_doctor_id=uuid.uuid4(),
                notes_encrypted="AES-GCM-CIPHER-DUMMY-RECORDS", # Notes are encrypted
                created_at=datetime.now()
            )
        ]

api_mock = APIMock()
