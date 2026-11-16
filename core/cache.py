"""計算結果快取。

網站上每個人看到的圖表都一樣（同樣的資料、同樣的選項），沒必要每次重算。
`@cached` 會記住「資料版本 + 參數」對應的結果；資料檔一更新（版本改變），
就自動重新計算。Render 免費方案的 CPU 很弱，這是讓頁面變快的關鍵。

注意：被快取的函式參數必須可雜湊（list 請先轉成 tuple），
回傳的物件會被多個請求共用，呼叫端不可以修改它。

--- English ---
Result cache.

Every visitor sees the same charts for the same data and options, so there is
no need to recompute. `@cached` remembers results per (data version, arguments);
when any data file changes, the version changes and results are recomputed.
Key to fast pages on Render's low-CPU free tier.

Note: cached function arguments must be hashable (convert lists to tuples), and
returned objects are shared between requests, so callers must not mutate them.
"""
from __future__ import annotations

from functools import lru_cache, wraps

from . import data


def cached(maxsize: int = 128):
    def deco(fn):
        @lru_cache(maxsize=maxsize)
        def inner(_version, *args):
            return fn(*args)

        @wraps(fn)
        def wrapper(*args):
            return inner(data.version(), *args)

        wrapper.cache_clear = inner.cache_clear
        return wrapper
    return deco
