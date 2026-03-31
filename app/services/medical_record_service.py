from typing import List
import httpx
from app.models.schemas import MedicalRecord
from app.utils.mocks import api_mock
from app.services.ai_service import ai_service
from app.core.config import settings
from google.genai import types
import json

class MedicalRecordService:
    async def fetch_patient_records(self, user_id: str) -> List[MedicalRecord]:
        """
        Fetch patient records from Medical API.
        Falls back to Mock if token is missing or request fails.
        """
        # Gunakan Mock jika token belum diset di .env
        if not settings.MEDICAL_API_TOKEN or settings.MEDICAL_API_TOKEN == "your_bearer_token_here":
            print("MEDICAL_API_TOKEN not set, falling back to Mock Data.")
            return await api_mock.get_medical_records(user_id)

        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {settings.MEDICAL_API_TOKEN}"}
                response = await client.get(
                    settings.MEDICAL_API_URL, 
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Parse 'data' array from the response
                    records_raw = data.get("data", [])
                    return [MedicalRecord(**r) for r in records_raw]
                else:
                    print(f"API Error {response.status_code}: {response.text}")
                    return await api_mock.get_medical_records(user_id)
        except Exception as e:
            print(f"Connection failed: {str(e)}. Falling back to Mock.")
            return await api_mock.get_medical_records(user_id)

    async def rank_relevant_records(self, prompt: str, records: List[MedicalRecord], limit: int = 5) -> List[MedicalRecord]:
        """
        Phase 1: Rank records based on unencrypted metadata using Gemini.
        Returns top-k records that match the user's intent.
        """
        if not records:
            return []

        # Prepare metadata representation for LLM
        metadata_summary = []
        for r in records:
            metadata_summary.append({
                "id": str(r.id),
                "diagnosis": r.diagnosis.description,
                "icd10": r.diagnosis.icd10_code,
                "date": str(r.diagnosis_date)
            })

        selector_prompt = f"""
        Tugas: Analisis daftar rekam medis berikut dan pilih maksimal {limit} ID yang paling relevan dengan pertanyaan user.
        
        Pertanyaan User: "{prompt}"
        
        Daftar Rekam Medis (Metadata):
        {json.dumps(metadata_summary, indent=2)}
        
        Instruksi format output:
        Hanya kembalikan list ID dalam format JSON (misal: ["id1", "id2"]). Jangan berikan penjelasan apapun.
        """

        try:
            # Menggunakan Gemini untuk memilih ID
            async with ai_service.client.aio as async_client:
                response = await async_client.models.generate_content(
                    model=ai_service.model_name,
                    contents=selector_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                # Parse output JSON
                relevant_ids = json.loads(response.text)
                if not isinstance(relevant_ids, list):
                    relevant_ids = [relevant_ids]
                
                # Filter records based on selected IDs
                return [r for r in records if str(r.id) in relevant_ids][:limit]
        except Exception as e:
            print(f"Error in ranking records: {e}")
            # Fallback: Kembalikan beberapa yang terbaru jika LLM gagal
            return sorted(records, key=lambda x: x.diagnosis_date, reverse=True)[:limit]

# Singleton
medical_record_service = MedicalRecordService()
