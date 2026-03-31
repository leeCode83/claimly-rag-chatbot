from supabase import create_client, Client
from app.core.config import settings

# Global Supabase Client
# Initialized once during application lifecycle
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Helper to check connection (optional)
def get_supabase() -> Client:
    return supabase
