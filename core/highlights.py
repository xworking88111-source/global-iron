"""「本週重點」：用規則從資料自動產生的雙語摘要。

目標是打開首頁 10 秒內知道「最近發生什麼事」。每條重點都是：
    (tone, zh 文字, en 文字)
tone = "up" / "down" / "warn" / "info"，介面依此顯示箭頭或圖示（不只靠顏色）。

規則刻意保持簡單、可解釋：每一條都能回溯到畫面上的某張圖或某個數字。

--- English ---
"This week at a glance": a bilingual summary generated from the data by rules.

Goal: know what happened lately within 10 seconds of opening the home page.
Each item is (tone, zh text, en text); tone = "up" / "down" / "warn" / "info",
shown as an arrow or icon (never colour alone).

Rules are deliberately simple and explainable: every bullet traces back to a
chart or number on the site.
"""
from __future__ import annotations

import pandas as pd

from . import analytics as an
from . import data


def _fmt_pct(x: float) -> str:
    return f"{x:+.1f}%"


def _zh(x: float, kind: str = "年") -> str:
    """中文漲跌寫法：+3.2 -> 「年增 3.2%」，-2.3 -> 「年減 2.3%」（比「年增 -2.3%」好讀）。"""
    return f"{kind}{'增' if x >= 0 else '減'} {abs(x):.1f}%"


def build(max_items: int = 9) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    px = data.prices()

    # 1. 價格：週漲跌幅最大的兩個品項（只挑變動超過 1% 的，避免雜訊）
    watch = {"cn_hrc": ("中國熱軋", "China HRC"), "us_hrc": ("美國熱軋", "US HRC"),
             "ore_62": ("鐵礦 62%", "Iron ore 62%"), "cn_coke": ("焦炭", "Coke"),
             "dry_bulk": ("乾散貨運價", "Dry-bulk freight")}
    moves = []
    for sid, (zh, en) in watch.items():
        if sid in px:
            ch = an.pct_change_over(px[sid], 7)
            if ch is not None and abs(ch) >= 1:
                moves.append((abs(ch), ch, zh, en))
    for _, ch, zh, en in sorted(moves, reverse=True)[:2]:
        items.append(("up" if ch > 0 else "down", f"{zh}本週{'上漲' if ch > 0 else '下跌'} {abs(ch):.1f}%",
                      f"{en} {'up' if ch > 0 else 'down'} {abs(ch):.1f}% this week"))

    # 2. 景氣位置：高爐利潤代理的 10 年分位
    sp = an.china_bf_spread(px)
    pctl = an.percentile_of_last(sp, 10)
    if pctl is not None:
        if pctl <= 10:
            items.append(("warn", f"中國高爐利潤代理在 10 年最低的 {max(pctl, 1):.0f}% 區間：鋼廠普遍虧損邊緣，留意減產與出口壓力",
                          f"China blast-furnace margin proxy is in the bottom {max(pctl, 1):.0f}% of its 10-year range: mills near break-even, watch for output cuts and export pressure"))
        elif pctl >= 80:
            items.append(("info", f"中國高爐利潤代理在 10 年分位 {pctl:.0f}：利潤豐厚，留意產能復產",
                          f"China blast-furnace margin proxy at 10-year percentile {pctl:.0f}: rich margins, watch for restarts"))

    # 3. 美中價差：美國熱軋是中國的幾倍
    #    有東京製鐵盤價時，一起列出日本：牆內（美國）、中間（日本）、低價區（中國）三層
    ts = data.tokyo_steel()
    gap = an.hrc_usd_per_tonne(px, ts["hrc"] if "hrc" in ts else None)
    gap = gap.dropna(subset=[c for c in ("US", "China") if c in gap])
    if len(gap) and {"US", "China"} <= set(gap.columns):
        us, cn = gap["US"].iloc[-1], gap["China"].iloc[-1]
        jp = gap["Japan"].ffill().iloc[-1] if "Japan" in gap else float("nan")
        ratio = us / cn
        if ratio >= 1.5:
            if pd.notna(jp):
                items.append(("info", f"熱軋每噸：美國 {us:,.0f}、日本（東京製鐵盤價）{jp:,.0f}、中國 {cn:,.0f} 美元。美國是中國的 {ratio:.1f} 倍，關稅牆仍高",
                              f"HRC per tonne: US {us:,.0f}, Japan (Tokyo Steel list) {jp:,.0f}, China {cn:,.0f} USD. "
                              f"The US is {ratio:.1f}x China: the tariff wall is still high"))
            else:
                items.append(("info", f"美國熱軋價格是中國的 {ratio:.1f} 倍（每噸 {us:,.0f} vs {cn:,.0f} 美元）：關稅壁壘仍高",
                              f"US HRC is {ratio:.1f}x China's (USD {us:,.0f} vs {cn:,.0f}/t): tariff wall still high"))

    # 4. 中國出口（最新月份）
    ex = data.china_exports()
    mon = ex.get("monthly", [])
    if len(mon) >= 2:
        last, prev = mon[-1], mon[-2]
        mom = (last["mt"] / prev["mt"] - 1) * 100
        ytd = ex.get("ytd", {})
        items.append(("down" if mom < 0 else "up",
                      f"中國 {last['month'][-2:].lstrip('0')} 月鋼材出口 {last['mt']:.2f} 百萬噸（{_zh(mom, '月')}），今年累計{_zh(ytd.get('yoy_pct', 0))}",
                      f"China exported {last['mt']:.2f} Mt of steel in {pd.Timestamp(last['month']).strftime('%b')} (MoM {_fmt_pct(mom)}), YTD {_fmt_pct(ytd.get('yoy_pct', 0))}"))

    # 5. 全球產量（worldsteel 最新月份）
    ws = data.worldsteel_monthly()
    if not ws.empty:
        m = ws["month"].max()
        tot = ws[(ws["month"] == m) & ws["entity"].str.startswith("Total")]
        cn = ws[(ws["month"] == m) & (ws["entity"] == "China")]
        if len(tot) and len(cn):
            items.append(("info",
                          f"{m[:4]} 年 {m[-2:].lstrip('0')} 月全球粗鋼 {tot['mt'].iloc[0]:.1f} 百萬噸（{_zh(tot['yoy_pct'].iloc[0])}），中國 {cn['mt'].iloc[0]:.1f}（{_zh(cn['yoy_pct'].iloc[0])}）",
                          f"World crude steel {tot['mt'].iloc[0]:.1f} Mt in {pd.Timestamp(m).strftime('%b %Y')} (YoY {_fmt_pct(tot['yoy_pct'].iloc[0])}); China {cn['mt'].iloc[0]:.1f} ({_fmt_pct(cn['yoy_pct'].iloc[0])})"))

    # 6. 中鋼最新盤價
    csc = data.csc_prices().get("changes", [])
    if csc:
        last = csc[-1]
        cum = sum(c["hrc"] for c in csc if c["month"][:4] == last["month"][:4])
        verb_zh = "調漲" if last["hrc"] > 0 else ("調降" if last["hrc"] < 0 else "平盤")
        items.append(("up" if last["hrc"] > 0 else ("down" if last["hrc"] < 0 else "info"),
                      f"中鋼 {last['month'][-2:].lstrip('0')} 月盤熱軋{verb_zh}" + (f" {abs(last['hrc']):,} 元/噸" if last["hrc"] else "")
                      + f"，{last['month'][:4]} 年累計 {cum:+,} 元",
                      f"China Steel {pd.Timestamp(last['month']).strftime('%b')} HRC list price {last['hrc']:+,} TWD/t; {last['month'][:4]} cumulative {cum:+,}"))

    # 6b. 台灣視角：出口目的地變化最大的一條（詳見「台灣視角」頁）
    try:
        from . import taiwan
        tw = taiwan.observations()
        if tw:
            items.append(tw[0])
    except Exception:  # noqa: BLE001 - 台灣資料缺漏時不影響其他重點
        pass

    # 7. 近 60 天的政策／事件
    ev = data.events()
    if len(ev):
        recent = ev[ev["date"] >= pd.Timestamp.today() - pd.Timedelta(days=60)].sort_values("date", ascending=False)
        for _, r in recent.head(1).iterrows():
            items.append(("warn", f"近期事件（{r['date']:%m/%d}）：{r['zh']}", f"Recent event ({r['date']:%b %d}): {r['en']}"))

    return items[:max_items]
