import asyncio
import random
import json
from typing import AsyncGenerator, List, Dict
import logging

logger = logging.getLogger("uvicorn.error")

class MockAIService:
    def __init__(self):
        self.model_name = 'mock-gemini'
        self.embed_model = "mock-embedding"

    async def get_embedding(self, text: str) -> List[float]:
        """Simulasikan embedding dengan random vector 768 dimensi."""
        await asyncio.sleep(0.1) # Simulasi latensi rendah
        return [random.uniform(-1, 1) for _ in range(768)]

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Simulasikan batch embedding."""
        await asyncio.sleep(0.2)
        return [[random.uniform(-1, 1) for _ in range(768)] for _ in texts]

    async def detect_medical_intent(self, prompt: str) -> str:
        """Simulasikan deteksi intent."""
        await asyncio.sleep(0.1)
        return 'medical'

    async def stream_rag_answer(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Simulasikan streaming jawaban AI dengan delay per chunk."""
        responses = [
            "Halo! Saya Dr. Claimly AI (MOCK). ",
            "Berdasarkan analisis data medis Anda yang disimulasikan, ",
            "kondisi kesehatan Anda terlihat stabil dalam pengujian beban ini. ",
            "\n\nCatatan: Ini adalah respon tiruan untuk keperluan load testing 100 concurrent users. ",
            "Sistem infrastruktur (Redis, Worker, WebSocket) sedang diuji kekuatannya. ",
            "\n\nSemoga hari Anda menyenangkan!"
        ]
        
        for chunk in responses:
            await asyncio.sleep(0.4) # Simulasi kecepatan LLM mengetik
            yield chunk

    async def process_selective_rag(self, user_id: str, prompt: str, session_id: str, correlation_id: str, password: str, access_token: str) -> AsyncGenerator[Dict, None]:
        """Simulasikan seluruh pipeline RAG."""
        # 1. Simulate Intent Detection
        await asyncio.sleep(0.1)
        
        # 2. Simulate Metadata Fetching & Ranking
        await asyncio.sleep(0.2)
        
        # 3. Simulate RAG Streaming
        async for chunk in self.stream_rag_answer(prompt, "Mock Context"):
            yield {"type": "chunk", "content": chunk}
