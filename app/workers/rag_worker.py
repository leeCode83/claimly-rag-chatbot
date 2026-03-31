import asyncio
import sys

# FIX: Inisialisasi Event Loop secara eksplisit untuk Python 3.14 / Windows
# Ini mencegah RuntimeError: There is no current event loop in thread 'MainThread'
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.kms_service import kms_service
from app.services.ai_service import ai_service
from app.services.supabase_service import supabase_service
from app.services.redis_service import redis_service
from app.utils.mocks import api_mock
import json

async def process_medical_rag(ctx, encrypted_payload: str):
    """
    Background Task: 
    1. Decrypt Task Payload
    2. Fetch Keys & Records (Mock)
    3. Decrypt on-the-fly
    4. RAG Pipeline (Embedding -> Vector Search -> Gemini Stream)
    5. Publish chunks to Pub/Sub
    """
    # 1. Decrypt using App Secret
    payload = kms_service.decrypt_payload(encrypted_payload, settings.APP_SECRET)
    user_id = payload['user_id']
    session_id = payload['session_id']
    correlation_id = payload['correlation_id']
    prompt = payload['prompt']
    kek = payload['kek'] # User-derived KEK

    print(f"Worker processing RAG for session {session_id}")

    try:
        # 2. Fetch Medical Records (Mock)
        records = await api_mock.get_medical_records(user_id)
        
        # 3. Perform RAG Pipeline
        context_parts = []
        for record in records:
            # Here we would normally decrypt using KEK
            plaintext_notes = "Pasien memiliki riwayat alergi parasetamol dan asma."
            context_parts.append(f"Diagnosis: {record.diagnosis_id}\nNotes: {plaintext_notes}")
        
        context = "\n---\n".join(context_parts)

        # 4. Stream RAG Answer via AI Service
        async for chunk in ai_service.stream_rag_answer(prompt, context):
            await redis_service.publish_chunk(session_id, correlation_id, chunk)
        
        # 5. Finalize
        await redis_service.publish_chunk(session_id, correlation_id, "", is_final=True)
        print(f"RAG Task complete for session {session_id}")

    except Exception as e:
        print(f"Error in Worker: {str(e)}")
        await redis_service.publish_chunk(session_id, correlation_id, f"Error: {str(e)}", is_final=True)

class WorkerSettings:
    """ARQ Worker Settings."""
    functions = [process_medical_rag]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
