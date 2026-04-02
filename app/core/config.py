from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    # App General
    APP_NAME: str = "Claimly RAG Chatbot"
    DEBUG: bool = True
    APP_SECRET: str
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # API URLs
    IDENTITY_API_URL: str
    MEDICAL_API_URL: str
    
    # Supabase (Vector Store - Cloud)
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Supabase (Auth - Local)
    SUPABASE_AUTH_URL: Optional[str] = None
    SUPABASE_AUTH_KEY: Optional[str] = None
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Gemini AI
    GEMINI_API_KEY: str
    
    # Testing & Mocks
    MOCK_AI: bool = False
    MOCK_IDENTITY: bool = False
    MOCK_AUTH: bool = False
    
    # Config for .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global Settings Instance
settings = Settings()
