"""台灣鋼材進出口分析：台灣夾在「關稅牆內的高價區」與「中國主導的低價區」之間。

資料：data/cache/taiwan_steel_trade.csv（財政部統計資料庫，scripts/update_data.py 每天更新）
- import / export：依國家的進出口金額（千美元），貨品為碳鋼（鐵或非合金鋼及其製品）、不銹鋼、廢鋼
- index：官方單價指數與數量指數（2021 = 100）；進口為 HS 72 章鋼鐵，出口為 HS 73 章鋼鐵製品

這個模組不碰介面，只回傳 DataFrame 與文字，網頁和未來的 API 都能共用。

--- English ---
Taiwan steel trade analytics: Taiwan sits between the "protected high-price zone" behind tariff
walls and the China-driven low-price zone.

Data: data/cache/taiwan_steel_trade.csv (Ministry of Finance statistics database, refreshed daily)
- import / export: values by partner (USD thousand) for carbon steel, stainless and scrap
- index: official unit-value and quantity indices (2021 = 100); imports cover HS 72 (iron and
  steel), exports HS 73 (articles of iron or steel)

UI-agnostic: returns DataFrames and text so the site and a future API can share it.
"""
from __future__ import annotations

import pandas as pd

from . import config, data

# 產品選項：網頁上的切換 -> 要加總的貨品
PRODUCTS = {"steel": ("carbon", "stainless"), "carbon": ("carbon",), "stainless": ("stainless",)}
EXPORT_PARTNERS = ("us", "eu", "asean", "mx", "cn", "jp")    # 出口看的目的地
IMPORT_PARTNERS = ("cn", "jp", "kr", "asean")                # 進口看的來源（其餘併為「其他」）
NAMES = {code: (zh, en) for code, zh, en in config.TW_PARTNERS.values()}
NAMES["other"] = ("其他", "Other")


def name(code: str, lang: str) -> str:
    """國家代碼 -> 顯示名稱（中文欄位名去掉「(註1)」之類的註記）。"""
    zh, en = NAMES.get(code, (code, code))
    return zh.split("(")[0] if lang == "zh" else en


def monthly(flow: str, product: str = "steel") -> pd.DataFrame:
    """每月金額（百萬美元），欄 = 國家代碼，列 = 月份（Timestamp）。"""
    df = data.taiwan_trade()
    if df.empty:
        return pd.DataFrame()
    df = df[(df["flow"] == flow) & df["product"].isin(PRODUCTS[product])]
    wide = df.pivot_table(index="month", columns="partner", values="value", aggfunc="sum") / 1000
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index().fillna(0.0)


def rolling12(flow: str, product: str = "steel") -> pd.DataFrame:
    """近 12 個月累計（百萬美元）：消除季節性，看得出趨勢。前 11 個月不足 12 個月，不顯示。"""
    m = monthly(flow, product)
    return m.rolling(12).sum().dropna(how="all") if not m.empty else m


def ytd(flow: str, product: str = "steel") -> pd.DataFrame:
    """每年「1 月到最新月份」的累計（百萬美元），讓今年和往年同期比較。列 = 年。"""
    m = monthly(flow, product)
    if m.empty:
        return m
    last = m.index.max().month
    m = m[m.index.month <= last]
    out = m.groupby(m.index.year).sum()
    out.attrs["last_month"] = last
    return out


def import_shares(product: str = "steel") -> pd.DataFrame:
    """進口來源占比（%，近 12 個月累計），欄 = 主要來源＋其他。"""
    r = rolling12("import", product)
    if r.empty or "world" not in r:
        return pd.DataFrame()
    parts = r[[c for c in IMPORT_PARTNERS if c in r]].copy()
    parts["other"] = (r["world"] - parts.sum(axis=1)).clip(lower=0)
    return parts.div(r["world"], axis=0) * 100


def indices() -> pd.DataFrame:
    """單價／數量指數（2021 = 100），欄 = import_uv, import_qty, export_uv, export_qty。"""
    df = data.taiwan_trade()
    if df.empty:
        return pd.DataFrame()
    df = df[df["flow"] == "index"]
    wide = df.pivot_table(index="month", columns="product", values="value")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def _pct(a: float, b: float) -> float | None:
    return (a / b - 1) * 100 if b else None


def observations() -> list[tuple[str, str, str]]:
    """依固定規則產生的觀察（tone, 中文, 英文）。每一條都能在頁面圖表上找到對應數字。"""
    out: list[tuple[str, str, str]] = []
    ex = ytd("export")
    if ex.empty or len(ex) < 4:
        return out
    yr, base = ex.index.max(), ex.index.max() - 3
    lm = ex.attrs["last_month"]
    period_zh, period_en = f"1–{lm} 月", f"Jan–{pd.Timestamp(2000, lm, 1):%b}"

    # 1. 出口目的地：和三年前同期比，變化最大的減少與增加
    chg = {c: ex.loc[yr, c] - ex.loc[base, c] for c in EXPORT_PARTNERS if c in ex}
    worst, best = min(chg, key=chg.get), max(chg, key=chg.get)
    for code, tone in ((worst, "down"), (best, "up")):
        p = _pct(ex.loc[yr, code], ex.loc[base, code])
        if p is None:
            continue
        out.append((tone,
                    f"台灣鋼材出口到{name(code, 'zh')}：{yr} 年 {period_zh} {ex.loc[yr, code]:,.0f} 百萬美元，"
                    f"比 {base} 年同期{'減少' if p < 0 else '增加'} {abs(p):.0f}%",
                    f"Taiwan steel exports to {name(code, 'en')}: USD {ex.loc[yr, code]:,.0f}m in {period_en} {yr}, "
                    f"{p:+.0f}% vs {base}"))

    # 2. 歐盟占出口比重：歐盟鋼鐵配額與 CBAM 的影響
    if "eu" in ex and "world" in ex:
        s_now, s_then = ex.loc[yr, "eu"] / ex.loc[yr, "world"] * 100, ex.loc[base, "eu"] / ex.loc[base, "world"] * 100
        out.append(("warn" if s_now < s_then else "info",
                    f"歐盟占台灣鋼材出口的比重從 {base} 年的 {s_then:.0f}% 變成 {s_now:.0f}%",
                    f"EU share of Taiwan's steel exports: {s_then:.0f}% in {base} → {s_now:.0f}% now"))

    # 3. 進口：中國占比（碳鋼，和中鋼產品直接競爭）
    imp = ytd("import", "carbon")
    if not imp.empty and {"cn", "world"} <= set(imp.columns):
        s_now = imp.loc[yr, "cn"] / imp.loc[yr, "world"] * 100
        s_prev = imp.loc[yr - 1, "cn"] / imp.loc[yr - 1, "world"] * 100
        out.append(("info",
                    f"台灣進口碳鋼有 {s_now:.0f}% 來自中國（去年同期 {s_prev:.0f}%）",
                    f"{s_now:.0f}% of Taiwan's carbon-steel imports come from China (same period last year {s_prev:.0f}%)"))

    # 3b. 不銹鋼：印尼占比（印尼不銹鋼產能多為中資鎳鐵一體化廠，例如青山）
    ss = ytd("import", "stainless")
    if not ss.empty and {"id", "world"} <= set(ss.columns) and ss.loc[yr, "world"]:
        s_id = ss.loc[yr, "id"] / ss.loc[yr, "world"] * 100
        out.append(("info",
                    f"台灣進口不銹鋼有 {s_id:.0f}% 來自印尼；印尼不銹鋼產能多為中資鎳鐵一體化廠（如青山）",
                    f"{s_id:.0f}% of Taiwan's stainless imports come from Indonesia, where capacity is largely "
                    f"Chinese-owned integrated nickel-to-stainless plants (e.g. Tsingshan)"))

    # 4. 指數：進口單價與出口數量
    ix = indices()
    if not ix.empty:
        for col, zh, en in (("import_uv", "進口鋼鐵單價指數", "Import steel unit-value index"),
                            ("export_qty", "出口鋼鐵製品數量指數", "Export steel-products volume index")):
            s = ix[col].dropna() if col in ix else pd.Series(dtype=float)
            if len(s) < 13:
                continue
            last, prev = s.iloc[-1], s.iloc[-13]
            p = _pct(last, prev)
            low = s.iloc[-120:].min() == last
            extra_zh, extra_en = ("，近十年最低" if low else ""), (", a 10-year low" if low else "")
            out.append(("down" if p < 0 else "up",
                        f"{zh} {last:.0f}（2021 = 100，{s.index[-1]:%Y-%m}），年{'減' if p < 0 else '增'} {abs(p):.0f}%{extra_zh}",
                        f"{en} {last:.0f} (2021 = 100, {s.index[-1]:%Y-%m}), {p:+.0f}% y/y{extra_en}"))
    return out
