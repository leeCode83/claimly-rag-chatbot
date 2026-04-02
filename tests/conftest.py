import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Ensure tests always use mock settings."""
    monkeypatch.setenv("MOCK_AI", "true")
    monkeypatch.setenv("MOCK_AUTH", "true")
    monkeypatch.setenv("MOCK_IDENTITY", "true")
    monkeypatch.setenv("APP_SECRET", "test_secret_32_chars_long_long_long")

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    return mock

@pytest.fixture
def mock_arq_pool():
    """Mock ARQ Redis pool."""
    mock = MagicMock()
    # mock.enqueue_job is async, so we need to mock it as such
    async def side_effect(*args, **kwargs):
        return MagicMock()
    mock.enqueue_job.side_effect = side_effect
    return mock

@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock = MagicMock()
    # Mock chainable calls like supabase.table().select().execute()
    mock.table.return_value.select.return_value.execute.return_value.data = []
    return mock

@pytest.fixture(autouse=True)
def mock_redis_service_global():
    """Mock the global redis_service singleton to avoid real connections."""
    mock = MagicMock()
    mock.get_kek = AsyncMock(return_value="test_kek")
    mock.delete_kek = AsyncMock()
    mock.save_kek = AsyncMock()
    
    # Patch the singleton instance in the service module
    with patch("app.services.redis_service.redis_service", mock):
        yield mock
