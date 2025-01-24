from hashlib import sha256
from typing import TypeVar, Callable, Awaitable
import inspect

import jsonpickle
from pinjected import *

T = TypeVar('T')
U = TypeVar('U')

@injected
def async_batch_cached(
        injected_utils_default_hasher,
        /,
        cache: dict,
        hasher: Callable[[T], str] = None
):
    """
    バッチ処理用のキャッシュデコレータ。
    入力アイテムのリストに対して、既にキャッシュされている結果は再利用し、
    キャッシュされていないアイテムのみを計算します。

    :param injected_utils_default_hasher: デフォルトのハッシュ関数
    :param cache: キャッシュとして使用する辞書オブジェクト
    :param hasher: カスタムハッシュ関数（オプション）
    :return: デコレータ関数
    """
    hasher = injected_utils_default_hasher if hasher is None else hasher

    def get_impl(func: Callable[[tuple[T]], Awaitable[list[U]]]):
        # funcの引数が*varargs（可変長引数）を持つことを確認
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        assert any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params), \
            f"func must have *args parameter, but got {sig}"

        async def impl(*items: list[T]) -> list[U]:
            # 1. 各アイテムのハッシュ値を計算
            key_to_item = {hasher(i): i for i in items}
            # 2. キャッシュにない項目を特定
            keys_to_calc = [k for k in key_to_item.keys() if k not in cache]
            # 3. キャッシュにないアイテムのみを計算
            inputs = [key_to_item[k] for k in keys_to_calc]
            if inputs:  # 計算が必要なアイテムがある場合のみ関数を実行
                results = await func(*inputs)
                # 4. 新しい結果をキャッシュに保存
                for k, r in zip(keys_to_calc, results):
                    cache[k] = r
            # 5. すべての結果を返す（キャッシュ + 新規計算）
            return [cache[k] for k in key_to_item.keys()]
        return impl
    return get_impl

@async_batch_cached(cache=dict())
@injected 
async def _test_function_batch_cached(*items):
    return items

run_test_function_batch_cached: IProxy = _test_function_batch_cached(1,2,3,4,5)

__meta_design__ = design(
    overrides=design(
        injected_utils_default_hasher=lambda item: sha256(jsonpickle.dumps(item).encode()).hexdigest()
    )
)