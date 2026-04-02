import ws from "k6/ws";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

// Kustom Metrik
const messagesSent = new Counter("messages_sent");
const messagesReceived = new Counter("messages_received");
const ttfc = new Trend("time_to_first_chunk", true); // Time to first chunk
const ttc = new Trend("time_to_complete", true); // Time to complete stream

export const options = {
  stages: [
    { duration: "30s", target: 50 }, // Ramp up ke 50 user
    { duration: "1m", target: 100 }, // Stabil di 100 user
    { duration: "30s", target: 0 }, // Ramp down
  ],
  thresholds: {
    time_to_first_chunk: ["p(95)<2000"], // 95% user harus dapat chunk pertama < 2 detik
    time_to_complete: ["p(95)<10000"], // 95% user harus selesai < 10 detik
  },
};

export default function () {
  const url = "ws://localhost:8000/ws/chat";
  const params = { tags: { my_tag: "chatbot_load_test" } };

  const res = ws.connect(url, params, function (socket) {
    let startTime;
    let firstChunkTime;
    let isComplete = false;

    socket.on("open", () => {
      // console.log('Connected to WebSocket');
    });

    socket.on("message", (data) => {
      const message = JSON.parse(data);

      if (message.type === "session_init") {
        // Sesi diinisialisasi, kirim prompt
        startTime = Date.now();
        socket.send(
          JSON.stringify({
            prompt: "Halo Dr. Claimly, bagaimana hasil lab saya kemarin?",
            password: "password_tes_123",
            accessToken: "mock_token_load_test",
          }),
        );
        messagesSent.add(1);
      } else if (message.type === "chunk") {
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
      } else if (message.type === "error") {
        console.error(`Error received: ${message.msg}`);
        socket.close();
      }
    });

    socket.on("close", () => {
      // console.log('Disconnected');
    });

    socket.on("error", (e) => {
      console.error(`WebSocket Error: ${e.error()}`);
    });

    // Paksa timeout jika tidak selesai dalam 30 detik
    socket.setTimeout(() => {
      if (!isComplete) {
        console.log("Test timed out");
        socket.close();
      }
    }, 30000);
  });

  check(res, { "status is 101": (r) => r && r.status === 101 });
}
