from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.http import AsyncHttpClient
from app.core.redis_pool import redis_pool_manager
from app.services.redis_service import redis_service
import sys
import asyncio
import json

# Winloop: Ultra-fast event loop for Windows (IOCP-based)
if sys.platform == "win32":
    import winloop
    winloop.install()

async def shared_pubsub_listener(app: FastAPI):
    """Background task to listen to all chat chunks and dispatch to user queues."""
    pubsub = redis_service.redis_client.pubsub()
    try:
        await pubsub.psubscribe("chat:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                try:
                    session_id = channel.split(":")[1]
                    if session_id in app.state.active_queues:
                        await app.state.active_queues[session_id].put(message["data"])
                except IndexError:
                    continue
    except Exception as e:
        print(f"PubSub Listener Error: {e}")
    finally:
        await pubsub.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize shared resources
    print(f"Starting {settings.APP_NAME}...")
    app.state.active_queues = {} # Global registry for session queues
    
    await redis_pool_manager.connect()
    
    # Start Shared PubSub Listener
    listener_task = asyncio.create_task(shared_pubsub_listener(app))
    
    yield
    # Shutdown: Clean up resources
    print(f"Shutting down {settings.APP_NAME}...")
    listener_task.cancel()
    await AsyncHttpClient.close_client()
    await redis_pool_manager.disconnect()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    debug=settings.DEBUG
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Chatbot Error", "detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
    )

# Healthcheck endpoint for Docker
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Import and include routers
from app.routers import websocket
app.include_router(websocket.router)
