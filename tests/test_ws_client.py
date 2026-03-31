import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://127.0.0.1:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        # 1. Listen for session ID
        init_msg = await websocket.recv()
        print(f"Server: {init_msg}")

        # 2. Send prompt and password
        payload = {
            "prompt": "Sebutkan riwayat alergi saya?",
            "password": "user-password-123"
        }
        await websocket.send(json.dumps(payload))
        print(f"Client: Sent prompt and password.")

        # 3. Listen for chunks
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            
            if data["type"] == "status":
                print(f"Status: {data['msg']}")
            elif data["type"] == "chunk":
                print(data["chunk"], end="", flush=True)
                if data["is_final"]:
                    print("\n[Chat Selesai]")
                    break

if __name__ == "__main__":
    asyncio.run(test_chat())
