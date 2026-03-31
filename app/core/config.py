from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App General
    APP_NAME: str = "Claimly RAG Chatbot"
    DEBUG: bool = True
    APP_SECRET: str
    
    # API URLs
    IDENTITY_API_URL: str
    MEDICAL_API_URL: str
    MEDICAL_API_TOKEN: Optional[str] = None
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Gemini AI
    GEMINI_API_KEY: str
    
    # Config for .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global Settings Instance
settings = Settings()
