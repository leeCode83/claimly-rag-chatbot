# Claimly RAG Chatbot: Secure On-Demand Medical Assistant

**Claimly RAG Chatbot** is a privacy-first, zero-persistence backend service designed to handle sensitive medical records. It leverages **FastAPI**, **Redis (RAM-only)**, and **Google Gemini 2.5/3.0** to provide real-time, RAG-enabled medical insights via secure WebSockets.

---

## 🛡️ Privacy & Security Features
- **Zero-Persistence Architecture**: Configured with a RAM-only Redis (RDB/AOF disabled) to ensure session data never touches the disk.
- **KMS Hybrid Engine**: 
    - Uses **Argon2id** (KDF) for high-entropy Key Encryption Key (KEK) derivation.
    - Uses **AES-256-GCM** for end-to-end task payload encryption.
- **Proactive Cleanup**: Session keys and sensitive decrypted records are immediately purged from RAM upon WebSocket disconnection.
- **Sticky Vectors**: Embeddings are temporarily stored and validated against user consent, ensuring data isolation.

## 🚀 Tech Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous Python)
- **AI/LLM**: [Google Gen AI SDK](https://github.com/google-gemini/generative-ai-python) (Gemini 2.5 Flash / Gemini 3.0)
- **Vector DB**: [Supabase](https://supabase.com/) (PostgreSQL + `pgvector`)
- **Task Queue**: [ARQ](https://github.com/samuelcolvin/arq) (Redis-based)
- **Caching/Streaming**: Redis (RAM-Only)

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.12+
- Redis Server (Running locally or via Docker)
- Supabase Project with `pgvector` enabled

### 2. Environment Configuration
Copy the template and fill in your credentials:
```bash
cp .env.example .env
```
Key requirements in `.env`:
- `GEMINI_API_KEY`: Your Google AI Studio API Key.
- `APP_SECRET`: A secure 32-character string.
- `REDIS_URL`: Defaults to `redis://localhost:6379`.

### 3. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🏃 Running the Project

To run the full E2E pipeline, you need three processes running:

### Terminal 1: FastAPI Server
```bash
uvicorn app.main:app --reload
```

### Terminal 2: ARQ Worker
```bash
arq app.workers.rag_worker.WorkerSettings
```

### Terminal 3: Test Client (Simulation)
```bash
python tests/test_ws_client.py
```

---

## 📡 WebSocket API (Sequential Interaction)
The chatbot uses a stateful WebSocket at `/ws/chat`:
1. **init**: Server sends `session_init` with a UUID.
2. **input**: Client sends `{ "prompt": "...", "password": "..." }`.
3. **status**: Server notifies `Menghubungi AI...`.
4. **streaming**: Server pushes text chunks via Redis Pub/Sub.
5. **final**: Connection stays open for the next prompt or until closed.

---

## 📂 Project Structure
```text
app/
├── core/        # Configuration & Singletons (Supabase, Settings)
├── models/      # Pydantic Schemas & Data Models
├── routers/     # WebSocket & HTTP Route Handlers
├── services/    # Business Logic (KMS, AI, Redis, Supabase)
├── workers/     # Background ARQ Task Processing
└── utils/       # Mocks & Helper Functions
```

