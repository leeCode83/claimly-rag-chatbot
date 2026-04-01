# Claimly RAG Chatbot: Secure On-Demand Medical Assistant

**Claimly RAG Chatbot** adalah backend service berbasis AI yang mengutamakan privasi (*privacy-first*) dan *zero-persistence* untuk menangani rekam medis sensitif. Menggunakan **FastAPI**, **Redis (RAM-only)**, dan **Google Gemini 2.5/3.0**, sistem ini memberikan wawasan medis secara real-time melalui WebSockets yang aman.

---

## 🛡️ Fitur Privasi & Keamanan
- **Arsitektur Zero-Persistence**: Menggunakan Redis RAM-only (RDB/AOF dinonaktifkan) untuk memastikan data sesi tidak pernah menyentuh hard disk.
- **Hybrid KMS Engine**: 
    - **Argon2id** (KDF) untuk derivasi *Key Encryption Key* (KEK) dengan entropi tinggi.
    - **AES-256-GCM** untuk enkripsi payload tugas *end-to-end*.
- **Pembersihan Proaktif**: Kunci sesi dan rekam medis yang didekripsi segera dihapus dari RAM setelah WebSocket terputus.
- **Optimasi Batch Embedding**: Menggunakan `gemini-embedding-001` dengan proses *batching* untuk efisiensi biaya dan performa tinggi.

## 🚀 Tech Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous Python)
- **AI/LLM**: [Google Gen AI SDK](https://github.com/google-gemini/generative-ai-python) (Gemini 2.5 Flash / Gemini 3.0)
- **Vector DB**: [Supabase](https://supabase.com/) (PostgreSQL + `pgvector`)
- **Task Queue**: [ARQ](https://github.com/samuelcolvin/arq) (Redis-based)
- **Caching/Streaming**: Redis (RAM-Only)

---

## 📂 Struktur Proyek & File Penting

| File / Folder | Fungsi Utama |
| :--- | :--- |
| `app/services/ai_service.py` | Pusat logika RAG, manajemen model Gemini, dan pembuatan *batch embedding*. |
| `app/services/medical_record_service.py` | Mengambil data rekam medis pasien dan melakukan perankingan relevansi (Phase 1). |
| `app/services/kms_service.py` | Menangani semua proses enkripsi/dekripsi Hybrid KMS untuk data medis sensitif. |
| `app/services/supabase_service.py` | Operasi database vektor, termasuk *batch insertion* dan sistem *caching vector*. |
| `app/routers/websocket.py` | Handler utama untuk koneksi real-time, autentikasi sesi, dan manajemen *feedback cycle*. |
| `app/workers/rag_worker.py` | Backend worker (ARQ) yang memproses tugas RAG berat di latar belakang. |

---

## 🏃 Cara Menjalankan Proyek

Pastikan Anda memiliki Python 3.12+ dan Redis yang berjalan di lokal.

1.  **Environment**: Salin `.env.example` ke `.env` dan isi kredensial Anda.
2.  **Server**: Jalankan FastAPI: `uvicorn app.main:app --reload`
3.  **Worker**: Jalankan ARQ: `arq app.workers.rag_worker.WorkerSettings`

---

## 📡 Panduan Pengujian (Postman)

Karena menggunakan WebSocket, Anda memerlukan fitur **WebSocket Request** di Postman:

1.  **URL**: Masukkan `ws://localhost:8000/ws/chat`.
2.  **Connect**: Klik tombol **Connect**. Server akan mengirimkan pesan `session_init` berisi UUID.
3.  **Payload**: Kirim pesan dalam format JSON:
    ```json
    {
      "prompt": "Apa diagnosa terakhir saya?",
      "password": "PASSWORD_DEKRIPSI_ANDA",
      "accessToken": "JWT_AUTH_TOKEN_SUPABASE"
    }
    ```
4.  **Streaming**: Anda akan melihat pesan masuk bertipe `chunk` yang merupakan respon asinkron dari AI Dr. Kalbe.

---

## 📡 Skema WebSocket
1.  **init**: Server mengirim `session_init` segera setelah koneksi terbuka.
2.  **input**: Client mengirim `{ "prompt", "password", "accessToken" }`.
3.  **status**: Server memberi tahu status proses (misal: "Menghubungi AI...").
4.  **streaming**: Server mendorong potongan teks melalui Redis Pub/Sub secara real-time.
5.  **final**: Pesan `is_final: true` menandakan akhir dari satu jawaban.

