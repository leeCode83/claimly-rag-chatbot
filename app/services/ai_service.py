from google import genai
from google.genai import types
from app.core.config import settings
from typing import AsyncGenerator, List, Dict

class AIService:
    def __init__(self):
        # Initialize Google Gen AI Client (Unified SDK 2026)
        # Auth uses GEMINI_API_KEY from settings
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Menggunakan model gemini-2.0-flash (Stable 2026) 
        # Menghindari error 404 pada model 1.5-flash yang sudah deprecated di SDK ini
        self.model_name = 'gemini-2.5-flash' 
        self.embed_model = "text-embedding-004"

    async def get_embedding(self, text: str) -> List[float]:
        """Generate 768-dimension vector menggunakan text-embedding-004 (Latest)."""
        async with self.client.aio as async_client:
            response = await async_client.models.embed_content(
                model=self.embed_model,
                contents=text,
                config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
            )
            return response.embeddings[0].values

    async def stream_rag_answer(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate RAG-enabled answer dengan streaming menggunakan Gemini 2.0."""
        full_message = f"""
        Kamu adalah chatbot medis asisten Dr. Kalbe. 
        Gunakan data rekam medis berikut sebagai konteks pencarian untuk menjawab pertanyaan user. 
        Jika jawaban tidak ada dalam konteks, jawab bahwa data tidak ditemukan.
        
        Konteks Medis:
        {context}
        
        Pertanyaan User:
        {prompt}
        """
        
        async with self.client.aio as async_client:
            # Menggunakan await pada pemanggilan stream lalu iterasi asinkron
            async for chunk in await async_client.models.generate_content_stream(
                model=self.model_name,
                contents=full_message
            ):
                if chunk.text:
                    yield chunk.text

# Singleton
ai_service = AIService()
