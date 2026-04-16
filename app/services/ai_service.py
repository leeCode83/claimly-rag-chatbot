from google import genai
from google.genai import types
from app.core.config import settings
from typing import AsyncGenerator, List, Dict
import logging
import json
import base64
import time
import asyncio
from app.services.kms_service import kms_service
from app.services.supabase_service import supabase_service

logger = logging.getLogger("uvicorn.error")

class AIService:
    def __init__(self):
        # Model utama untuk ranking records dan generasi jawaban RAG
        self.model_name = 'gemini-2.5-flash'
        # Model ringan untuk intent detection (15 RPM, 500 RPD) — hemat kuota
        self.intent_model = "gemini-2.5-flash-lite"
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
                config=types.EmbedContentConfig(
                    task_type='RETRIEVAL_QUERY',
                    output_dimensionality=768
                )
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
                config=types.EmbedContentConfig(
                    task_type='RETRIEVAL_DOCUMENT',
                    output_dimensionality=768
                )
            )
            return [emb.values for emb in response.embeddings]

    async def detect_medical_intent(self, prompt: str) -> str:
        """
        Determines if the prompt requires internal medical record access or is a general query.
        Uses gemini-2.1-flash-lite (15 RPM, 500 RPD) to preserve gemini-2.5-flash quota.
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
        
        for attempt in range(3):
            try:
                client = self.get_client()
                async with client.aio as async_client:
                    response = await async_client.models.generate_content(
                        model=self.intent_model,
                        contents=intent_prompt
                    )
                    intent = response.text.strip().lower()
                    return 'medical' if 'medical' in intent else 'general'
            except Exception as e:
                logger.error(f"Intent detection failed (Attempt {attempt+1}/3): {e}")
                if "503" in str(e) or "quota" in str(e).lower():
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                break
                
        return 'medical' # Fallback to medical for safety

    async def stream_rag_answer(self, prompt: str, context: str, history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """Generate RAG-enabled answer dengan streaming menggunakan Gemini 2.5."""
        system_instruction = f"""# IDENTITAS & PERAN

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

# ATURAN PANJANG JAWABAN

Sesuaikan panjang jawabanmu dengan kompleksitas pertanyaan:
- **Pertanyaan Ya/Tidak** (contoh: "Apakah saya punya riwayat diabetes?", "Apakah flu itu menular?"): Jawab dengan **"Ya"** atau **"Tidak"**, diikuti maksimal **1 kalimat** penjelasan singkat. Jangan panjangkan.
- **Pertanyaan kompleks** (contoh: "Jelaskan hasil lab saya", "Apa yang harus saya lakukan?"): Gunakan format lengkap sesuai bagian FORMAT JAWABAN di bawah.

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
        
        # Build contents from history + current prompt
        contents = []
        if history:
            for msg in history:
                contents.append(types.Content(
                    role=msg["role"],
                    parts=[types.Part(text=msg["parts"][0]["text"])]
                ))
        
        # Add current user prompt
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        ))

        # Menggunakan await pada pemanggilan stream lalu iterasi asinkron
        client = self.get_client()
        async with client.aio as async_client:
            async for chunk in await async_client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            ):
                             yield chunk.text

    async def process_selective_rag(self, user_id: str, prompt: str, session_id: str, correlation_id: str, password: str, access_token: str, history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """
        Main Pipeline: Optimized Two-Phase semantic RAG.
        1. Intent Detection
        2. DB-First Vector Search
        3. Lazy API Fetch (once per session)
        4. Structured context generation
        """
        from app.services.medical_record_service import medical_record_service
        from app.services.identity_service import identity_service
        from app.services.redis_service import redis_service

        # PHASE 0: Intent Detection
        t_intent = time.perf_counter()
        intent = await self.detect_medical_intent(prompt)
        elapsed_intent = (time.perf_counter() - t_intent) * 1000
        logger.info(f"[RAG:INTENT] Detected intent='{intent}' in {elapsed_intent:.0f}ms")

        if intent != "medical":
            logger.info(f"[RAG:STREAM] General query — skipping medical record lookup")
            async for chunk in self.stream_rag_answer(prompt, "Sapa user dan jawab pertanyaan umum dengan ramah.", history):
                yield {"type": "chunk", "content": chunk}
            return

        # PHASE 1: DB-First Vector Search
        t_db = time.perf_counter()
        query_embedding = await self.get_embedding(prompt)
        db_matches = await supabase_service.match_records(user_id, query_embedding, threshold=0.7)
        elapsed_db = (time.perf_counter() - t_db) * 1000
        logger.info(f"[RAG:DB-SEARCH] Found {len(db_matches)} potential matches in Supabase ({elapsed_db:.0f}ms)")

        # PHASE 2: Lazy API Fetch (If DB results are empty or low similarity)
        is_api_fetched = await redis_service.is_api_fetched(session_id)
        
        if not db_matches and not is_api_fetched:
            logger.info(f"[RAG:LAZY-FETCH] No relevant data in DB and API not fetched yet. Calling Medical API...")
            try:
                fetched_records = await medical_record_service.fetch_patient_records(user_id, access_token)
                await redis_service.set_api_fetched(session_id)

                if fetched_records:
                    # If we have password, we can decrypt and embed immediately to populate DB
                    if password:
                        # 2.1 Get Private Key
                        crypto_data = await identity_service.get_user_crypto_data(access_token)
                        private_key = kms_service.decrypt_private_key(
                            crypto_data["encrypted_priv_key"], password,
                            crypto_data["key_derivation_salt"], crypto_data["key_iv"]
                        )
                        
                        # 2.2 Get/Generate Derived Key for DB encryption
                        dk_data = await redis_service.get_derived_key(session_id)
                        if dk_data:
                            dk = base64.b64decode(dk_data["key"])
                        else:
                            dk, salt_str = kms_service.generate_derived_key(password)
                            await redis_service.set_derived_key(session_id, base64.b64encode(dk).decode(), salt_str)

                        # 2.3 Decrypt, Embed and Save all fetched records
                        records_to_insert = []
                        relevant_fetched = await medical_record_service.rank_relevant_records(prompt, fetched_records)
                        
                        if relevant_fetched:
                            texts_to_embed = []
                            for r in relevant_fetched:
                                plaintext = kms_service.decrypt_medical_record(r.notes_encrypted, private_key)
                                texts_to_embed.append(plaintext)
                            
                            embeddings = await self.get_embeddings_batch(texts_to_embed)
                            for i, r in enumerate(relevant_fetched):
                                encrypted_val = kms_service.encrypt_content(texts_to_embed[i], dk)
                                records_to_insert.append({
                                    "user_id": user_id, "session_id": session_id, "correlation_id": correlation_id,
                                    "content": encrypted_val, "embedding": embeddings[i], "record_id": str(r.id)
                                })
                            
                            await supabase_service.insert_vectors_batch(records_to_insert)
                            # Re-run DB search to pick up new vectors
                            db_matches = await supabase_service.match_records(user_id, query_embedding, threshold=0.7)
                    else:
                        sample_diag = fetched_records[0].diagnosis.description if fetched_records else "Data Medis"
                        yield {"type": "password_required", "diagnosis": sample_diag}
                        return
            except Exception as e:
                logger.error(f"[RAG:LAZY-FETCH] Failed: {e}")

        # PHASE 3: Decryption & Context Preparation
        if not db_matches:
            msg = "Maaf, saya tidak menemukan informasi medis yang relevan dengan pertanyaan Anda."
            async for chunk in self.stream_rag_answer(prompt, msg, history):
                yield {"type": "chunk", "content": chunk}
            return

        dk_data = await redis_service.get_derived_key(session_id)
        if not dk_data:
            yield {"type": "password_required", "diagnosis": "Detail Rekam Medis"}
            return
            
        dk = base64.b64decode(dk_data["key"])
        decrypted_contexts = []
        for match in db_matches:
            try:
                plaintext = kms_service.decrypt_content(match["content"], dk)
                decrypted_contexts.append(f"Informasi Terkait: {plaintext}")
            except Exception as e:
                logger.error(f"[RAG:DECRYPT] Failed to decrypt match: {e}")
                continue

        if not decrypted_contexts:
            async for chunk in self.stream_rag_answer(prompt, "Data medis ditemukan namun tidak dapat dibuka. Silakan masukkan password kembali.", history):
                yield {"type": "chunk", "content": chunk}
            return

        final_context = "\n\n".join(decrypted_contexts)
        logger.info(f"[RAG:STREAM] Generating final answer with {len(decrypted_contexts)} record(s)")
        async for chunk in self.stream_rag_answer(prompt, final_context, history):
            yield {"type": "chunk", "content": chunk}

# Singleton Instance Factory
if settings.MOCK_AI:
    from app.services.mocks.ai_service_mock import MockAIService
    ai_service = MockAIService()
    print("WARNING: AIService is running in MOCK mode.")
else:
    ai_service = AIService()
