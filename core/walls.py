"""貿易壁壘：各國對鋼鐵發起的反傾銷（AD）與反補貼（CVD）調查。

資料：WTO 貿易救濟資料庫（逐案，各會員每半年申報），只取 HS 第 XV 類裡的鋼鐵產品。
這裡的函式和介面無關，只回傳 DataFrame 或文字；頁面在 pages/walls.py。

計算單位：一件「調查」= 一個申報國 × 一個被調查國 × 一項產品。
南部非洲關稅同盟、海灣合作理事會、歐亞經濟聯盟是以聯盟名義立案、再由每個成員國各報一次，
所以先合併成一個申報者再去重，否則同一件案子會被算 5–6 次。

--- English ---
Trade walls: anti-dumping (AD) and countervailing (CVD) investigations on steel.

Data: WTO Trade Remedies Data Portal (case level, reported by members every six months),
keeping steel products within HS Section XV. Functions here are UI-agnostic and return
DataFrames or text; the page lives in pages/walls.py.

Unit: one investigation = one reporting member × one exporting member × one product.
SACU, the GCC and the Eurasian Economic Union open cases as a bloc and each member then
reports them, so members are merged into one reporter and de-duplicated; otherwise a single
case would count five or six times.
"""
from __future__ import annotations

import re

import pandas as pd

from . import data

# 非鋼鐵的卑金屬（鋁、銅、鎳…）與鐵合金；但「鍍鋁鋅鋼」「鍍錫鋼」「含鎳不銹鋼」仍算鋼鐵
_NON_FERROUS = re.compile(
    r"alumin|copper|brass|bronze|nickel|titan|magnes|tungst|molyb|silicon metal|\blead\b|cobalt|"
    r"zinc|unwrought|\btin\b|mangan|vanad|antimony|tantal|zircon|bismuth|cadmium|germanium|indium|rare earth",
    re.I)
_STEEL = re.compile(r"steel|\biron\b|stainless|tinplate|rebar|galvan|tubular|wire rod", re.I)
_FERRO_ALLOY = re.compile(r"ferro|silico-?\s?man|alloys of iron", re.I)

# 以聯盟名義立案的成員 -> 聯盟
_BLOCS = {
    **dict.fromkeys(["South Africa", "Botswana", "Eswatini", "Lesotho", "Namibia"], "SACU"),
    **dict.fromkeys(["Bahrain, Kingdom of", "Kuwait, the State of", "Oman", "Qatar",
                     "Saudi Arabia, Kingdom of", "United Arab Emirates"], "GCC"),
    **dict.fromkeys(["Armenia", "Belarus", "Kazakhstan", "Kyrgyz Republic", "Russian Federation"], "EAEU"),
}

NAMES = {  # WTO 名稱 -> (中文, 英文短名)
    "China": ("中國", "China"), "Chinese Taipei": ("台灣", "Taiwan"), "Hong Kong, China": ("香港", "Hong Kong"),
    "Korea, Republic of": ("韓國", "Korea"), "Japan": ("日本", "Japan"), "Viet Nam": ("越南", "Vietnam"),
    "India": ("印度", "India"), "Indonesia": ("印尼", "Indonesia"), "Malaysia": ("馬來西亞", "Malaysia"),
    "Thailand": ("泰國", "Thailand"), "Philippines": ("菲律賓", "Philippines"), "Singapore": ("新加坡", "Singapore"),
    "Pakistan": ("巴基斯坦", "Pakistan"), "Sri Lanka": ("斯里蘭卡", "Sri Lanka"), "Nepal": ("尼泊爾", "Nepal"),
    "Australia": ("澳洲", "Australia"), "New Zealand": ("紐西蘭", "New Zealand"),
    "United States": ("美國", "US"), "Canada": ("加拿大", "Canada"), "Mexico": ("墨西哥", "Mexico"),
    "Brazil": ("巴西", "Brazil"), "Argentina": ("阿根廷", "Argentina"), "Chile": ("智利", "Chile"),
    "Colombia": ("哥倫比亞", "Colombia"), "Peru": ("秘魯", "Peru"), "Ecuador": ("厄瓜多", "Ecuador"),
    "Paraguay": ("巴拉圭", "Paraguay"), "Venezuela, Bolivarian Republic of": ("委內瑞拉", "Venezuela"),
    "Costa Rica": ("哥斯大黎加", "Costa Rica"), "Dominican Republic": ("多明尼加", "Dominican Rep."),
    "Guatemala": ("瓜地馬拉", "Guatemala"), "Trinidad and Tobago": ("千里達及托巴哥", "Trinidad & Tobago"),
    "European Union": ("歐盟", "EU"), "United Kingdom": ("英國", "UK"), "Ukraine": ("烏克蘭", "Ukraine"),
    "Türkiye": ("土耳其", "Türkiye"), "Russian Federation": ("俄羅斯", "Russia"), "Belarus": ("白俄羅斯", "Belarus"),
    "Kazakhstan": ("哈薩克", "Kazakhstan"), "Uzbekistan": ("烏茲別克", "Uzbekistan"), "Georgia": ("喬治亞", "Georgia"),
    "Azerbaijan": ("亞塞拜然", "Azerbaijan"), "Moldova, Republic of": ("摩爾多瓦", "Moldova"),
    "Serbia": ("塞爾維亞", "Serbia"), "Switzerland": ("瑞士", "Switzerland"), "Israel": ("以色列", "Israel"),
    "Iran": ("伊朗", "Iran"), "Jordan": ("約旦", "Jordan"), "Egypt": ("埃及", "Egypt"), "Morocco": ("摩洛哥", "Morocco"),
    "Tunisia": ("突尼西亞", "Tunisia"), "Algeria": ("阿爾及利亞", "Algeria"), "Ghana": ("迦納", "Ghana"),
    "Mozambique": ("莫三比克", "Mozambique"), "South Africa": ("南非", "South Africa"),
    "Saudi Arabia, Kingdom of": ("沙烏地阿拉伯", "Saudi Arabia"), "United Arab Emirates": ("阿聯", "UAE"),
    "Oman": ("阿曼", "Oman"), "Qatar": ("卡達", "Qatar"),
    "Germany": ("德國", "Germany"), "France": ("法國", "France"), "Italy": ("義大利", "Italy"), "Spain": ("西班牙", "Spain"),
    "Netherlands": ("荷蘭", "Netherlands"), "Belgium": ("比利時", "Belgium"), "Austria": ("奧地利", "Austria"),
    "Poland": ("波蘭", "Poland"), "Romania": ("羅馬尼亞", "Romania"), "Sweden": ("瑞典", "Sweden"),
    "Finland": ("芬蘭", "Finland"), "Czech Republic": ("捷克", "Czechia"), "Slovak Republic": ("斯洛伐克", "Slovakia"),
    "SACU": ("南部非洲關稅同盟", "SACU"), "GCC": ("海灣合作理事會", "GCC"), "EAEU": ("歐亞經濟聯盟", "EAEU"),
}

TARGETS = {"cn": "China", "tw": "Chinese Taipei"}  # 頁面上可以切換的「被調查國」


def name(wto_name: str, lang: str) -> str:
    """WTO 國名 -> 介面顯示名稱（沒有對照時用原文）。"""
    zh, en = NAMES.get(wto_name, (wto_name, wto_name))
    return zh if lang == "zh" else en


def steel_cases() -> pd.DataFrame:
    """鋼鐵類調查（AD + CVD），聯盟成員已合併去重。多一欄 year。"""
    df = data.trade_remedies()
    if df.empty:
        return df
    p = df["product"].fillna("")
    steel = ~p.str.contains(_FERRO_ALLOY) & (p.str.contains(_STEEL) | ~p.str.contains(_NON_FERROUS))
    df = df[steel].copy()
    df["reporter"] = df["reporter"].replace(_BLOCS)
    df = df.drop_duplicates(["type", "reporter", "exporter", "initiated", "product"])
    df["year"] = df["initiated"].dt.year
    return df.sort_values("initiated")


def latest_date() -> pd.Timestamp | None:
    """資料涵蓋到哪一天（最新一件立案日期）。"""
    df = steel_cases()
    return df["initiated"].max() if len(df) else None


def by_year(start: int = 2000) -> pd.DataFrame:
    """每年新立案件數：index = 年，欄位 China（對中國）、other（對其他國家）。"""
    df = steel_cases()
    if df.empty:
        return df
    df = df[df["year"] >= start]
    out = pd.DataFrame({
        "China": df[df["exporter"] == "China"].groupby("year").size(),
        "other": df[df["exporter"] != "China"].groupby("year").size(),
    }).fillna(0).astype(int)
    return out.reindex(range(start, int(df["year"].max()) + 1), fill_value=0)


def reporters_against(target: str, since: int) -> pd.Series:
    """某年以來，哪些國家對 target（WTO 國名）的鋼鐵立案最多（件數，由多到少）。"""
    df = steel_cases()
    if df.empty:
        return pd.Series(dtype=int)
    df = df[(df["exporter"] == target) & (df["year"] >= since)]
    return df.groupby("reporter").size().sort_values(ascending=False)


def recent(target: str | None, n: int = 15) -> pd.DataFrame:
    """最新的 n 件（target = None 代表全部被調查國）。"""
    df = steel_cases()
    if df.empty:
        return df
    if target:
        df = df[df["exporter"] == target]
    return df.sort_values("initiated", ascending=False).head(n)


def _half(ts: pd.Timestamp) -> str:
    return f"{ts.year} H{1 if ts.month <= 6 else 2}"


def observations() -> list[tuple[str, str, str]]:
    """依固定規則產生的觀察：(語氣, 中文, 英文)。語氣 = up / down / warn / info。"""
    df = steel_cases()
    if df.empty:
        return []
    out = []
    last = df["initiated"].max()
    yr = by_year(2000)
    full = [y for y in yr.index if y < last.year or last.month == 12]  # 只比較完整年度
    if full:
        y = full[-1]
        tot, cn = int(yr.loc[y].sum()), int(yr.loc[y, "China"])
        avg = yr.loc[[v for v in yr.index if y - 10 <= v < y]].sum(axis=1).mean()
        tone = "warn" if tot > avg * 1.3 else "info"
        out.append((tone,
                    f"{y} 年全球新立案的鋼鐵反傾銷／反補貼調查 {tot} 件，其中 {cn} 件針對中國（{cn / tot:.0%}）；過去 10 年平均每年 {avg:.0f} 件",
                    f"{tot} new steel AD/CVD investigations worldwide in {y}, {cn} of them against China ({cn / tot:.0%}); "
                    f"10-year average {avg:.0f} a year"))
    # 今年上半年（或最新半年）的件數 vs 去年同期
    h = df[(df["initiated"].dt.year == last.year) & (df["initiated"].dt.month <= last.month)]
    h0 = df[(df["initiated"].dt.year == last.year - 1) & (df["initiated"].dt.month <= last.month)]
    if len(h0):
        chg = (len(h) / len(h0) - 1) * 100
        cn_h = int((h["exporter"] == "China").sum())
        out.append(("up" if chg > 0 else "down",
                    f"{last.year} 年 1–{last.month} 月全球新立案的鋼鐵反傾銷／反補貼調查 {len(h)} 件（去年同期 {len(h0)} 件），對中國 {cn_h} 件",
                    f"{len(h)} new steel AD/CVD investigations worldwide in Jan–{last:%b} {last.year} "
                    f"(same period last year: {len(h0)}), {cn_h} against China"))
    # 築牆最積極的國家
    r = reporters_against("China", last.year - 1)
    if len(r):
        top = r.head(3)
        out.append(("info",
                    f"{last.year - 1} 年以來對中國鋼鐵立案最多：" + "、".join(f"{name(k, 'zh')} {v} 件" for k, v in top.items()),
                    f"Most cases against Chinese steel since {last.year - 1}: "
                    + ", ".join(f"{name(k, 'en')} {v}" for k, v in top.items())))
    # 台灣也被波及
    tw = df[(df["exporter"] == "Chinese Taipei") & (df["year"] >= last.year - 1)]
    if len(tw):
        who = tw.groupby("reporter").size().sort_values(ascending=False)
        out.append(("warn",
                    f"台灣鋼材也被波及：{last.year - 1} 年以來有 {len(tw)} 件調查把台灣列為對象（"
                    + "、".join(f"{name(k, 'zh')} {v}" for k, v in who.head(4).items()) + "）",
                    f"Taiwan is caught too: {len(tw)} cases since {last.year - 1} name Taiwan ("
                    + ", ".join(f"{name(k, 'en')} {v}" for k, v in who.head(4).items()) + ")"))
    out.append(("info",
                f"資料涵蓋到 {last:%Y-%m-%d}（WTO 會員每半年申報一次，所以最新案件會晚約半年才出現）",
                f"Data run to {last:%Y-%m-%d} (WTO members report every six months, so new cases appear about half a year late)"))
    return out
