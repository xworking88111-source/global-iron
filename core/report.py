"""每月情勢報告：把網站各頁的資料，用固定規則寫成一份雙語月報。

不用 AI 生成文字：每一句都是模板＋資料，能回溯到網站上的某個數字，所以可以放心引用。
報告分成幾個段落（價差、中國、亞洲盤價、台灣、貿易壁壘、航運與政策、下個月觀察），
每段回傳 {"key", "zh_title", "en_title", "zh": [句子...], "en": [句子...], "link"}。

歸檔：每月 25 日以後的第一次資料更新，會把當時的月報凍結成
data/cache/reports/YYYY-MM.json（見 scripts/update_data.py），之後可以回頭看當時怎麼寫。

--- English ---
Monthly situation report: the site's data written up as a bilingual monthly brief by fixed rules.

No AI-generated prose: every sentence is a template filled with data and traces back to a
number on the site, so it can be quoted safely. Sections (price gap, China, Asian list prices,
Taiwan, trade walls, shipping and policy, what to watch next month) each return
{"key", "zh_title", "en_title", "zh": [sentences], "en": [sentences], "link"}.

Archive: the first data refresh on or after the 25th of each month freezes the report as
data/cache/reports/YYYY-MM.json (see scripts/update_data.py), so past editions stay readable.
"""
from __future__ import annotations

import json

import pandas as pd

from . import analytics as an
from . import config, data

REPORT_DIR = config.CACHE_DIR / "reports"
ARCHIVE_DAY = 25  # 每月幾號以後歸檔（中國海關、worldsteel、東京製鐵、中鋼都已公布）

_EN_MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _chg_zh(x: float, unit: str = "%") -> str:
    return f"{'上漲' if x >= 0 else '下跌'} {abs(x):.1f}{unit}"


def _chg_en(x: float, unit: str = "%") -> str:
    return f"{'up' if x >= 0 else 'down'} {abs(x):.1f}{unit}"


def _mzh(m: str) -> str:
    """'2026-10' -> '2026 年 10 月'"""
    return f"{m[:4]} 年 {int(m[5:7])} 月"


def _men(m: str) -> str:
    return f"{_EN_MON[int(m[5:7]) - 1]} {m[:4]}"


def _section(key, zh_title, en_title, zh, en, link):
    return {"key": key, "zh_title": zh_title, "en_title": en_title, "zh": zh, "en": en, "link": link}


# ---------------------------------------------------------------------------
# 各段落
# ---------------------------------------------------------------------------
def _prices(px: pd.DataFrame) -> dict | None:
    ts = data.tokyo_steel()
    gap = an.hrc_usd_per_tonne(px, ts["hrc"] if "hrc" in ts else None)
    if gap.empty or not {"US", "China"} <= set(gap.columns):
        return None
    zh, en = [], []
    us, cn = gap["US"].dropna(), gap["China"].dropna()
    r_now = us.iloc[-1] / cn.iloc[-1]
    month_ago = gap.index[-1] - pd.Timedelta(days=30)
    g0 = gap[gap.index <= month_ago].ffill()
    r_then = g0["US"].iloc[-1] / g0["China"].iloc[-1] if len(g0) else None
    line_zh = f"熱軋卷每公噸：美國 {us.iloc[-1]:,.0f} 美元、中國 {cn.iloc[-1]:,.0f} 美元"
    line_en = f"Hot-rolled coil per tonne: US USD {us.iloc[-1]:,.0f}, China USD {cn.iloc[-1]:,.0f}"
    if "Japan" in gap and gap["Japan"].notna().any():
        jp = gap["Japan"].ffill().iloc[-1]
        line_zh += f"，日本（東京製鐵盤價）{jp:,.0f} 美元"
        line_en += f", Japan (Tokyo Steel list) USD {jp:,.0f}"
    zh.append(line_zh + "。")
    en.append(line_en + ".")
    if r_then:
        trend_zh = "擴大" if r_now > r_then * 1.02 else "縮小" if r_now < r_then * 0.98 else "大致不變"
        trend_en = "widened" if r_now > r_then * 1.02 else "narrowed" if r_now < r_then * 0.98 else "held steady"
        zh.append(f"美國價格是中國的 {r_now:.1f} 倍，一個月前是 {r_then:.1f} 倍：牆內外價差{trend_zh}。")
        en.append(f"US prices are {r_now:.1f}x China's, against {r_then:.1f}x a month ago: the gap across the wall has {trend_en}.")
    for sid, zh_n, en_n in (("us_hrc", "美國熱軋", "US HRC"), ("cn_hrc", "中國熱軋", "China HRC")):
        if sid in px:
            c = an.pct_change_over(px[sid], 30)
            if c is not None:
                zh.append(f"{zh_n}近一個月{_chg_zh(c)}。")
                en.append(f"{en_n} is {_chg_en(c)} over the past month.")
    return _section("prices", "牆內外價差", "The price gap across the wall", zh, en, "/")


def _china(px: pd.DataFrame) -> dict | None:
    zh, en = [], []
    sp = an.china_bf_spread(px)
    pctl = an.percentile_of_last(sp, 10)
    if pctl is not None:
        if pctl <= 10:
            zh.append(f"中國高爐利潤代理落在 10 年來最低的 {max(pctl, 1):.0f}% 區間，鋼廠普遍在虧損邊緣。")
            en.append(f"China's blast-furnace margin proxy is in the bottom {max(pctl, 1):.0f}% of its 10-year range, with mills near break-even.")
        else:
            state_zh = "偏低，鋼廠利潤受到擠壓" if pctl < 30 else "在正常範圍" if pctl < 70 else "偏高，鋼廠利潤豐厚"
            state_en = "low, squeezing mill margins" if pctl < 30 else "in its normal range" if pctl < 70 else "high, with fat mill margins"
            zh.append(f"中國高爐利潤代理位在 10 年分位 {pctl:.0f}（0 = 最低、100 = 最高），{state_zh}。")
            en.append(f"China's blast-furnace margin proxy sits at {pctl:.0f} on a 0–100 scale of its 10-year range, {state_en}.")
    ex = data.china_exports()
    mon = ex.get("monthly", [])
    if len(mon) >= 2:
        last, prev = mon[-1], mon[-2]
        mom = (last["mt"] / prev["mt"] - 1) * 100
        ytd = ex.get("ytd", {})
        zh.append(f"{_mzh(last['month'])}鋼材出口 {last['mt']:.2f} 百萬噸，比上月{_chg_zh(mom).replace('上漲', '增加').replace('下跌', '減少')}"
                  + (f"；今年累計 {ytd['mt']:.1f} 百萬噸，比去年同期{'增加' if ytd['yoy_pct'] >= 0 else '減少'} {abs(ytd['yoy_pct']):.1f}%" if ytd.get("mt") else "")
                  + "。")
        en.append(f"Steel exports were {last['mt']:.2f} Mt in {_men(last['month'])}, {_chg_en(mom)} from the previous month"
                  + (f"; year to date {ytd['mt']:.1f} Mt, {_chg_en(ytd['yoy_pct'])} on last year" if ytd.get("mt") else "")
                  + ".")
    ws = data.worldsteel_monthly()
    if not ws.empty:
        m = ws["month"].max()
        cn = ws[(ws["month"] == m) & (ws["entity"] == "China")]
        tot = ws[(ws["month"] == m) & ws["entity"].str.startswith("Total")]
        if len(cn) and len(tot):
            share = cn["mt"].iloc[0] / tot["mt"].iloc[0] * 100
            y = cn["yoy_pct"].iloc[0]
            zh.append(f"{_mzh(m)}中國粗鋼產量 {cn['mt'].iloc[0]:.1f} 百萬噸（年{'增' if y >= 0 else '減'} {abs(y):.1f}%），占全球 {share:.0f}%"
                      + ("；減產還沒有真的發生。" if y > -2 else "；減產正在發生。"))
            en.append(f"China made {cn['mt'].iloc[0]:.1f} Mt of crude steel in {_men(m)} ({y:+.1f}% YoY), {share:.0f}% of the world"
                      + ("; output cuts have not really happened yet." if y > -2 else "; output cuts are under way."))
    if not zh:
        return None
    return _section("china", "中國：低價區的源頭", "China: the source of the low-price zone", zh, en, "/monthly")


def _asia() -> dict | None:
    zh, en = [], []
    ts = data.tokyo_steel()
    if "hrc" in ts and ts["hrc"].notna().any():
        h = ts["hrc"].dropna()
        m = f"{h.index[-1]:%Y-%m}"
        yr = h[h.index <= h.index[-1] - pd.DateOffset(years=1)]
        zh.append(f"東京製鐵 {_mzh(m)}熱軋盤價每公噸 {h.iloc[-1]:,.0f} 日圓"
                  + (f"，比一年前{_chg_zh((h.iloc[-1] / yr.iloc[-1] - 1) * 100)}" if len(yr) else "") + "。")
        en.append(f"Tokyo Steel's HRC list price for {_men(m)} is JPY {h.iloc[-1]:,.0f}/t"
                  + (f", {_chg_en((h.iloc[-1] / yr.iloc[-1] - 1) * 100)} on a year earlier" if len(yr) else "") + ".")
        note = data.tokyo_steel_note()
        if note.get("month") and note["month"] > m and note.get("move"):
            mv_zh = {"flat": "全品項平盤", "up": "調漲", "down": "調降"}[note["move"]]
            mv_en = {"flat": "all products unchanged", "up": "a price increase", "down": "a price cut"}[note["move"]]
            zh.append(f"已公布 {_mzh(note['month'])}盤價：{mv_zh}。")
            en.append(f"It has announced {mv_en} for {_men(note['month'])}.")
    csc = data.csc_prices().get("changes", [])
    if csc:
        last = csc[-1]
        cum = sum(c["hrc"] for c in csc if c["month"][:4] == last["month"][:4])
        v = last["hrc"]
        zh.append(f"中鋼 {_mzh(last['month'])}熱軋盤價" + (f"{'調漲' if v > 0 else '調降'} {abs(v):,} 元／噸" if v else "平盤")
                  + f"，{last['month'][:4]} 年累計 {cum:+,} 元。")
        en.append(f"China Steel's HRC list price for {_men(last['month'])}: {v:+,} TWD/t; {last['month'][:4]} cumulative {cum:+,}.")
    if not zh:
        return None
    return _section("asia", "亞洲鋼廠盤價", "Asian mills' list prices", zh, en, "/monthly")


def _taiwan() -> dict | None:
    from . import taiwan
    obs = taiwan.observations()
    if not obs:
        return None
    pick = obs[:4]
    return _section("taiwan", "台灣：夾在兩個價格區之間", "Taiwan: caught between two price zones",
                    [o[1] + "。" if not o[1].endswith("。") else o[1] for o in pick],
                    [o[2] + "." if not o[2].endswith(".") else o[2] for o in pick], "/taiwan")


def _walls() -> dict | None:
    from . import walls
    obs = walls.observations()
    if not obs:
        return None
    pick = obs[:4]
    return _section("walls", "貿易壁壘", "Trade walls",
                    [o[1] + "。" for o in pick], [o[2] + "." for o in pick], "/walls")


def _shipping(px: pd.DataFrame) -> dict | None:
    zh, en = [], []
    for sid, zh_n, en_n in (("dry_bulk", "乾散貨運價（BDRY）", "Dry-bulk freight (BDRY)"), ("brent", "布蘭特原油", "Brent crude")):
        if sid in px:
            c = an.pct_change_over(px[sid], 30)
            if c is not None:
                zh.append(f"{zh_n}近一個月{_chg_zh(c)}。")
                en.append(f"{en_n} is {_chg_en(c)} over the past month.")
    ev = data.events()
    if len(ev):
        recent = ev[ev["date"] >= pd.Timestamp.today().normalize() - pd.Timedelta(days=60)]
        if len(recent):
            for r in recent.sort_values("date").itertuples():
                zh.append(f"{r.date:%m/%d}：{r.zh}。")
                en.append(f"{r.date:%b %d}: {r.en}.")
        else:
            zh.append("本站政策與事件時間軸近 60 天沒有新增事件。")
            en.append("The site's policy and event timeline has no new entries in the last 60 days.")
    if not zh:
        return None
    return _section("shipping", "航運與政策", "Shipping and policy", zh, en, "/risk")


def _watch(today: pd.Timestamp) -> dict:
    """下個月的資料公布時程（大約日期，依過去慣例）。"""
    nxt = (today + pd.offsets.MonthBegin(1))
    m_zh, m_en = f"{nxt.month} 月", _EN_MON[nxt.month - 1]
    prev = today.month  # 下個月公布的是「這個月」的數字
    zh = [
        f"{m_zh} 7–10 日：中國海關公布 {prev} 月鋼材出口；財政部公布台灣 {prev} 月進出口。",
        f"{m_zh}中旬：東京製鐵與中鋼公布下個月盤價。",
        f"{m_zh} 20–25 日：worldsteel 公布 {prev} 月全球粗鋼產量。",
        "WTO 貿易救濟案件每半年更新一次；各國新立案通常會先出現在新聞，再晚約半年進入資料庫。",
    ]
    en = [
        f"{m_en} 7–10: China customs publishes {_EN_MON[prev - 1]} steel exports; Taiwan's Ministry of Finance publishes {_EN_MON[prev - 1]} trade.",
        f"Mid-{m_en}: Tokyo Steel and China Steel announce next month's list prices.",
        f"{m_en} 20–25: worldsteel publishes {_EN_MON[prev - 1]} world crude steel output.",
        "WTO trade-remedy data update every six months; new cases usually show up in the news first and enter the database about half a year later.",
    ]
    return _section("watch", "下個月觀察", "What to watch next month", zh, en, None)


def _headline(px: pd.DataFrame) -> tuple[str, str]:
    """一句話總結：牆內外價差的方向＋中國鋼廠的處境。直接從數字組句，不拼接其他段落的句子。"""
    zh, en = [], []
    gap = an.hrc_usd_per_tonne(px).dropna()
    if len(gap) and {"US", "China"} <= set(gap.columns):
        r_now = gap["US"].iloc[-1] / gap["China"].iloc[-1]
        g0 = gap[gap.index <= gap.index[-1] - pd.Timedelta(days=30)]
        if len(g0):
            r_then = g0["US"].iloc[-1] / g0["China"].iloc[-1]
            if r_now > r_then * 1.02:
                zh.append(f"牆內外價差擴大：美國熱軋是中國的 {r_now:.1f} 倍（一個月前 {r_then:.1f} 倍）")
                en.append(f"The gap across the wall widened: US HRC is {r_now:.1f}x China's ({r_then:.1f}x a month ago)")
            elif r_now < r_then * 0.98:
                zh.append(f"牆內外價差縮小：美國熱軋是中國的 {r_now:.1f} 倍（一個月前 {r_then:.1f} 倍）")
                en.append(f"The gap across the wall narrowed: US HRC is {r_now:.1f}x China's ({r_then:.1f}x a month ago)")
            else:
                zh.append(f"牆內外價差持平：美國熱軋是中國的 {r_now:.1f} 倍")
                en.append(f"The gap across the wall held: US HRC is {r_now:.1f}x China's")
    pctl = an.percentile_of_last(an.china_bf_spread(px), 10)
    if pctl is not None:
        if pctl <= 10:
            zh.append("中國鋼廠利潤在 10 年最低區間")
            en.append("Chinese mill margins are at 10-year lows")
        elif pctl >= 80:
            zh.append("中國鋼廠利潤處於 10 年高檔")
            en.append("Chinese mill margins are near 10-year highs")
    ex = data.china_exports().get("ytd", {})
    if ex.get("mt"):
        zh.append(f"中國今年鋼材出口 {ex['mt']:.0f} 百萬噸，{'仍比去年多' if ex['yoy_pct'] >= 0 else '只比去年少'} {abs(ex['yoy_pct']):.1f}%")
        en.append(f"China's exports so far this year are {ex['mt']:.0f} Mt, {'still up' if ex['yoy_pct'] >= 0 else 'only down'} {abs(ex['yoy_pct']):.1f}% on last year")
    if not zh:
        return "", ""
    return "；".join(zh) + "。", "; ".join(en) + "."


# ---------------------------------------------------------------------------
# 組合、歸檔
# ---------------------------------------------------------------------------
def build(today: pd.Timestamp | None = None) -> dict:
    """用目前的資料產生月報。"""
    today = (today or pd.Timestamp.today()).normalize()
    px = data.prices()
    sections = []
    for fn in (lambda: _prices(px), lambda: _china(px), _asia, _taiwan, _walls, lambda: _shipping(px)):
        try:
            s = fn()
        except Exception:  # noqa: BLE001 - 某一段資料缺漏時，其他段落照常產生
            s = None
        if s:
            sections.append(s)
    sections.append(_watch(today))
    hz, he = _headline(px)
    return {"month": f"{today:%Y-%m}", "generated": f"{today:%Y-%m-%d}", "headline_zh": hz, "headline_en": he,
            "sections": sections}


def archived() -> list[str]:
    """已歸檔的月份，新的在前。"""
    if not REPORT_DIR.exists():
        return []
    return sorted((p.stem for p in REPORT_DIR.glob("*.json")), reverse=True)


def load(month: str) -> dict:
    return data.load_json(REPORT_DIR / f"{month}.json")


def archive_if_due(today: pd.Timestamp | None = None) -> str | None:
    """每月 ARCHIVE_DAY 日以後，如果這個月還沒歸檔，就把當下的月報存檔。回傳歸檔的月份。"""
    today = (today or pd.Timestamp.today()).normalize()
    month = f"{today:%Y-%m}"
    path = REPORT_DIR / f"{month}.json"
    if today.day < ARCHIVE_DAY or path.exists():
        return None
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(today), ensure_ascii=False, indent=1), encoding="utf-8")
    return month


def to_markdown(rep: dict, lang: str) -> str:
    """月報轉成 Markdown（給「下載」按鈕用）。"""
    title = (f"# 全球鋼鐵市場分裂月報：{_mzh(rep['month'])}" if lang == "zh"
             else f"# Global steel split monthly brief: {_men(rep['month'])}")
    lines = [title, "", (f"資料截至 {rep['generated']}" if lang == "zh" else f"Data as of {rep['generated']}"), ""]
    head = rep.get(f"headline_{lang}")
    if head:
        lines += [f"**{head}**", ""]
    for s in rep["sections"]:
        lines += [f"## {s[f'{lang}_title']}", ""]
        lines += [f"- {x}" for x in s[lang]]
        if s.get("link"):
            lines += ["", f"https://global-iron.onrender.com{s['link']}"]
        lines.append("")
    lines.append("—— Global Iron（https://global-iron.onrender.com）· 資料僅供參考，不構成投資建議。" if lang == "zh"
                 else "— Global Iron (https://global-iron.onrender.com) · For information only, not investment advice.")
    return "\n".join(lines)
