import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.redis_pool import RedisPool

class TestRedisPool:
    @pytest.fixture
    def pool_manager(self):
        return RedisPool()

    @pytest.mark.asyncio
    async def test_connect_success(self, pool_manager, mocker):
        mock_pool = AsyncMock()
        with patch('app.core.redis_pool.create_pool', return_value=mock_pool) as mock_create:
            await pool_manager.connect()
            
            assert pool_manager.pool is not None
            mock_create.assert_called_once()
            assert pool_manager.get_pool() == mock_pool

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, pool_manager, mocker):
        mock_pool = AsyncMock()
        pool_manager.pool = mock_pool
        
        with patch('app.core.redis_pool.create_pool') as mock_create:
            await pool_manager.connect()
            # Should not call create_pool again
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pool_failure(self, pool_manager):
        # Test error when pool is not initialized
        pool_manager.pool = None
        with pytest.raises(RuntimeError, match="not connected"):
            pool_manager.get_pool()

    @pytest.mark.asyncio
    async def test_disconnect_success(self, pool_manager):
        mock_pool = AsyncMock()
        pool_manager.pool = mock_pool
        
        await pool_manager.disconnect()
        
        mock_pool.close.assert_called_once()
        assert pool_manager.pool is None

    @pytest.mark.asyncio
    async def test_connect_exception(self, pool_manager):
        with patch('app.core.redis_pool.create_pool', side_effect=Exception("Redis Down")):
            with pytest.raises(Exception, match="Redis Down"):
                await pool_manager.connect()
