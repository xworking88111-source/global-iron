"""從免費資料來源抓資料的函式。

只有 `scripts/update_data.py` 會呼叫這裡。網站本身在使用者瀏覽時「不會」連網抓
資料，只讀快取檔。好處：頁面快、不會被資料源限流；資料源掛掉時，網站只是資料
變舊，而不會整個壞掉。
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import pandas as pd

log = logging.getLogger(__name__)


def _retry(fn: Callable, tries: int = 3, wait: float = 3.0):
    """最多呼叫 fn() `tries` 次。新浪／Yahoo 偶爾會暫時逾時，重試通常就好了。"""
    last_err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 任何網路或解析錯誤都值得重試
            last_err = e
            log.warning("attempt %d/%d failed: %s", i + 1, tries, e)
            time.sleep(wait * (i + 1))  # 每次失敗等久一點再試
    raise last_err


# ---------------------------------------------------------------------------
# 中國期貨（上期所／大商所），來源：新浪財經
# ---------------------------------------------------------------------------
# 這就是 `akshare` 套件背後用的同一個公開介面。我們直接呼叫，
# 因為 akshare 把逾時寫死成 10 秒，鐵礦的長歷史資料常常超過。
_SINA_KLINE = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{sym}{tag}=/InnerFuturesNewService.getDailyKLine"


def fetch_cn_future(symbol: str, start: str) -> pd.Series:
    """主力連續合約的每日收盤價，例如 'HC0' = 上期所熱軋卷。

    「主力連續」會把持倉量最大的合約月份接起來，所以換月那天可能有小跳動。
    """
    import json
    import re

    import requests

    tag = pd.Timestamp.today().strftime("_%Y_%m_%d")

    def call():
        r = requests.get(_SINA_KLINE.format(sym=symbol, tag=tag),
                         params={"symbol": symbol, "type": tag[1:]},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        # 回應是 JSONP 格式：`var _X=([...]);`，用正規表達式取出中間的 JSON 陣列
        m = re.search(r"\((\[.*\])\)", r.text, re.S)
        if not m:
            raise ValueError(f"unexpected Sina response for {symbol}")
        return json.loads(m.group(1))

    rows = _retry(call)
    # 欄位：d=日期 o=開盤 h=最高 l=最低 c=收盤 v=成交量 p=持倉量 s=結算價
    df = pd.DataFrame(rows)
    s = pd.Series(df["c"].astype(float).values, index=pd.to_datetime(df["d"]), name=symbol)
    return s[s.index >= start].sort_index()


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def fetch_yf_history(tickers: list[str], start: str | None = None, period: str | None = None) -> pd.DataFrame:
    """每日收盤價，一個代碼一欄。抓不到的代碼會是整欄空值。"""
    import yfinance as yf

    kwargs = {"start": start} if start else {"period": period or "5y"}

    def call():
        # auto_adjust=True：股價已調整除權息，報酬率計算才正確
        return yf.download(tickers, auto_adjust=True, progress=False, threads=True, **kwargs)

    raw = _retry(call)
    if raw.empty:
        return pd.DataFrame(columns=tickers)
    # 多個代碼時欄位是兩層（欄位種類, 代碼），只取 Close 這層
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
    return close.reindex(columns=tickers)


# 從 yfinance 的 .info 中保留的欄位（原本有約 150 個，多數用不到）
_INFO_FIELDS = [
    "currency", "financialCurrency", "marketCap", "priceToBook", "trailingPE", "forwardPE",
    "debtToEquity", "ebitda", "totalRevenue", "ebitdaMargins", "profitMargins", "operatingMargins",
    "returnOnEquity", "dividendYield", "totalDebt", "totalCash", "currentRatio", "beta",
]


def fetch_yf_fundamentals(ticker: str) -> dict:
    """單一代碼的基本面快照。Yahoo 沒資料時各欄位為 None。"""
    import yfinance as yf

    info = _retry(lambda: yf.Ticker(ticker).info, tries=2)
    return {k: info.get(k) for k in _INFO_FIELDS}


def fetch_fx_to_usd(currencies: set[str]) -> dict[str, float]:
    """各幣別最新的「1 美元可換多少該幣」（USD 本身為 1.0）。用來把市值等換算成美元。"""
    out = {"USD": 1.0}
    need = sorted(c for c in currencies if c and c != "USD")
    if not need:
        return out
    df = fetch_yf_history([f"{c}=X" for c in need], period="10d")
    for c in need:
        col = df.get(f"{c}=X")
        if col is not None and col.dropna().size:
            out[c] = float(col.dropna().iloc[-1])
    return out
