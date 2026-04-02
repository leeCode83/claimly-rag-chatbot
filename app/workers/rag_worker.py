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
    password = payload['password']
    accessToken = payload['accessToken']

    print(f"Worker processing RAG for session {session_id}")

    try:
        # 3. Execute Two-Phase RAG Pipeline
        # Now yields dictionaries: {"type": "chunk", "content": "..."} or {"type": "password_required", ...}
        async for result in ai_service.process_selective_rag(user_id, prompt, session_id, correlation_id, password, accessToken):
            msg_type = result.get("type", "chunk")
            
            if msg_type == "chunk":
                await redis_service.publish_chunk(session_id, correlation_id, result["content"], msg_type="chunk")
            elif msg_type == "password_required":
                # For metadata types, we can pass the whole JSON-stringified dict or specific chunk
                await redis_service.publish_chunk(session_id, correlation_id, json.dumps(result), msg_type="password_required")
        
        # 4. Finalize
        await redis_service.publish_chunk(session_id, correlation_id, "", is_final=True)
        print(f"RAG Task complete for session {session_id}")

    except Exception as e:
        error_msg = str(e)
        print(f"Error in Worker: {error_msg}")
        # Jika error mengandung kata "Maaf", berarti itu error bisnis/user-friendly dari service
        # Jika tidak, berikan pesan teknis standar.
        friendly_msg = error_msg if "Maaf" in error_msg else "Terjadi kesalahan teknis pada sistem chatbot. Mohon coba lagi nanti."
        await redis_service.publish_chunk(session_id, correlation_id, friendly_msg, msg_type="error", is_final=True)

class WorkerSettings:
    """ARQ Worker Settings."""
    functions = [process_medical_rag]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 25  # Rebalanced: 4 workers x 25 jobs = 100 total capacity
