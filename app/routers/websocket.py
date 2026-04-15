from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.services.kms_service import kms_service
from app.services.redis_service import redis_service
from app.services.supabase_service import supabase_service
from app.models.schemas import ChatRequest, ChatChunk
from app.core.redis_pool import redis_pool_manager
import uuid
import json
import base64
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
    
    # --- SESSION INITIALIZATION ---
    queue = asyncio.Queue()
    websocket.app.state.active_queues[session_id] = queue
    
    await websocket.send_text(json.dumps({"type": "session_init", "session_id": session_id}))

    # Get Global Redis Pool for ARQ
    try:
        redis_pool = redis_pool_manager.get_pool()
    except Exception as e:
        logger.error(f"Failed to get Global Redis Pool: {e}")
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
                if settings.MOCK_AUTH:
                    user_id = "mock_user_123"
                    logger.info(f"Using MOCK_AUTH for user: {user_id}")
                else:
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

            # B. Key Management (Derived Key Lazy Init)
            derived_key_data = await redis_service.get_derived_key(session_id)
            if not derived_key_data and password:
                try:
                    dk, salt = kms_service.generate_derived_key(password)
                    dk_b64 = base64.b64encode(dk).decode()
                    await redis_service.set_derived_key(session_id, dk_b64, salt)
                    logger.info(f"Derived key initialized for session: {session_id}")
                except Exception as e:
                    logger.error(f"Failed to generate derived key: {e}")

            if not prompt:
                continue

            # C. Secure Task Enqueueing
            task_payload = {
                "session_id": session_id,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "prompt": prompt,
                "password": password, # Raw password for identity KEK derivation
                "accessToken": data.get("accessToken")
            }
            encrypted_payload = kms_service.encrypt_payload(task_payload, settings.APP_SECRET)
            
            # D. ENQUEUE & LISTEN VIA SHARED QUEUE
            # Enqueue Background Task (ARQ)
            await redis_pool.enqueue_job("process_medical_rag", encrypted_payload)
            await websocket.send_text(json.dumps({"type": "status", "msg": "Menghubungi AI...", "cid": correlation_id}))

            # E. SEQUENTIAL LISTENING FROM QUEUE
            while True:
                message_data = await queue.get()
                try:
                    chunk_data = json.loads(message_data)
                    if chunk_data['correlation_id'] == correlation_id:
                        msg_type = chunk_data.get("type", "chunk")
                        
                        if msg_type == "password_required":
                            metadata = json.loads(chunk_data["chunk"])
                            await websocket.send_text(json.dumps({
                                "type": "password_required",
                                **metadata
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "chunk", 
                                "chunk": chunk_data['chunk'],
                                "is_final": chunk_data['is_final']
                            }))

                        if chunk_data['is_final']:
                            break
                except Exception as e:
                    logger.error(f"Error parsing queue message: {e}")
                    continue

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        # Cleanup session queue to prevent memory leaks
        if session_id in websocket.app.state.active_queues:
            del websocket.app.state.active_queues[session_id]
        
        # Cleanup derived key and vector cache
        await redis_service.delete_derived_key(session_id)
        await supabase_service.delete_session_vectors(session_id)

        # Cleanup Chat History
        from app.services.chat_history_service import chat_history_service
        await chat_history_service.clear_history(session_id)
