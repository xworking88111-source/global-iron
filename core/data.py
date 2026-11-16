"""網站讀取資料用的函式。

所有讀取函式都以（檔案路徑, 修改時間）做快取：更新腳本改寫快取檔之後，
下一個請求就會讀到新資料，不需要重啟伺服器。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import config


def _mtime(p: Path) -> float:
    """檔案最後修改時間；檔案不存在回傳 0。"""
    return p.stat().st_mtime if p.exists() else 0.0


# ---------------------------------------------------------------------------
# 靜態（人工整理）資料
# ---------------------------------------------------------------------------
@lru_cache(maxsize=32)
def _load_json(path: str, mtime: float) -> dict:  # mtime 只用來當快取的 key，檔案一改就會重讀
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return _load_json(str(path), _mtime(path))


def companies(industry: str = "steel") -> pd.DataFrame:
    """某產業的所有公司，一列一家。`industry` 參數先預留給未來的其他產業。"""
    raw = load_json(config.STATIC_DIR / "companies.json")
    df = pd.DataFrame(raw.get("companies", []))
    # 布林欄位在 JSON 裡多數公司沒寫，補成 False
    for col in ("sanctions", "highlight"):
        df[col] = df[col].fillna(False).astype(bool) if col in df else False
    return df


def company(cid: str) -> dict:
    """用 id 取單一公司（找不到回傳空 dict）。"""
    df = companies()
    row = df[df["id"] == cid]
    return row.iloc[0].to_dict() if len(row) else {}


def worldsteel() -> dict:
    return load_json(config.STATIC_DIR / "worldsteel_2024.json")


def geo_layers() -> dict:
    return load_json(config.STATIC_DIR / "geo_layers.json")


def events() -> pd.DataFrame:
    raw = load_json(config.STATIC_DIR / "events.json")
    df = pd.DataFrame(raw.get("events", []))
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
    return df


def event_categories() -> dict:
    return load_json(config.STATIC_DIR / "events.json").get("_meta", {}).get("categories", {})


def fleet() -> list[dict]:
    return load_json(config.STATIC_DIR / "fleet.json").get("vessels", [])


# ---------------------------------------------------------------------------
# 快取（程式自動抓的）資料
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def _load_long_csv(path: str, mtime: float, key: str, value: str) -> pd.DataFrame:
    """長格式 CSV（date, key, value）轉成寬表：日期為列、每個 key 一欄。"""
    df = pd.read_csv(path, parse_dates=["date"])
    wide = df.pivot_table(index="date", columns=key, values=value, aggfunc="last").sort_index()
    return wide


def prices() -> pd.DataFrame:
    """寬表：index=日期，欄位=config.PRICE_SERIES 的序列 id。"""
    p = config.PRICES_FILE
    if not p.exists():
        return pd.DataFrame()
    return _load_long_csv(str(p), _mtime(p), "series", "value")


def stock_prices() -> pd.DataFrame:
    """寬表：index=日期，欄位=股票代碼（當地幣別收盤價，已調整分割與除息）。"""
    p = config.STOCKS_FILE
    if not p.exists():
        return pd.DataFrame()
    return _load_long_csv(str(p), _mtime(p), "ticker", "close")


def fundamentals() -> dict:
    return load_json(config.FUNDAMENTALS_FILE)


def ais_snapshot() -> dict:
    return load_json(config.AIS_FILE)


def meta() -> dict:
    return load_json(config.META_FILE)


# ---------------------------------------------------------------------------
# 資料版本：所有資料檔的修改時間。給「計算結果快取」當 key 用——
# 任何資料檔一更新，版本就變，舊的快取自動失效。
# ---------------------------------------------------------------------------
def version() -> tuple:
    files = [config.PRICES_FILE, config.STOCKS_FILE, config.FUNDAMENTALS_FILE, config.AIS_FILE, config.META_FILE,
             config.QUARTERLY_FILE, config.WS_MONTHLY_FILE]
    files += sorted(config.STATIC_DIR.glob("*.json"))
    return tuple(_mtime(p) for p in files)


# ---------------------------------------------------------------------------
# 月度與季度資料
# ---------------------------------------------------------------------------
def china_exports() -> dict:
    """中國成品鋼材出口（人工整理自海關數字）。"""
    return load_json(config.STATIC_DIR / "china_steel_exports.json")


def csc_prices() -> dict:
    """中鋼月盤熱軋／冷軋調整幅度（人工整理自媒體報導）。"""
    return load_json(config.STATIC_DIR / "csc_price_changes.json")


@lru_cache(maxsize=4)
def _load_csv(path: str, mtime: float, parse_dates: tuple = ()) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=list(parse_dates))


def quarterly() -> pd.DataFrame:
    """各公司季報重點：ticker, quarter_end, revenue, ebitda, operating_income, net_income（當地幣別）。"""
    p = config.QUARTERLY_FILE
    return _load_csv(str(p), _mtime(p), ("quarter_end",)) if p.exists() else pd.DataFrame()


def worldsteel_monthly() -> pd.DataFrame:
    """worldsteel 每月產量：month, kind(region/country), entity, mt, yoy_pct, ytd_mt, ytd_yoy_pct。"""
    p = config.WS_MONTHLY_FILE
    if not p.exists():
        return pd.DataFrame()
    df = _load_csv(str(p), _mtime(p)).copy()
    df["month"] = df["month"].astype(str)
    return df
