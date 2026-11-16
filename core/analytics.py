"""分析模組：利差、分位數、同業評分、情境模型。

全部是對 pandas 物件運算的「純函式」：不讀寫檔案、不碰介面。
好測試，之後也可以直接給 API 使用。

--- English ---
Analytics: spreads, percentiles, peer scoring, scenario model.

Pure functions over pandas objects: no file I/O, no UI. Easy to test and to
reuse from an API later.
"""
from __future__ import annotations

import math

import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def last_valid(s: pd.Series) -> tuple[pd.Timestamp | None, float | None]:
    """最後一筆有值的（日期, 數值）。"""
    s = s.dropna()
    if s.empty:
        return None, None
    return s.index[-1], float(s.iloc[-1])


def pct_change_over(s: pd.Series, days: int) -> float | None:
    """最新值相對於 `days` 個日曆天前的漲跌幅（%）。"""
    s = s.dropna()
    if len(s) < 2:
        return None
    end_date, end_val = s.index[-1], s.iloc[-1]
    past = s[s.index <= end_date - pd.Timedelta(days=days)]
    if past.empty or past.iloc[-1] == 0:
        return None
    return float(end_val / past.iloc[-1] - 1) * 100


def percentile_of_last(s: pd.Series, lookback_years: int | None = None) -> float | None:
    """最新值在自己歷史中的位置（0 = 區間最低，100 = 區間最高）。"""
    s = s.dropna()
    if lookback_years:
        s = s[s.index >= s.index[-1] - pd.DateOffset(years=lookback_years)]
    if len(s) < 20:
        return None
    return float((s < s.iloc[-1]).mean() * 100)


def series_summary(s: pd.Series) -> dict:
    """指標卡需要的所有數字：最新值、週／月／年漲跌、10 年分位。"""
    d, v = last_valid(s)
    return {
        "date": d, "value": v,
        "chg_1w": pct_change_over(s, 7),
        "chg_1m": pct_change_over(s, 30),
        "chg_1y": pct_change_over(s, 365),
        "pctl_10y": percentile_of_last(s, 10),
    }


# ---------------------------------------------------------------------------
# 鋼鐵專用指標
# ---------------------------------------------------------------------------
def china_bf_spread(px: pd.DataFrame,
                    ore_ratio: float = config.SPREAD_ORE_RATIO,
                    coke_ratio: float = config.SPREAD_COKE_RATIO) -> pd.Series:
    """期貨推算的高爐利潤代理（人民幣/噸）：

        熱軋 - 1.6 × 鐵礦 - 0.5 × 焦炭

    沒有扣能源、人工、合金等其他成本（每噸約 600–900 元人民幣），
    所以數字本身不是獲利；重點是它的「趨勢與分位」。
    """
    need = {"cn_hrc", "cn_ore", "cn_coke"}
    if not need.issubset(px.columns):
        return pd.Series(dtype=float)
    df = px[list(need)].dropna()  # 三個價格同一天都有值才計算
    return (df["cn_hrc"] - ore_ratio * df["cn_ore"] - coke_ratio * df["cn_coke"]).rename("spread")


def hrc_usd_per_tonne(px: pd.DataFrame) -> pd.DataFrame:
    """把中國與美國熱軋換到同一基準（美元／公噸）。

    兩者價差大致等於：美國關稅保護 + 運費 + 美國本土供給溢價。
    """
    out = pd.DataFrame(index=px.index)
    if {"cn_hrc", "fx_cny"}.issubset(px.columns):
        fx = px["fx_cny"].ffill()  # 匯率遇到假日缺值時沿用前一天
        out["China"] = px["cn_hrc"] / fx
    if "us_hrc" in px.columns:
        out["US"] = px["us_hrc"] / config.SHORT_TON_IN_TONNES  # 短噸換公噸
    return out.dropna(how="all")


def regime_label(spread_pctl: float | None) -> str:
    """把利潤分位轉成粗略的市場狀態（回傳翻譯 key，由介面翻譯）。"""
    if spread_pctl is None or math.isnan(spread_pctl):
        return "regime_unknown"
    if spread_pctl < 20:
        return "regime_squeezed"
    if spread_pctl < 45:
        return "regime_weak"
    if spread_pctl < 70:
        return "regime_normal"
    return "regime_strong"


# ---------------------------------------------------------------------------
# 公司／同業分析
# ---------------------------------------------------------------------------
def total_return(s: pd.Series, days: int) -> float | None:
    return pct_change_over(s, days)


def peer_table(companies: pd.DataFrame, fundamentals: dict, stocks: pd.DataFrame) -> pd.DataFrame:
    """每家公司一列、可互相比較的指標（需要時換算成美元）。"""
    fx = fundamentals.get("_fx_to_usd", {})
    rows = []
    for _, c in companies.iterrows():
        t = c.get("ticker")
        f = fundamentals.get(t, {}) if isinstance(t, str) else {}
        # 報價幣別（市值用）和財報幣別（EBITDA、營收用）可能不同，例如 ADR
        quote_ccy = f.get("currency") or "USD"
        fin_ccy = f.get("financialCurrency") or quote_ccy
        q_fx = fx.get(quote_ccy)
        f_fx = fx.get(fin_ccy)

        mcap_usd = f["marketCap"] / q_fx if f.get("marketCap") and q_fx else None
        ebitda_usd = f["ebitda"] / f_fx if f.get("ebitda") and f_fx else None
        rev_usd = f["totalRevenue"] / f_fx if f.get("totalRevenue") and f_fx else None
        out_mt = c.get("output_2024_mt")
        out_mt = None if out_mt is None or (isinstance(out_mt, float) and math.isnan(out_mt)) else out_mt

        s = stocks[t] if isinstance(t, str) and t in stocks.columns else pd.Series(dtype=float)
        rows.append({
            "id": c["id"], "ticker": t, "role": c.get("role"),
            "output_mt": out_mt,
            "mcap_usd_bn": mcap_usd / 1e9 if mcap_usd else None,
            "revenue_usd_bn": rev_usd / 1e9 if rev_usd else None,
            # 集團 EBITDA ÷ 粗鋼噸數：粗估，多角化集團和礦商會偏高
            "ebitda_per_t": (ebitda_usd / (out_mt * 1e6)) if ebitda_usd and out_mt else None,
            "ebitda_margin": _pct(f.get("ebitdaMargins")),
            "net_margin": _pct(f.get("profitMargins")),
            "roe": _pct(f.get("returnOnEquity")),
            "pb": f.get("priceToBook"),
            "pe": f.get("trailingPE"),
            # yfinance 的負債權益比是百分比（45.2 代表 0.452 倍），換成倍數
            "debt_to_equity": f["debtToEquity"] / 100 if f.get("debtToEquity") is not None else None,
            "current_ratio": f.get("currentRatio"),
            "div_yield": _div_yield(f.get("dividendYield")),
            "ret_1y": total_return(s, 365),
            "ret_3y": total_return(s, 365 * 3),
        })
    df = pd.DataFrame(rows).set_index("id")
    # 鋼廠和鋼廠比、礦商和礦商比：
    # 混在一起的話，利潤率 50% 的礦商會讓每家鋼廠都顯得很差。
    return pd.concat([_add_scores(g.copy()) for _, g in df.groupby("role", dropna=False)]).reindex(df.index)


def _pct(x):
    """小數轉百分比。Yahoo 在沒資料時會給剛好 0，所以 0 視為缺值。"""
    if not isinstance(x, (int, float)) or math.isnan(x) or x == 0:
        return None
    return x * 100


def _div_yield(x):
    """yfinance（0.2.54 以後）的殖利率已經是百分比（0.82 代表 0.82%），不用再乘 100。"""
    if not isinstance(x, (int, float)) or math.isnan(x):
        return None
    return float(x)


def _rank(s: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """同業間的百分位排名 0–100（缺值維持缺值）。"""
    return s.astype(float).rank(pct=True, ascending=higher_is_better) * 100


def _add_scores(df: pd.DataFrame) -> pd.DataFrame:
    """三個同業相對分數（0–100）。是相對排名不是絕對分數：80 = 勝過 80% 的同業。

    - 體質 health：  獲利能力＋財務結構（EBITDA 利潤率、ROE、低槓桿、流動性）
    - 價值 value：   股價淨值比有多便宜（鋼鐵是景氣循環股，P/B 比 P/E 穩定）
    - 動能 momentum：一年股價報酬
    """
    parts = pd.DataFrame({
        "m": _rank(df["ebitda_margin"]),
        "roe": _rank(df["roe"]),
        "lev": _rank(df["debt_to_equity"], higher_is_better=False),  # 負債越低越好
        "liq": _rank(df["current_ratio"]),
    })
    # 四項中至少要有兩項有資料，才給體質分數，避免單一指標決定一切
    df["score_health"] = parts.mean(axis=1, skipna=True).where(parts.notna().sum(axis=1) >= 2)
    df["score_value"] = _rank(df["pb"].where(df["pb"] > 0), higher_is_better=False)  # 負淨值不列入
    df["score_momentum"] = _rank(df["ret_1y"])
    return df


def rebased(stocks: pd.DataFrame, tickers: list[str], start: pd.Timestamp) -> pd.DataFrame:
    """把股價在 `start` 那天都換成 100，不同幣別的股票才能放在一起比較。"""
    cols = [t for t in tickers if t in stocks.columns]
    df = stocks.loc[stocks.index >= start, cols].ffill().dropna(how="all")
    if df.empty:
        return df
    first = df.bfill().iloc[0]  # 每檔股票區間內第一個有值的價格
    return df.divide(first) * 100


# ---------------------------------------------------------------------------
# 情境模型
# ---------------------------------------------------------------------------
def margin_per_tonne(hrc: float, ore: float, coke: float, other_cost: float,
                     ore_ratio: float = config.SPREAD_ORE_RATIO,
                     coke_ratio: float = config.SPREAD_COKE_RATIO) -> float:
    """簡化的高爐每噸利潤（所有輸入需同一幣別）。"""
    return hrc - ore_ratio * ore - coke_ratio * coke - other_cost


def scenario(base: dict, shocks: dict, output_mt: float, other_cost: float) -> dict:
    """對基準價格套用 % 變動，回傳每噸利潤與年度影響。

    base   = {"hrc": .., "ore": .., "coke": ..}（美元/噸）
    shocks = {"hrc": +5, "ore": -10, "coke": 0}（百分比）
    年度影響假設全部粗鋼都以熱軋價格出售：對扁鋼為主的鋼廠是上限估計，
    對長鋼廠會高估。
    """
    new = {k: base[k] * (1 + shocks.get(k, 0) / 100) for k in base}
    m0 = margin_per_tonne(base["hrc"], base["ore"], base["coke"], other_cost)
    m1 = margin_per_tonne(new["hrc"], new["ore"], new["coke"], other_cost)
    return {
        "new_prices": new,
        "margin_base": m0, "margin_new": m1, "margin_delta": m1 - m0,
        "annual_delta_usd_m": (m1 - m0) * output_mt,  # 百萬噸 × 美元/噸 = 百萬美元
        # 敏感度：每項價格變動 1%，年度利潤變動幾百萬美元
        "sens_per_1pct": {
            "hrc": base["hrc"] * 0.01 * output_mt,
            "ore": -config.SPREAD_ORE_RATIO * base["ore"] * 0.01 * output_mt,
            "coke": -config.SPREAD_COKE_RATIO * base["coke"] * 0.01 * output_mt,
        },
    }


def downsample(obj, years: int):
    """依時間長度降低資料密度，讓圖表傳輸量變小、畫面看起來一樣。

    1 年：每日（約 250 點）；3 年：每 3 天；5 年以上：每週。
    取每段的最後一個值（等同收盤價概念）。
    """
    if years <= 1 or obj is None or len(obj) == 0:
        return obj
    rule = "3D" if years <= 3 else "W-FRI"
    return obj.resample(rule).last().dropna(how="all")


def safe_round(x, nd=1):
    """四捨五入；None、NaN、無限大都回傳 None。"""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


def fmt(x, nd=1, suffix="", sign=False) -> str:
    """數字格式化給畫面顯示；缺值顯示「—」。sign=True 時正數加「+」。"""
    v = safe_round(x, nd)
    if v is None:
        return "—"
    s = f"{v:+,.{nd}f}" if sign else f"{v:,.{nd}f}"
    return s + suffix
