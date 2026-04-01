from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.http import AsyncHttpClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize shared resources
    print(f"Starting {settings.APP_NAME}...")
    yield
    # Shutdown: Clean up resources
    print(f"Shutting down {settings.APP_NAME}...")
    await AsyncHttpClient.close_client()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    debug=settings.DEBUG
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

# Import and include routers
from app.routers import websocket
app.include_router(websocket.router)
