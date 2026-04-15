from app.core.supabase import supabase_vector as supabase
from typing import List, Dict, Any, Optional

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
    async def get_vector_by_record_id(user_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Check if a specific medical record already has an embedding in Supabase."""
        response = supabase.table("session_vectors") \
            .select("content, embedding") \
            .eq("user_id", user_id) \
            .eq("record_id", record_id) \
            .limit(1) \
            .execute()
        
        return response.data[0] if response.data else None

    @staticmethod
    async def insert_vector(user_id: str, session_id: str, correlation_id: str, content: str, embedding: List[float], record_id: str = None):
        """Persist vector to Supabase including record_id for caching."""
        data = {
            "user_id": user_id,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "content": content,
            "embedding": embedding,
            "record_id": record_id
        }
        supabase.table("session_vectors").insert(data).execute()

    @staticmethod
    async def insert_vectors_batch(vectors_data: List[Dict[str, Any]]):
        """Persist multiple vectors to Supabase in a single request."""
        if not vectors_data:
            return
        supabase.table("session_vectors").insert(vectors_data).execute()

    @staticmethod
    async def delete_session_vectors(session_id: str):
        """Clean up all cached vectors for a session when it ends."""
        supabase.table("session_vectors") \
            .delete() \
            .eq("session_id", session_id) \
            .execute()

# Singleton
supabase_service = SupabaseService()
