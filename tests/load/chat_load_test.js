import ws from "k6/ws";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

/**
 * LOAD TEST CONFIGURATION (MOCK MODE)
 * Pastikan di .env backend:
 * MOCK_AI=true
 * MOCK_AUTH=true
 */

// Kustom Metrik
const messagesSent = new Counter("messages_sent");
const messagesReceived = new Counter("messages_received");
const ttfr = new Trend("time_to_first_response", true); // Latensi sampai pesan 'status' (Worker ACK)
const ttfc = new Trend("time_to_first_chunk", true);    // Latensi sampai data AI pertama muncul
const ttc = new Trend("time_to_complete", true);       // Total waktu sampai streaming selesai

export const options = {
  stages: [
    { duration: "10s", target: 20 }, // Warm up
    { duration: "40s", target: 100 }, // Stress test 100 users
    { duration: "10s", target: 0 },  // Cool down
  ],
  thresholds: {
    time_to_first_response: ["p(95)<1000"], // Status ACK harus < 1 detik
    time_to_first_chunk: ["p(95)<3000"],    // AI Mock Response < 3 detik
    time_to_complete: ["p(95)<8000"],       // Total chat < 8 detik (termasuk streaming)
  },
};

export default function () {
  const url = "ws://localhost:8000/ws/chat";
  const params = { tags: { my_tag: "chatbot_mock_load_test" } };

  const res = ws.connect(url, params, function (socket) {
    let startTime;
    let firstResponseTime;
    let firstChunkTime;
    let isComplete = false;

    socket.on("open", () => {
      // Tunggu session_init dari server
    });

    socket.on("message", (data) => {
      const message = JSON.parse(data);

      if (message.type === "session_init") {
        startTime = Date.now();
        socket.send(
          JSON.stringify({
            prompt: "Halo Dr. Claimly, ini adalah tes beban otomatis (MOCK).",
            password: "password_tes_123",
            accessToken: "mock_token_load_test",
          }),
        );
        messagesSent.add(1);

      } else if (message.type === "status") {
        // Server mengakui request dan masuk ke worker
        if (!firstResponseTime) {
          firstResponseTime = Date.now();
          ttfr.add(firstResponseTime - startTime);
        }

      } else if (message.type === "chunk") {
        // AI mulai mengirimkan data
        if (!firstChunkTime) {
          firstChunkTime = Date.now();
          ttfc.add(firstChunkTime - startTime);
        }

        if (message.is_final) {
          ttc.add(Date.now() - startTime);
          isComplete = true;
          socket.close();
        }
        messagesReceived.add(1);

      } else if (message.type === "password_required") {
        // Jika mode MOCK tidak sengaja memicu ini
        console.warn(`Warning: Password required for diagnostic ${message.diagnosis}`);
        socket.close();

      } else if (message.type === "error") {
        console.error(`Error received: ${message.msg}`);
        socket.close();
      }
    });

    socket.on("close", () => {
      // Disconnected
    });

    socket.on("error", (e) => {
      console.error(`WebSocket Error: ${e.error()}`);
    });

    // Timeout pengamanan (30 detik)
    socket.setTimeout(() => {
      if (!isComplete) {
        console.log("Test execution timed out");
        socket.close();
      }
    }, 30000);
  });

  check(res, { "status is 101": (r) => r && r.status === 101 });
}
