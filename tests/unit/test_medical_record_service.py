import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.medical_record_service import MedicalRecordService
from app.models.schemas import MedicalRecord, DiagnosisInfo, PatientInfo, DoctorInfo
from uuid import uuid4, UUID
from datetime import date, datetime
import json

class TestMedicalRecordService:
    @pytest.fixture
    def service(self):
        return MedicalRecordService()

    def create_mock_record(self, record_id=None, diagnosis_desc="Flu"):
        rid = record_id if record_id else uuid4()
        pid = uuid4()
        did = uuid4()
        doc_id = uuid4()
        return MedicalRecord(
            id=rid,
            patient_id=pid,
            hospital_institution_id=uuid4(),
            diagnosis_id=did,
            diagnosis_date=date(2023, 10, 1),
            diagnosis_date_encoded=20231001,
            attending_doctor_id=doc_id,
            notes_encrypted="abc",
            diagnosis=DiagnosisInfo(description=diagnosis_desc, icd10_code="J11"),
            patient=PatientInfo(id=pid, full_name="Test Patient"),
            attending_doctor=DoctorInfo(id=doc_id, full_name="Test Doctor", role="GP"),
            created_at=datetime.now()
        )

    @pytest.mark.asyncio
    async def test_fetch_patient_records_success(self, service, mocker):
        rid = str(uuid4())
        pid = str(uuid4())
        hid = str(uuid4())
        did = str(uuid4())
        doc_id = str(uuid4())
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": rid,
                    "patient_id": pid,
                    "hospital_institution_id": hid,
                    "diagnosis_id": did,
                    "diagnosis_date": "2023-10-01",
                    "diagnosis_date_encoded": 20231001,
                    "attending_doctor_id": doc_id,
                    "notes_encrypted": "abc",
                    "diagnosis": {"description": "Flu", "icd10_code": "J11"},
                    "patient": {"id": pid, "full_name": "Test Patient"},
                    "attending_doctor": {"id": doc_id, "full_name": "Test Doctor", "role": "GP"},
                    "created_at": datetime.now().isoformat()
                }
            ]
        }
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        
        with patch('app.services.medical_record_service.get_http_client', return_value=mock_client):
            records = await service.fetch_patient_records("user_1", "valid_token")
            
            assert len(records) == 1
            assert str(records[0].id) == rid
            assert records[0].diagnosis.description == "Flu"

    @pytest.mark.asyncio
    async def test_fetch_patient_records_no_token(self, service):
        with pytest.raises(Exception, match="sesi Anda tidak valid"):
            await service.fetch_patient_records("user_1", "")

    @pytest.mark.asyncio
    async def test_fetch_patient_records_api_error(self, service, mocker):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        
        with patch('app.services.medical_record_service.get_http_client', return_value=mock_client):
            with pytest.raises(Exception, match="Server medis sedang sibuk"):
                await service.fetch_patient_records("user_1", "token")

    @pytest.mark.asyncio
    async def test_rank_relevant_records_success(self, service, mocker):
        rec1 = self.create_mock_record(diagnosis_desc="Asthma")
        rec2 = self.create_mock_record(diagnosis_desc="Fracture")
        records = [rec1, rec2]
        
        mock_client = MagicMock()
        mock_async_client = AsyncMock()
        mock_client.aio.__aenter__.return_value = mock_async_client
        
        mock_response = MagicMock()
        mock_response.text = json.dumps([str(rec1.id)])
        mock_async_client.models.generate_content.return_value = mock_response
        
        with patch('app.services.ai_service.ai_service.get_client', return_value=mock_client):
            result = await service.rank_relevant_records("Napas saya sesak", records)
            
            assert len(result) == 1
            assert result[0].id == rec1.id

    @pytest.mark.asyncio
    async def test_rank_relevant_records_fallback(self, service, mocker):
        rec1 = self.create_mock_record(diagnosis_desc="A")
        rec2 = self.create_mock_record(diagnosis_desc="B")
        records = [rec1, rec2]
        
        with patch('app.services.ai_service.ai_service.get_client', side_effect=Exception("LLM Error")):
            result = await service.rank_relevant_records("Any prompt", records, limit=1)
            assert len(result) == 1
