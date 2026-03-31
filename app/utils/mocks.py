import uuid
import json
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
                id=uuid.UUID("638fcb52-d642-4764-9fc5-f1f5130546d3"),
                patient_id=uuid.UUID(user_id),
                hospital_institution_id=uuid.UUID("21ab0492-957a-47f8-aa1e-2152a114b01c"),
                diagnosis_id=uuid.UUID("05866cdc-10fe-4f4e-8e06-ad3ef8419f75"),
                diagnosis_date=date(2026, 1, 15),
                diagnosis_date_encoded=20260115,
                attending_doctor_id=uuid.UUID("b2608734-ea72-4088-9ce4-cc9cc1b4a4c1"),
                notes_encrypted=json.dumps({
                    "epk": "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEdTDECKbNnCpx9CuSiqaGbun8SY9C1P28FnRVNEYatrqFf6rIva4DboTK9qnQpmhHWGL+8nwRRip9JfktzRmv8g==",
                    "iv": "QqZU+EftvbLiJEct",
                    "ct": "EIS3bWduitqBS0bt8msmPExoREA+zVa6zVtGttA4OQsD",
                    "tag": "Pp6FmoWZzbynTUzMDoXc1A=="
                }),
                diagnosis={
                    "icd10_code": "A00",
                    "description": "Cholera"
                },
                patient={
                    "id": uuid.UUID(user_id),
                    "full_name": "Test New Patient"
                },
                attending_doctor={
                    "id": uuid.UUID("b2608734-ea72-4088-9ce4-cc9cc1b4a4c1"),
                    "role": "hospital_staff",
                    "full_name": "Ale Santoso"
                },
                created_at=datetime.now()
            )
        ]

api_mock = APIMock()
