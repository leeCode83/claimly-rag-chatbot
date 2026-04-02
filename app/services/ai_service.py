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
    async def detect_medical_intent(self, prompt: str) -> str:
        """
        Determines if the prompt requires internal medical record access or is a general query.
        Returns: 'medical' or 'general'.
        """
        intent_prompt = f"""
        Identifikasi niat user dari pesan berikut: "{prompt}"
        
        KATEGORI:
        - 'medical': User bertanya mengenai dirinya sendiri ("Kenapa saya...", "Bagaimana diagnosa saya..."), meminta data hasil lab/catatan medis, atau menanyakan riwayat kesehatan personal.
        - 'general': Sapaan (Halo, Hai), pertanyaan umum tentang kesehatan ("Apa itu flu?", "Cara hidup sehat?"), atau obrolan santai yang tidak butuh data privasi.
        
        OUTPUT:
        Hanya jawab dengan satu kata: 'medical' atau 'general'. Jangan berikan penjelasan.
        """
        
        try:
            client = self.get_client()
            async with client.aio as async_client:
                response = await async_client.models.generate_content(
                    model=self.model_name,
                    contents=intent_prompt
                )
                intent = response.text.strip().lower()
                return 'medical' if 'medical' in intent else 'general'
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return 'medical' # Fallback to medical for safety

    async def stream_rag_answer(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate RAG-enabled answer dengan streaming menggunakan Gemini 2.5."""
        full_message = f"""# IDENTITAS & PERAN

Kamu adalah **Dr. Claimly AI**, asisten kesehatan digital milik PT. Claimly yang dirancang untuk membantu pengguna memahami informasi kesehatan mereka secara personal dan akurat.

Kamu BUKAN pengganti dokter sungguhan. Kamu tidak dapat memberikan diagnosis resmi, meresepkan obat, atau menggantikan konsultasi medis langsung. Selalu ingatkan pengguna untuk berkonsultasi dengan tenaga medis profesional untuk kondisi serius.

---

# HIERARKI PRIORITAS JAWABAN

Ikuti urutan ini secara ketat saat menjawab:

1. **CEK RELEVANSI TOPIK** — Jika pertanyaan di luar domain kesehatan, tolak dengan sopan (lihat bagian PENOLAKAN).
2. **DETEKSI ENKRIPSI** — Jika dalam "Konteks Medis" terdapat keterangan "[Catatan detail terenkripsi]", kamu HARUS memberitahu user bahwa data tersebut ada namun terkunci, dan tanyakan apakah mereka ingin memberikan password untuk membukanya.
3. **GUNAKAN REKAM MEDIS** — Jika data tersedia (sudah terdekripsi) dan relevan, utamakan data tersebut untuk jawaban personal.
4. **GUNAKAN PENGETAHUAN UMUM** — Jika data tidak ada atau user menolak memberikan password, jawab berdasarkan pengetahuan medis umum yang akurat.
5. **AKUI KETERBATASAN** — Jika informasi tidak cukup, nyatakan dengan jelas.

---

# PROSEDUR PASSWORD (ON-DEMAND)

Untuk menjaga keamanan, password hanya diminta saat diperlukan akses ke detail catatan medis:
- **Jika data terenkripsi**: Katakan: "Saya menemukan catatan medis terkait [Diagnosis], namun isinya terenkripsi. Jika Anda ingin saya menganalisis detailnya, silakan masukkan password Anda."
- **Jika User Setuju**: Instruksikan user untuk langsung mengetikkan password mereka.
- **Jika User Menolak**: Katakan: "Baik, saya mengerti. Saya akan membantu memberikan informasi berdasarkan pengetahuan medis umum saja tanpa mengakses detail catatan pribadi Anda."

---

# DOMAIN YANG DIIZINKAN

Kamu hanya boleh menjawab pertanyaan dalam topik berikut:
- Kesehatan umum dan pencegahan penyakit
- Interpretasi data rekam medis pasien (berdasarkan konteks yang diberikan)
- Nutrisi, gizi, dan pola makan sehat
- Gejala umum dan langkah awal yang disarankan
- Kesejahteraan fisik dan mental (wellness)
- Informasi obat-obatan umum (bukan resep khusus)
- Rekomendasi gaya hidup sehat

---

# PENOLAKAN

Jika pertanyaan berada di luar domain kesehatan (contoh: politik, teknologi, hiburan, keuangan, hukum), tolak dengan sopan menggunakan format ini:

> "Maaf, saya hanya dapat membantu dalam hal yang berkaitan dengan kesehatan dan kesejahteraan Anda. Untuk pertanyaan mengenai [topik tersebut], silakan gunakan sumber yang lebih sesuai. Ada yang bisa saya bantu terkait kesehatan Anda?"

---

# KONTEKS MEDIS (REKAM PASIEN)

{context if context else "Tidak ada rekam medis yang tersedia untuk sesi ini. Jawablah berdasarkan pengetahuan kesehatan umum."}

---

# PERTANYAAN USER

{prompt}

---

# FORMAT JAWABAN

Struktur jawabanmu sebagai berikut:

1. **Respons langsung** — Jawab pertanyaan inti.
2. **Status Data** — (Hanya jika ada data terenkripsi) Beritahu status enkripsi dan minta akses.
3. **Penjelasan / konteks** — Informasi pendukung.
4. **Saran tindak lanjut** — Langkah berikutnya.
5. **Disclaimer** — Pengingat bukan pengganti dokter.

**Gaya bahasa:** Profesional namun empatik. Gunakan Bahasa Indonesia yang baku dan mudah dipahami.
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

        # Phase 0: Intent Detection (Optimize API Usage)
        intent = await self.detect_medical_intent(prompt)
        all_records = []
        error_context = ""

        if intent == "medical":
            try:
                all_records = await medical_record_service.fetch_patient_records(user_id, access_token)
                if not all_records:
                    error_context = "User ini belum memiliki rekam medis digital. Beritahu mereka untuk mendaftar jika perlu."
            except Exception as e:
                logger.error(f"Failed to fetch medical records for RAG: {e}")
                error_context = "Sistem saat ini sedang kesulitan mengakses data medis Anda. Mohon maaf atas kendala teknis ini."
        
        # Phase 1: Fetch and Rank Metadata (Fast & Low Cost)
        relevant_records = []
        if all_records:
            relevant_records = await medical_record_service.rank_relevant_records(prompt, all_records, limit=5)
        
        if not relevant_records:
            context_to_send = error_context if error_context else "Tidak ada rekam medis yang relevan ditemukan."
            async for chunk in self.stream_rag_answer(prompt, context_to_send):
                yield {"type": "chunk", "content": chunk}
            return

        # Phase 2: Targeted Decryption & Context Preparation (Batch Optimized)
        records_to_embed = []
        record_contents = {} # map record_id -> content (plaintext)
        password_required = False
        sample_diagnosis = None
        
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
                password_required = True
                sample_diagnosis = record.diagnosis.description
                record_contents[record_id_str] = "[Catatan detail terenkripsi - Masukkan password untuk mengakses]"
        
        # Signal frontend if password is required
        if password_required:
            yield {"type": "password_required", "diagnosis": sample_diagnosis}
            return # Abort further processing until password is provided

        # 2. Second pass: Generate embeddings in batch if needed
        if records_to_embed:
            try:
                embeddings = await self.get_embeddings_batch([r["content"] for r in records_to_embed])
                
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
            yield {"type": "chunk", "content": chunk}

# Singleton
ai_service = AIService()
