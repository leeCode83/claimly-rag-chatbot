from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.services.kms_service import kms_service
from app.services.redis_service import redis_service
from app.services.supabase_service import supabase_service
from app.models.schemas import ChatRequest, ChatChunk
from arq import create_pool
from arq.connections import RedisSettings
import uuid
import json
import asyncio
import logging

# Setup standard logging
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # 1. Server-side Session Init
    session_id = str(uuid.uuid4())
    user_id = None # To be populated after auth
    
    await websocket.send_text(json.dumps({"type": "session_init", "session_id": session_id}))

    # Setup Redis Pool for ARQ
    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    except Exception as e:
        logger.error(f"Failed to create Redis Pool: {e}")
        await websocket.close(code=1011)
        return

    try:
        while True:
            # A. Receive User Input
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            prompt = data.get("prompt")
            password = data.get("password")
            accessToken = data.get("accessToken")
            correlation_id = str(uuid.uuid4())

            # 1. Dynamic Auth (Supabase Local/Auth Provider)
            if not user_id:
                try:
                    from app.core.supabase import supabase_auth
                    auth_response = supabase_auth.auth.get_user(accessToken)
                    user_id = auth_response.user.id
                    logger.info(f"User authenticated (Local Auth): {user_id}")
                except Exception as e:
                    logger.error(f"Auth failed: {e}")
                    await websocket.send_text(json.dumps({"type": "error", "msg": "Sesi tidak valid atau token kadaluarsa."}))
                    await websocket.close(code=1008)
                    return

            # B. Key Management (KMS Hybrid)
            kek = await redis_service.get_kek(session_id)
            if not kek:
                salt = b"DUMMY_SALT_16_BYTES" 
                kek_bytes = kms_service.derive_kek(password, salt)
                kek = kek_bytes.hex()
                await redis_service.set_kek(session_id, kek)

            # C. Secure Task Enqueueing
            task_payload = {
                "session_id": session_id,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "prompt": prompt,
                "kek": kek, # Legacy/Session KEK
                "password": password, # Raw password for identity KEK derivation
                "accessToken": data.get("accessToken")
            }
            encrypted_payload = kms_service.encrypt_payload(task_payload, settings.APP_SECRET)
            
            # D. Enqueue Background Task (ARQ)
            await redis_pool.enqueue_job("process_medical_rag", encrypted_payload)
            await websocket.send_text(json.dumps({"type": "status", "msg": "Menghubungi AI...", "cid": correlation_id}))

            # E. SEQUENTIAL LISTENING: One prompt at a time 
            async with redis_service.redis_client.pubsub() as pubsub:
                await pubsub.subscribe(f"chat:{session_id}")
                
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            chunk_data = json.loads(message["data"])
                            if chunk_data['correlation_id'] == correlation_id:
                                await websocket.send_text(json.dumps({
                                    "type": "chunk", 
                                    "chunk": chunk_data['chunk'],
                                    "is_final": chunk_data['is_final']
                                }))
                                if chunk_data['is_final']:
                                    break
                        except Exception as e:
                            logger.error(f"Error parsing chunk: {e}")
                            continue
                
                await pubsub.unsubscribe(f"chat:{session_id}")

    except WebSocketDisconnect:
        await redis_service.delete_kek(session_id)
    except Exception as e:
        logger.error(f"WebSocket Error: {str(e)}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "msg": "Terjadi kesalahan internal pada server."}))
        except:
            pass
    finally:
        await redis_pool.close()
