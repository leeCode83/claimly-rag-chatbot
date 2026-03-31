from google import genai
from google.genai import types
from app.core.config import settings
from typing import AsyncGenerator, List, Dict
from app.services.kms_service import kms_service
from app.services.supabase_service import supabase_service

class AIService:
    def __init__(self):
        # Initialize Google Gen AI Client (Unified SDK 2026)
        # Auth uses GEMINI_API_KEY from settings
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Menggunakan model gemini-2.0-flash (Stable 2026) 
        # Menghindari error 404 pada model 1.5-flash yang sudah deprecated di SDK ini
        self.model_name = 'gemini-2.5-flash' 
        self.embed_model = "text-embedding-004"

    async def get_embedding(self, text: str) -> List[float]:
        """Generate 768-dimension vector menggunakan text-embedding-004 (Latest)."""
        async with self.client.aio as async_client:
            response = await async_client.models.embed_content(
                model=self.embed_model,
                contents=text,
                config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
            )
            return response.embeddings[0].values

    async def stream_rag_answer(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate RAG-enabled answer dengan streaming menggunakan Gemini 2.0."""
        full_message = f"""
        Kamu adalah chatbot medis asisten Dr. Kalbe. 
        Gunakan data rekam medis berikut sebagai konteks pencarian untuk menjawab pertanyaan user. 
        Jika jawaban tidak ada dalam konteks, jawab bahwa data tidak ditemukan.
        
        Konteks Medis:
        {context}
        
        Pertanyaan User:
        {prompt}
        """
        
        async with self.client.aio as async_client:
            # Menggunakan await pada pemanggilan stream lalu iterasi asinkron
            async for chunk in await async_client.models.generate_content_stream(
                model=self.model_name,
                contents=full_message
            ):
                if chunk.text:
                    yield chunk.text

    async def process_selective_rag(self, user_id: str, prompt: str, session_id: str, correlation_id: str) -> AsyncGenerator[str, None]:
        """
        Main Pipeline: Two-Phase Semantic RAG for Medical Records.
        """
        # Hubungkan di sini untuk menghindari Circular Import
        from app.services.medical_record_service import medical_record_service
        
        # Phase 1: Fetch and Rank Metadata (Fast & Low Cost)
        all_records = await medical_record_service.fetch_patient_records(user_id)
        relevant_records = await medical_record_service.rank_relevant_records(prompt, all_records, limit=5)
        
        if not relevant_records:
            async for chunk in self.stream_rag_answer(prompt, "Sistem tidak menemukan rekam medis yang relevan."):
                yield chunk
            return

        # Phase 2: Targeted Decryption & Context Preparation
        decrypted_contexts = []
        for record in relevant_records:
            # 1. Decrypt (Mocked in KMS for now)
            # In real case, we'd fetch encrypted private key from Identity API first
            plaintext = kms_service.decrypt_medical_record(record.notes_encrypted, "PRIVATE_KEY_MOCK")
            
            # 2. Vector Caching Check (Sticky Vectors)
            # Check if this record is already embedded to avoid duplicate costs
            # We skip matching here because we already have the relevant record IDs
            # but we want to PERSIST the vector if it doesn't exist.
            
            # 3. Embedding Generation (if needed)
            # In a production app, we would cache this in Supabase
            embedding = await self.get_embedding(plaintext)
            await supabase_service.insert_vector(
                user_id=user_id,
                session_id=session_id,
                correlation_id=correlation_id,
                content=plaintext,
                embedding=embedding
            )
            
            decrypted_contexts.append(f"Diagnosa: {record.diagnosis.description} ({record.diagnosis_date})\nCatatan: {plaintext}")

        # Final RAG with collected context
        combined_context = "\n\n".join(decrypted_contexts)
        async for chunk in self.stream_rag_answer(prompt, combined_context):
            yield chunk

# Singleton
ai_service = AIService()
