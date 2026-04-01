from google import genai
from google.genai import types
from app.core.config import settings
from typing import AsyncGenerator, List, Dict
import logging
import json
from app.services.kms_service import kms_service
from app.services.supabase_service import supabase_service

logger = logging.getLogger("uvicorn.error")

class AIService:
    def __init__(self):
        # Menggunakan model gemini-1.5-flash-latest untuk kompatibilitas lebih baik
        self.model_name = 'gemini-2.5-flash' 
        self.embed_model = "gemini-embedding-001"

    def get_client(self):
        """Creates a fresh Gemini client for each operation to avoid connection closure issues."""
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def get_embedding(self, text: str) -> List[float]:
        """Generate 768-dimension vector menggunakan gemini-embedding-001."""
        client = self.get_client()
        async with client.aio as async_client:
            response = await async_client.models.embed_content(
                model=self.embed_model,
                contents=text,
                config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
            )
            return response.embeddings[0].values

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate multiple 768-dimension vectors in a single request."""
        if not texts:
            return []
            
        client = self.get_client()
        async with client.aio as async_client:
            response = await async_client.models.embed_content(
                model=self.embed_model,
                contents=texts,
                config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
            )
            return [emb.values for emb in response.embeddings]

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
        
        # Menggunakan await pada pemanggilan stream lalu iterasi asinkron
        client = self.get_client()
        async with client.aio as async_client:
            async for chunk in await async_client.models.generate_content_stream(
                model=self.model_name,
                contents=full_message
            ):
                if chunk.text:
                    yield chunk.text

    async def process_selective_rag(self, user_id: str, prompt: str, session_id: str, correlation_id: str, password: str, access_token: str) -> AsyncGenerator[str, None]:
        """
        Main Pipeline: Two-Phase Semantic RAG for Medical Records.
        Now uses Batch Embedding for efficiency.
        """
        from app.services.medical_record_service import medical_record_service
        from app.services.identity_service import identity_service
        
        # 0. Fetch and Decrypt User Private Key
        private_key = None
        if password and password.strip():
            try:
                crypto_data = await identity_service.get_user_crypto_data(access_token)
                private_key = kms_service.decrypt_private_key(
                    crypto_data["encrypted_priv_key"], 
                    password,
                    crypto_data["key_derivation_salt"],
                    crypto_data["key_iv"]
                )
            except Exception as e:
                yield json.dumps({"type": "chunk", "chunk": f"Otentikasi kunci gagal: {str(e)}", "is_final": False})
                return

        # Phase 1: Fetch and Rank Metadata (Fast & Low Cost)
        all_records = await medical_record_service.fetch_patient_records(user_id, access_token)
        relevant_records = await medical_record_service.rank_relevant_records(prompt, all_records, limit=5)
        
        if not relevant_records:
            async for chunk in self.stream_rag_answer(prompt, "Sistem tidak menemukan rekam medis yang relevan."):
                yield chunk
            return

        # Phase 2: Targeted Decryption & Context Preparation (Batch Optimized)
        records_to_embed = []
        record_contents = {} # map record_id -> content (plaintext)
        
        # 1. First pass: Identify what's missing from cache
        for record in relevant_records:
            record_id_str = str(record.id)
            cached = await supabase_service.get_vector_by_record_id(user_id, record_id_str)
            
            if cached:
                record_contents[record_id_str] = cached["content"]
            elif private_key:
                try:
                    plaintext = kms_service.decrypt_medical_record(record.notes_encrypted, private_key)
                    record_contents[record_id_str] = plaintext
                    records_to_embed.append({"id": record_id_str, "content": plaintext})
                except Exception as e:
                    logger.error(f"Failed to decrypt record {record_id_str}: {e}")
                    record_contents[record_id_str] = "[Gagal mendekripsi catatan]"
            else:
                record_contents[record_id_str] = "[Catatan detail terenkripsi - Masukkan password untuk mengakses]"

        # 2. Second pass: Generate embeddings in batch if needed
        if records_to_embed:
            texts = [r["content"] for r in records_to_embed]
            try:
                embeddings = await self.get_embeddings_batch(texts)
                
                # Prepare data for bulk insert
                vectors_to_insert = []
                for i, record_info in enumerate(records_to_embed):
                    vectors_to_insert.append({
                        "user_id": user_id,
                        "session_id": session_id,
                        "correlation_id": correlation_id,
                        "content": record_info["content"],
                        "embedding": embeddings[i],
                        "record_id": record_info["id"]
                    })
                
                await supabase_service.insert_vectors_batch(vectors_to_insert)
                logger.info(f"Batched embedding and insertion for {len(records_to_embed)} records.")
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")

        # 3. Third pass: Construct final context
        decrypted_contexts = []
        for record in relevant_records:
            record_id_str = str(record.id)
            plaintext = record_contents.get(record_id_str, "[Data tidak tersedia]")
            decrypted_contexts.append(f"Diagnosa: {record.diagnosis.description} ({record.diagnosis_date})\nCatatan: {plaintext}")

        # Final RAG with collected context
        combined_context = "\n\n".join(decrypted_contexts)
        async for chunk in self.stream_rag_answer(prompt, combined_context):
            yield chunk

# Singleton
ai_service = AIService()
