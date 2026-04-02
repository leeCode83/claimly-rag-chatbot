# Claimly RAG Chatbot: Secure On-Demand Medical Assistant

**Claimly RAG Chatbot** adalah backend service berbasis AI yang mengutamakan privasi (*privacy-first*) dan *zero-persistence* untuk menangani rekam medis sensitif. Menggunakan **FastAPI**, **Redis (RAM-only)**, dan **Google Gemini**, sistem ini memberikan wawasan medis secara real-time melalui WebSockets yang aman.

---

## ⚡ Arsitektur Performa Tinggi (Windows Optimized)

![Architecture Diagram](file:///C:/Users/Leandro/.gemini/antigravity/brain/2c4128de-3e16-4ca3-ba05-0283bc7ccf2a/architecture_diagram_claimly_rag_1775119551723.png)

Sistem ini didesain khusus untuk menangani **100+ concurrent users** di lingkungan Windows dengan optimasi berikut:

- **Winloop (IOCP)**: Menggunakan event loop berbasis IOCP untuk I/O asinkron yang sangat cepat di Windows.
- **Shared PubSub Listener**: Menggunakan satu koneksi Redis Pub/Sub global per worker process. Pesan didistribusikan secara internal melalui `asyncio.Queue` (Fan-out pattern) untuk menghemat ribuan koneksi Redis.
- **Multi-Worker Scaling**: Berjalan dalam mode multi-process (4 API workers & 4 Worker instances) untuk memanfaatkan seluruh core CPU.

```mermaid
graph TD
    Client[100 VUs / k6] -->|WebSocket| API_LoadBalancer[FastAPI Multi-Worker]
    API_LoadBalancer -->|Shared Listener| Redis_PubSub((Redis Stream))
    API_LoadBalancer -->|Enqueue Job| ARQ_Queue((Redis Job Queue))
    ARQ_Queue -->|Process| RAG_Workers[4x Arq Workers]
    RAG_Workers -->|Publish| Redis_PubSub
```

---

## 🛠️ Sistem Mock (Developer Mode)

Untuk pengujian tanpa memakan kuota API atau membutuhkan database asli, gunakan flag environment berikut:

- `MOCK_AI=true`: Mengganti pemanggilan Gemini dengan respon streaming simulasi.
- `MOCK_AUTH=true`: Melewati validasi token Supabase (user_id otomatis `mock_user_123`).
- `MOCK_IDENTITY=true`: Menggunakan kunci enkripsi statis tanpa perlu derivasi Argon2id yang berat di CPU.

---

## 🚀 Cara Menjalankan (Production/Scale Mode)

Gunakan skrip PowerShell yang disediakan untuk konsistensi environment:

1.  **Jalankan Workers**:
    ```powershell
    .\run_workers.ps1
    ```
    *(Membuka 4 jendela worker baru dengan `MOCK_AI=true`)*

2.  **Jalankan API**:
    ```powershell
    .\run_api.ps1
    ```
    *(Menjalankan FastAPI dengan 4 workers di port 8000)*

---

## 📊 Load Testing (k6)

Kami menggunakan [k6](https://k6.io/) untuk memvalidasi performa sistem.

**Kebutuhan**: Instal k6 di Windows (`winget install gnu.k6`).

**Eksekusi Test**:
```powershell
k6 run tests/load/chat_load_test.js
```

**Target Performa (SLA)**:
- **TTFC (Time to First Chunk)**: p95 < 2.0 detik.
- **Success Rate**: 100% (No disconnected/timeout).

---

## 📂 Struktur Proyek & File Penting

| File / Folder | Fungsi Utama |
| :--- | :--- |
| `app/main.py` | Entry point dengan integrasi `winloop` dan `Shared PubSub Listener`. |
| `app/routers/websocket.py` | Manajemen koneksi WebSocket dengan sistem antrean internal per-user. |
| `app/workers/rag_worker.py` | Backend worker (ARQ) yang memproses tugas RAG berat. |
| `run_api.ps1` / `run_workers.ps1` | Skrip otomasi deployment lokal dengan konfigurasi optimal. |

---

## 📡 Skema WebSocket
1.  **session_init**: Server mengirim UUID sesi segera setelah koneksi terbuka.
2.  **input**: Client mengirim `{ "prompt", "password", "accessToken" }`.
3.  **status**: Server memberi tahu status proses (misal: "Menghubungi AI...").
4.  **chunk**: Server mendorong potongan teks secara real-time.
5.  **final**: Pesan `is_final: true` menandakan akhir dari satu jawaban.
