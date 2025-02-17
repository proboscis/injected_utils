import asyncio
from pathlib import Path
import pytest
import pytest_asyncio
from injected_utils.async_caching.async_sqlite import AsyncSqlite

@pytest.fixture
def db_path(tmp_path):
    """テスト用の一時的なデータベースパスを提供"""
    return tmp_path / "test.db"

@pytest_asyncio.fixture
async def async_sqlite(db_path):
    """テスト用のAsyncSqliteインスタンスを提供"""
    sqlite = AsyncSqlite(db_path)
    yield sqlite  # テスト終了後にデータベースを自動的にクリーンアップ

@pytest.mark.asyncio
async def test_basic_set_get(async_sqlite):
    """基本的なset/get操作のテスト"""
    key = b"test_key"
    value = b"test_value"
    
    await async_sqlite.a_set(key, value)
    result = await async_sqlite.a_get(key)
    
    assert result == value

@pytest.mark.asyncio
async def test_key_error(async_sqlite):
    """存在しないキーへのアクセスのテスト"""
    with pytest.raises(KeyError):
        await async_sqlite.a_get(b"non_existent_key")

@pytest.mark.asyncio
async def test_value_override(async_sqlite):
    """値の上書きのテスト"""
    key = b"override_key"
    value1 = b"value1"
    value2 = b"value2"
    
    await async_sqlite.a_set(key, value1)
    await async_sqlite.a_set(key, value2)
    
    result = await async_sqlite.a_get(key)
    assert result == value2

@pytest.mark.asyncio
async def test_concurrent_table_creation(async_sqlite):
    """テーブル作成の同時実行テスト"""
    async def concurrent_set(key: bytes, value: bytes):
        await async_sqlite.a_set(key, value)
    
    tasks = [
        concurrent_set(f"key{i}".encode(), f"value{i}".encode())
        for i in range(5)
    ]
    
    await asyncio.gather(*tasks)
    
    # すべての値が正しく保存されていることを確認
    for i in range(5):
        key = f"key{i}".encode()
        expected_value = f"value{i}".encode()
        result = await async_sqlite.a_get(key)
        assert result == expected_value

@pytest.mark.asyncio
async def test_contains(async_sqlite):
    """キーの存在確認のテスト"""
    key = b"test_key"
    value = b"test_value"
    
    # キーが存在しない場合
    assert not await async_sqlite.a_contains(key)
    
    # キーを追加
    await async_sqlite.a_set(key, value)
    
    # キーが存在する場合
    assert await async_sqlite.a_contains(key)