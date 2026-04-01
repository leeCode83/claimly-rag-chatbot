from supabase import create_client, Client
from app.core.config import settings

# Hybrid Supabase Clients
# supabase_vector: Mengarah ke Cloud (untuk tabel session_vectors)
supabase_vector: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# supabase_auth: Mengarah ke Lokal / Auth Provider (untuk verifikasi JWT)
# Jika SUPABASE_AUTH_URL tidak diset, gunakan cloud client sebagai default
auth_url = settings.SUPABASE_AUTH_URL or settings.SUPABASE_URL
auth_key = settings.SUPABASE_AUTH_KEY or settings.SUPABASE_KEY

supabase_auth: Client = create_client(auth_url, auth_key)

# Backward Compatibility Helper (using vector client by default)
supabase = supabase_vector

def get_supabase() -> Client:
    return supabase_vector

def get_supabase_auth() -> Client:
    return supabase_auth
