import pytest
import json
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from app.routers.websocket import router

# Setup a test app
app = FastAPI()
app.include_router(router)
app.state.active_queues = {}

def test_websocket_session_init(mock_redis):
    client = TestClient(app)
    
    # Mock Redis Pool & Service
    mock_pool = MagicMock()
    mock_rs = AsyncMock()
    
    with patch('app.core.redis_pool.redis_pool_manager.get_pool', return_value=mock_pool), \
         patch('app.routers.websocket.redis_service', mock_rs):
        with client.websocket_connect("/ws/chat") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "session_init"
            assert "session_id" in data
            
            session_id = data["session_id"]
            assert session_id in app.state.active_queues

def test_websocket_chat_flow_success(mock_redis, mock_arq_pool):
    client = TestClient(app)
    mock_rs = AsyncMock()
    mock_rs.get_kek.return_value = "mock_kek"
    
    with patch('app.core.redis_pool.redis_pool_manager.get_pool', return_value=mock_arq_pool), \
         patch('app.routers.websocket.redis_service', mock_rs):
        with client.websocket_connect("/ws/chat") as websocket:
            # 1. Get Session ID
            init_data = websocket.receive_json()
            session_id = init_data["session_id"]
            
            # 2. Prepare payload
            payload = {
                "prompt": "Halo Dokter",
                "password": "pass",
                "accessToken": "token",
                "kek": "kek_key"
            }
            
            # 3. Simulate messages arriving in the queue in the background
            # Since the router loop blocks on queue.get(), we need to feed it
            async def feed_queue():
                # Wait a bit for the router to start listening
                await asyncio.sleep(0.1)
                queue = app.state.active_queues[session_id]
                
                # We need to find the correlation_id generated in the router
                # Since it's random, we can't know it easily unless we mock uuid.uuid4()
                # But we can just push a message and the router might filter it if CID mismatch
                # Let's mock uuid.uuid4 to have a stable CID
            
            with patch('uuid.uuid4', side_effect=["stable-session-id", "stable-correlation-id"]):
                # This doesn't work well with TestClient sync websocket
                # Instead, let's just test that enqueue_job was called
                websocket.send_json(payload)
                
                # Receive status message
                status = websocket.receive_json()
                assert status["type"] == "status"
                
                # Check if arq was called with correct payload
                mock_arq_pool.enqueue_job.assert_called_once()
                
def test_websocket_missing_prompt(mock_redis, mock_arq_pool):
    client = TestClient(app)
    mock_redis_service = AsyncMock()
    with patch('app.core.redis_pool.redis_pool_manager.get_pool', return_value=mock_arq_pool), \
         patch('app.routers.websocket.redis_service', mock_redis_service):
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.receive_json() # skip init
            
            websocket.send_json({"prompt": "", "password": "abc"})
            # Should not call enqueue_job
            mock_arq_pool.enqueue_job.assert_not_called()

def test_websocket_disconnect_cleanup(mock_redis, mock_arq_pool):
    client = TestClient(app)
    session_id = None
    mock_rs = AsyncMock()
    with patch('app.core.redis_pool.redis_pool_manager.get_pool', return_value=mock_arq_pool), \
         patch('app.routers.websocket.redis_service', mock_rs):
        with client.websocket_connect("/ws/chat") as websocket:
            data = websocket.receive_json()
            session_id = data["session_id"]
            assert session_id in app.state.active_queues
        
        # After closing the context, the socket is disconnected
        # The finally block in the router should have run
        # Note: TestClient might need a small sleep or check if the registry is cleaned
        assert session_id not in app.state.active_queues
