from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime
from typing import List, Optional

# --- External API Mock Models ---

class DiagnosisInfo(BaseModel):
    icd10_code: str
    description: str

class PatientInfo(BaseModel):
    id: UUID
    full_name: str

class DoctorInfo(BaseModel):
    id: UUID
    role: str
    full_name: str

class MedicalRecord(BaseModel):
    id: UUID
    patient_id: UUID
    hospital_institution_id: UUID
    diagnosis_id: UUID
    diagnosis_date: date
    diagnosis_date_encoded: int
    attending_doctor_id: UUID
    notes_encrypted: Optional[str] = None
    diagnosis: DiagnosisInfo
    patient: PatientInfo
    attending_doctor: DoctorInfo
    created_at: datetime

class UserKeys(BaseModel):
    user_id: UUID
    encrypted_private_key: str
    salt: str

# --- Chat Models ---

class ChatRequest(BaseModel):
    prompt: str
    password: str

class ChatChunk(BaseModel):
    """Payload for streaming chunks over WebSocket."""
    session_id: str
    correlation_id: str
    chunk: str
    is_final: bool = False

# --- Internal Task Payload ---

class TaskPayload(BaseModel):
    session_id: str
    correlation_id: str
    user_id: str
    prompt: str
    kek: str  # Encrypted using APP_SECRET in KMSService before enqueue
