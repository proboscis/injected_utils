import asyncio
import pytest
from injected_utils.async_caching.async_cached_function import (
    BlockingDictAsyncCache,
    ThreadPooledDictAsyncCache,
    AsyncCachedFunctionV2
)

# テスト用のヘルパー関数とカウンター
call_count = 0

async def mock_async_function(x: int) -> int:
    global call_count
    call_count += 1
    return x * 2

async def mock_failing_function(x: int) -> int:
    raise ValueError("Test error")

async def mock_temporary_failing_function(x: int) -> int:
    global call_count
    call_count += 1
    if call_count == 1:
        raise ValueError("Temporary error")
    return x * 2

async def custom_error_handler(e: Exception) -> str:
    if isinstance(e, ValueError):
        return "Retrying after ValueError"
    return ""

async def mock_key_function(*args, **kwargs) -> str:
    return f"key-{args}-{sorted(kwargs.items())}"

async def mock_none_function(x: int) -> None:
    return None

async def mock_invalidate_check(inputs: tuple, value: int | None) -> str:
    if value is None:
        return ""  # None値は無効化しない
    args, kwargs = inputs
    x = args[0] if args else kwargs.get('x')
    # 値が20より大きい場合は無効化
    if value > 20:
        return "Value too large"
    return ""

# フィクスチャ
@pytest.fixture
def blocking_cache():
    return BlockingDictAsyncCache(src={})

@pytest.fixture
def thread_pooled_cache():
    return ThreadPooledDictAsyncCache(src={})

@pytest.fixture(autouse=True)
def reset_call_count():
    global call_count
    call_count = 0

# テストケース
@pytest.mark.asyncio
async def test_blocking_dict_cache_basic_operations(blocking_cache):
    key = "test_key_1"  # ハッシュ可能な文字列キー
    value = 42
    
    # セット操作のテスト
    await blocking_cache.a_set(key, value)
    
    # 存在確認のテスト
    assert await blocking_cache.a_contains(key)
    
    # 取得操作のテスト
    result = await blocking_cache.a_get(key)
    assert result == value

@pytest.mark.asyncio
async def test_cached_function_hit_miss(blocking_cache):
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 初回呼び出し(キャッシュミス)
    result1 = await cached_func(5)
    assert result1 == 10
    
    # 2回目の呼び出し(キャッシュヒット)
    result2 = await cached_func(5)
    assert result2 == 10
    
    # 異なる引数での呼び出し(キャッシュミス)
    result3 = await cached_func(3)
    assert result3 == 6

@pytest.mark.asyncio
async def test_error_handling(blocking_cache):
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_failing_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    with pytest.raises(ValueError):
        await cached_func(5)

@pytest.mark.asyncio
async def test_thread_pooled_cache_concurrent(thread_pooled_cache):
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=thread_pooled_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 複数の非同期呼び出しを同時に実行
    tasks = [cached_func(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    
    assert results == [0, 2, 4, 6, 8]

@pytest.mark.asyncio
async def test_thread_pooled_cache_thread_safety(thread_pooled_cache):
    # スレッドセーフティをテストするために多数の同時実行を行う
    n_iterations = 100
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=thread_pooled_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 同じキーに対して複数回の同時アクセス
    tasks = [cached_func(5) for _ in range(n_iterations)]
    results = await asyncio.gather(*tasks)
    
    # すべての結果が同じであることを確認
    assert all(result == 10 for result in results)

@pytest.mark.asyncio
async def test_custom_key_function(blocking_cache):
    """カスタムキー関数のテスト"""
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 通常の引数でのテスト
    result1 = await cached_func(5)
    assert result1 == 10
    assert call_count == 1
    
    # 同じ引数での2回目の呼び出し
    result2 = await cached_func(5)
    assert result2 == 10
    assert call_count == 1  # キャッシュヒットのため増加しない
    
    # キーワード引数でのテスト
    result3 = await cached_func(x=5)
    assert result3 == 10
    assert call_count == 2  # 異なるキーとして扱われる

@pytest.mark.asyncio
async def test_temporary_error_recovery(blocking_cache):
    """一時的なエラーからの回復をテスト"""
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_temporary_failing_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 最初の呼び出しで一時的なエラー
    with pytest.raises(ValueError, match="Temporary error"):
        await cached_func(5)
    assert call_count == 1  # エラーで1回

    # リトライで正常に値を取得
    result1 = await cached_func(5)
    assert result1 == 10
    assert call_count == 2  # 2回目の呼び出しで成功

    # 2回目の呼び出しはキャッシュから
    result2 = await cached_func(5)
    assert result2 == 10
    assert call_count == 2  # キャッシュヒットのため増加しない

@pytest.mark.asyncio
async def test_none_value_caching(blocking_cache):
    """None値のキャッシング動作をテスト"""
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_none_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # None値を返す関数の呼び出し
    result1 = await cached_func(5)
    assert result1 is None
    
    # キャッシュからNone値を取得
    result2 = await cached_func(5)
    assert result2 is None
    
    # キャッシュが正しく動作していることを確認
    key = await mock_key_function(5)
    assert await blocking_cache.a_contains(key)

@pytest.mark.asyncio
async def test_kwargs_handling(blocking_cache):
    """キーワード引数の処理をテスト"""
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 異なる順序での同じキーワード引数
    result1 = await cached_func(x=5)
    assert result1 == 10
    assert call_count == 1
    
    # 順序が異なる同じキーワード引数
    result2 = await cached_func(x=5)
    assert result2 == 10
    assert call_count == 1  # キャッシュヒットのため増加しない

@pytest.mark.asyncio
async def test_cache_invalidation(blocking_cache):
    """キャッシュ無効化機能のテスト"""
    cached_func = AsyncCachedFunctionV2(
        a_func=mock_async_function,
        a_param_to_key=mock_key_function,
        cache=blocking_cache,
        a_is_error_to_retry=custom_error_handler,
        a_invalidate_value=mock_invalidate_check
    )
    
    # 大きな値を使用して無効化をトリガー
    result1 = await cached_func(15)  # 15 * 2 = 30 > 20 なので無効化される
    assert result1 == 30
    assert call_count == 1
    
    # 同じ値で再度呼び出し - キャッシュは無効化されるため再計算される
    result2 = await cached_func(15)
    assert result2 == 30
    assert call_count == 2  # 無効化により再計算
    
    # 小さな値でテスト - 無効化されない
    result3 = await cached_func(5)  # 5 * 2 = 10 < 20 なので無効化されない
    assert result3 == 10
    assert call_count == 3
    
    # 同じ小さな値で再度呼び出し - キャッシュが有効
    result4 = await cached_func(5)
    assert result4 == 10
    assert call_count == 3  # キャッシュヒットのため増加しない