from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize shared resources if needed
    # Supabase is already initialized during import in core/supabase.py
    print(f"Starting {settings.APP_NAME}...")
    yield
    # Shutdown: Clean up resources
    print(f"Shutting down {settings.APP_NAME}...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    debug=settings.DEBUG
)

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "version": "1.0.0"
    }

# Import and include routers
from app.routers import websocket
app.include_router(websocket.router)
