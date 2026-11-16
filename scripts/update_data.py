"""更新所有市場資料快取。

本機執行：  python scripts/update_data.py
自動排程：  .github/workflows/update-data.yml（每個平日，免費的 GitHub Actions）

每個區塊互相獨立：某個來源失敗時，其他來源照常更新，失敗來源保留舊資料。

--- English ---
Refresh all cached market data.

Run locally:   python scripts/update_data.py
Scheduled:     .github/workflows/update-data.yml (weekdays, free GitHub Actions)

Each block is independent: if one source fails, the others still update and the
failed source keeps its previous data.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 讓腳本可以 import core

from core import config, data, fetch  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("update")


def _now() -> str:
    """現在的 UTC 時間（ISO 格式字串）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_prices() -> int:
    """商品期貨、運價代理、匯率 -> data/cache/prices.csv（長格式）。"""
    frames = []
    yf_specs = {k: v for k, v in config.PRICE_SERIES.items() if v["source"] == "yfinance"}
    cn_specs = {k: v for k, v in config.PRICE_SERIES.items() if v["source"] == "sina"}

    for sid, spec in cn_specs.items():
        try:
            s = fetch.fetch_cn_future(spec["symbol"], config.HISTORY_START)
            frames.append(pd.DataFrame({"date": s.index, "series": sid, "value": s.values}))
            log.info("sina    %-14s %5d rows, last %s", sid, len(s), s.index[-1].date())
        except Exception as e:  # noqa: BLE001
            log.error("sina %s failed: %s", sid, e)

    try:
        wide = fetch.fetch_yf_history([v["symbol"] for v in yf_specs.values()], start=config.HISTORY_START)
        for sid, spec in yf_specs.items():
            s = wide[spec["symbol"]].dropna()
            if s.empty:
                log.warning("yfinance %s returned no data", sid)
                continue
            frames.append(pd.DataFrame({"date": s.index, "series": sid, "value": s.values}))
            log.info("yfinance %-14s %5d rows, last %s", sid, len(s), s.index[-1].date())
    except Exception as e:  # noqa: BLE001
        log.error("yfinance batch failed: %s", e)

    if not frames:
        return 0
    new = pd.concat(frames, ignore_index=True)
    new["date"] = pd.to_datetime(new["date"]).dt.tz_localize(None).dt.normalize()

    # 和舊快取合併：失敗的來源保留原本的歷史資料
    if config.PRICES_FILE.exists():
        old = pd.read_csv(config.PRICES_FILE, parse_dates=["date"])
        old = old[~old["series"].isin(new["series"].unique())]
        new = pd.concat([old, new], ignore_index=True)
    new = new.drop_duplicates(["date", "series"], keep="last").sort_values(["series", "date"])
    new.to_csv(config.PRICES_FILE, index=False, float_format="%.4f")
    return new["series"].nunique()


def update_stocks() -> int:
    """所有上市公司的股價 -> data/cache/stock_prices.csv。"""
    tickers = sorted(t for t in data.companies()["ticker"].dropna().unique())
    try:
        wide = fetch.fetch_yf_history(tickers, period=config.STOCK_HISTORY_PERIOD)
    except Exception as e:  # noqa: BLE001
        log.error("stock download failed: %s", e)
        return 0
    wide.index = pd.to_datetime(wide.index).tz_localize(None).normalize()
    long = wide.reset_index(names="date").melt(id_vars="date", var_name="ticker", value_name="close").dropna()
    missing = sorted(set(tickers) - set(long["ticker"]))
    if missing:
        log.warning("no price data for: %s", ", ".join(missing))
    long.to_csv(config.STOCKS_FILE, index=False, float_format="%.4f")
    return long["ticker"].nunique()


def update_fundamentals() -> int:
    """每檔股票的估值與財務快照 -> data/cache/fundamentals.json。"""
    tickers = sorted(t for t in data.companies()["ticker"].dropna().unique())
    out: dict = {}
    for t in tickers:
        try:
            out[t] = fetch.fetch_yf_fundamentals(t)
            log.info("fundamentals %-12s mcap=%s", t, out[t].get("marketCap"))
        except Exception as e:  # noqa: BLE001
            log.warning("fundamentals %s failed: %s", t, e)
    ccys = {v.get("currency") for v in out.values()} | {v.get("financialCurrency") for v in out.values()}
    out["_fx_to_usd"] = fetch.fetch_fx_to_usd({c for c in ccys if c})
    out["_updated"] = _now()
    config.FUNDAMENTALS_FILE.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(out) - 2


def update_quarterly() -> int:
    """各上市公司近幾季損益重點 -> data/cache/quarterly.csv（和舊資料合併，季數會越累積越多）。"""
    tickers = sorted(t for t in data.companies()["ticker"].dropna().unique())
    frames = []
    for t in tickers:
        try:
            df = fetch.fetch_yf_quarterly(t)
            if not df.empty:
                frames.append(df)
        except Exception as e:  # noqa: BLE001
            log.warning("quarterly %s failed: %s", t, e)
    if not frames:
        return 0
    new = pd.concat(frames, ignore_index=True)
    if config.QUARTERLY_FILE.exists():
        old = pd.read_csv(config.QUARTERLY_FILE, parse_dates=["quarter_end"])
        new = pd.concat([old, new], ignore_index=True)
    # 同一季以最新抓到的為準（公司可能修正數字），全空的列丟掉
    new = new.dropna(subset=["revenue", "ebitda", "operating_income", "net_income"], how="all")
    new = new.drop_duplicates(["ticker", "quarter_end"], keep="last").sort_values(["ticker", "quarter_end"])
    new.to_csv(config.QUARTERLY_FILE, index=False)
    return new["ticker"].nunique()


def update_worldsteel_monthly() -> int:
    """worldsteel 每月產量新聞稿 -> data/cache/worldsteel_monthly.csv（只抓還沒有的月份）。"""
    have = set()
    if config.WS_MONTHLY_FILE.exists():
        old = pd.read_csv(config.WS_MONTHLY_FILE, dtype={"month": str})
        have = set(old["month"])
    else:
        old = pd.DataFrame()
    urls = fetch.list_worldsteel_monthly(pages=1)
    # 補回最近 24 個月中列表頁沒列到的月份（用網址格式推測）
    for m in pd.period_range(end=pd.Timestamp.today().to_period("M") - 1, periods=24, freq="M"):
        urls.setdefault(str(m), fetch.guess_worldsteel_url(str(m)))
    frames = []
    for month, url in sorted(urls.items()):
        if month in have:
            continue
        try:
            frames.append(fetch.fetch_worldsteel_month(url, month))
            log.info("worldsteel %s ok", month)
        except Exception as e:  # noqa: BLE001 - 還沒發布或網址不同就跳過
            log.info("worldsteel %s skipped (%s)", month, str(e)[:80])
    if not frames:
        return len(have)
    new = pd.concat([old] + frames, ignore_index=True).drop_duplicates(["month", "kind", "entity"], keep="last")
    new.sort_values(["month", "kind", "entity"]).to_csv(config.WS_MONTHLY_FILE, index=False)
    return new["month"].nunique()


def update_csc_prices() -> int:
    """中鋼官網盤價新聞稿 -> data/cache/csc_official.json（依月份合併，官網列表只保留最近幾則，所以要累積）。"""
    try:
        new = fetch.fetch_csc_price_releases()
    except Exception as e:  # noqa: BLE001
        log.error("csc prices failed: %s", e)
        return 0
    old = json.loads(config.CSC_OFFICIAL_FILE.read_text(encoding="utf-8")) if config.CSC_OFFICIAL_FILE.exists() else {}
    for r in new:
        old[r["month"]] = r
        log.info("csc %s: HRC %s CRC %s", r["month"], r["hrc"], r["crc"])
    config.CSC_OFFICIAL_FILE.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return len(old)


def main(which: list[str]) -> None:
    """執行指定的更新工作（沒指定就全部跑），並記錄成功的時間。"""
    meta = data.meta() or {}
    jobs = {"prices": update_prices, "stocks": update_stocks, "fundamentals": update_fundamentals,
            "quarterly": update_quarterly, "worldsteel": update_worldsteel_monthly, "csc": update_csc_prices}
    for name in which or jobs:
        n = jobs[name]()
        log.info("== %s: %d items", name, n)
        if n:
            meta[name] = _now()
    config.META_FILE.write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    # 可加參數只跑部分工作，例如 `python scripts/update_data.py prices`
    main(sys.argv[1:])
