from app.core.supabase import supabase
from typing import List, Dict, Any

class SupabaseService:
    @staticmethod
    async def match_records(user_id: str, embedding: List[float], threshold: float = 0.5, limit: int = 5) -> List[Dict[str, Any]]:
        """Query the vector store for matching medical records using RPC."""
        # Note: RPC parameters must match the SQL function exactly
        response = supabase.rpc(
            "match_medical_records",
            {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": limit,
                "p_user_id": user_id
            }
        ).execute()
        return response.data

    @staticmethod
    async def insert_vector(user_id: str, session_id: str, correlation_id: str, content: str, embedding: List[float]):
        """Persist vector to Supabase."""
        data = {
            "user_id": user_id,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "content": content,
            "embedding": embedding
        }
        supabase.table("session_vectors").insert(data).execute()

# Singleton
supabase_service = SupabaseService()
