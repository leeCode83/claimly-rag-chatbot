from typing import List
import logging
import time
from app.models.schemas import MedicalRecord
from app.services.ai_service import ai_service
from app.core.config import settings
from app.core.http import get_http_client
from google.genai import types
import json

logger = logging.getLogger("uvicorn.error")

class MedicalRecordService:
    async def fetch_patient_records(self, user_id: str, access_token: str) -> List[MedicalRecord]:
        """
        Fetch patient records from Medical API using user's bearer token.
        """
        if not access_token:
            logger.warning("Access token missing.")
            raise Exception("Maaf, sesi Anda tidak valid atau token hilang. Silakan login kembali.")

        t0 = time.perf_counter()
        logger.info(f"[RAG:MEDICAL-API] Calling {settings.MEDICAL_API_URL} for user {user_id}")

        try:
            client = get_http_client()
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(
                settings.MEDICAL_API_URL, 
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                # Parse 'data' array from the response
                records_raw = data.get("data", [])
                records = [MedicalRecord(**r) for r in records_raw]
                elapsed = (time.perf_counter() - t0) * 1000
                logger.info(f"[RAG:MEDICAL-API] Received {len(records)} records in {elapsed:.0f}ms")
                return records
            else:
                elapsed = (time.perf_counter() - t0) * 1000
                logger.error(f"[RAG:MEDICAL-API] Error {response.status_code} after {elapsed:.0f}ms: {response.text}")
                raise Exception("Maaf, kami tidak dapat mengakses data medis Anda saat ini. Pastikan akun Anda sudah terdaftar dengan benar.")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error(f"[RAG:MEDICAL-API] Connection failed after {elapsed:.0f}ms: {str(e)}")
            raise Exception("Server medis sedang sibuk atau tidak merespons. Mohon coba lagi beberapa saat lagi.")

    async def rank_relevant_records(self, prompt: str, records: List[MedicalRecord], limit: int = 5) -> List[MedicalRecord]:
        """
        Phase 1: Rank records based on unencrypted metadata using Gemini.
        Returns top-k records that match the user's intent.
        """
        if not records:
            return []

        logger.info(f"[RAG:RANKING] Ranking {len(records)} records for prompt relevance")
        t0 = time.perf_counter()

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
        
        ATURAN PENTING:
        1. Jika pertanyaan user bersifat umum (Halo, Apa kabar, Siapa kamu) atau tidak terkait dengan data kesehatan personal, kembalikan LIST KOSONG `[]`.
        2. Hanya pilih ID jika pertanyaan membutuhkan data medis (misal: "Apa diagnosa saya?", "Hasil lab?").
        
        Instruksi format output:
        Hanya kembalikan list ID dalam format JSON (misal: ["id1", "id2"] atau []). Jangan berikan penjelasan apapun.
        """

        try:
            # Menggunakan Gemini untuk memilih ID
            client = ai_service.get_client()
            async with client.aio as async_client:
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
            result = [r for r in records if str(r.id) in relevant_ids][:limit]
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(f"[RAG:RANKING] Selected {len(result)} relevant records in {elapsed:.0f}ms")
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error(f"[RAG:RANKING] Ranking failed after {elapsed:.0f}ms: {e}")
            # Fallback: Kembalikan beberapa yang terbaru jika LLM gagal
            return sorted(records, key=lambda x: x.diagnosis_date, reverse=True)[:limit]

# Singleton
medical_record_service = MedicalRecordService()
