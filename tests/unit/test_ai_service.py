import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.ai_service import AIService
import json

class TestAIService:
    @pytest.fixture
    def ai_service(self):
        return AIService()

    @pytest.mark.asyncio
    async def test_get_embedding_success(self, ai_service, mocker):
        # Setup Mock Client
        mock_client = MagicMock()
        mock_async_client = AsyncMock()
        mock_client.aio.__aenter__.return_value = mock_async_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]
        mock_async_client.models.embed_content.return_value = mock_response
        
        with patch('google.genai.Client', return_value=mock_client):
            embedding = await ai_service.get_embedding("test text")
            
            assert embedding == [0.1, 0.2, 0.3]
            mock_async_client.models.embed_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_medical_intent_medical(self, ai_service, mocker):
        mock_client = MagicMock()
        mock_async_client = AsyncMock()
        mock_client.aio.__aenter__.return_value = mock_async_client
        
        mock_response = MagicMock()
        mock_response.text = "medical"
        mock_async_client.models.generate_content.return_value = mock_response
        
        with patch('google.genai.Client', return_value=mock_client):
            intent = await ai_service.detect_medical_intent("Sakit perut")
            assert intent == "medical"

    @pytest.mark.asyncio
    async def test_detect_medical_intent_general(self, ai_service, mocker):
        mock_client = MagicMock()
        mock_async_client = AsyncMock()
        mock_client.aio.__aenter__.return_value = mock_async_client
        
        mock_response = MagicMock()
        mock_response.text = "general"
        mock_async_client.models.generate_content.return_value = mock_response
        
        with patch('google.genai.Client', return_value=mock_client):
            intent = await ai_service.detect_medical_intent("Halo")
            assert intent == "general"

    @pytest.mark.asyncio
    async def test_stream_rag_answer_success(self, ai_service, mocker):
        mock_client = MagicMock()
        mock_async_client = AsyncMock()
        mock_client.aio.__aenter__.return_value = mock_async_client
        
        # Mock stream items
        class MockChunk:
            def __init__(self, text):
                self.text = text
                
        async def mock_stream(*args, **kwargs):
            yield MockChunk("Hello ")
            yield MockChunk("World")
            
        mock_async_client.models.generate_content_stream.return_value = mock_stream()
        
        with patch('google.genai.Client', return_value=mock_client):
            results = []
            async for chunk in ai_service.stream_rag_answer("Hi", "Context"):
                results.append(chunk)
            
            assert "".join(results) == "Hello World"

    @pytest.mark.asyncio
    async def test_detect_medical_intent_fallback(self, ai_service, mocker):
        # Test exception handling (network error etc)
        with patch('google.genai.Client', side_effect=Exception("API Down")):
            intent = await ai_service.detect_medical_intent("Any prompt")
            # Should fallback to 'medical' for safety as per code
            assert intent == "medical"
