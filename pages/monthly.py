"""月度數據：供需面的三個關鍵月資料。

1. 中國成品鋼材出口（海關）：這兩年鋼價低迷的頭號原因
2. worldsteel 每月粗鋼產量：減產有沒有真的發生
3. 中鋼月盤調整：台灣內銷鋼價的風向球
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from core import data
from core.cache import cached
from core.config import COLORS
from core.i18n import pick, t

from .common import SERIES, card, source_line, stat, theme

GOOD, BAD = SERIES[0], SERIES[7]  # 發散配色：藍 = 增加，紅 = 減少


def _chg(x: float, lang: str, kind: str) -> str:
    """漲跌文字：中文寫「月減 6.1%」，英文寫「MoM -6.1%」。kind = "mom" 或 "yoy"。"""
    if lang == "zh":
        return f"{'月' if kind == 'mom' else '年'}{'增' if x >= 0 else '減'} {abs(x):.1f}%"
    return f"{'MoM' if kind == 'mom' else 'YoY'} {x:+.1f}%"


# ---------------------------------------------------------------------------
# 1. 中國出口
# ---------------------------------------------------------------------------
def _exports_block(lang: str):
    ex = data.china_exports()
    rows = pd.DataFrame(ex.get("monthly", []))
    if rows.empty:
        return card(t("cn_exports_title", lang), html.P(t("no_data", lang)))
    rows["derived"] = rows.get("derived", False).fillna(False).astype(bool)
    rows["month_dt"] = pd.to_datetime(rows["month"])
    last, prev = rows.iloc[-1], rows.iloc[-2]
    mom = (last["mt"] / prev["mt"] - 1) * 100
    annual = {a["year"]: a for a in ex.get("annual", [])}
    ytd = ex.get("ytd", {})

    fig = go.Figure()
    # 直接公布的月份用實心；推算的月份用淡色＋斜線紋理，讀者一眼分得出來
    for derived, name, style in ((False, t("reported", lang), dict(color=SERIES[0])),
                                 (True, t("derived", lang), dict(color="#2c4a6e", pattern_shape="/",
                                                                pattern_fgcolor=SERIES[0]))):
        g = rows[rows["derived"] == derived]
        fig.add_trace(go.Bar(x=g["month_dt"], y=g["mt"], name=name, marker=dict(cornerradius=3, **style),
                             hovertemplate="%{x|%Y-%m}: %{y:.2f} Mt<extra></extra>"))
    # 2025 全年平均月出口量當參考線
    if 2025 in annual:
        avg = annual[2025]["mt"] / 12
        fig.add_hline(y=avg, line=dict(color=COLORS["muted"], width=1, dash="dash"),
                      annotation_text=f"{t('avg_2025', lang)} {avg:.1f}", annotation_position="top left",
                      annotation_font_color=COLORS["muted"])
    theme(fig, height=320)
    fig.update_layout(hovermode="closest", bargap=0.25, yaxis_title="Mt")

    stats = html.Div([
        stat(t("latest_month", lang) + f" ({last['month']})", f"{last['mt']:.2f} Mt",
             _chg(mom, lang, "mom")),
        stat(t("ytd", lang) + " 2026", f"{ytd.get('mt', 0):.1f} Mt", _chg(ytd.get("yoy_pct", 0), lang, "yoy")),
        stat("2025", f"{annual.get(2025, {}).get('mt', 0):.1f} Mt", pick(annual.get(2025, {}), "note", lang)),
        stat("2015", f"{annual.get(2015, {}).get('mt', 0):.1f} Mt", pick(annual.get(2015, {}), "note", lang)),
    ], className="stat-row")
    ctx = " · ".join(f"{c['date']}: {pick(c, '', lang)}" for c in ex.get("context", []))
    return card(t("cn_exports_title", lang), stats, dcc.Graph(figure=fig, config={"displayModeBar": False}),
                note=f"{t('cn_exports_note', lang)} {ctx}. {pick(ex['_meta'], 'derived_note', lang)}")


# ---------------------------------------------------------------------------
# 2. worldsteel 每月產量
# ---------------------------------------------------------------------------
def _production_block(lang: str):
    ws = data.worldsteel_monthly()
    if ws.empty:
        return card(t("ws_monthly_title", lang), html.P(t("no_data", lang)))
    total = ws[(ws["kind"] == "region") & ws["entity"].str.startswith("Total")].set_index("month")["mt"]
    china = ws[(ws["kind"] == "country") & (ws["entity"] == "China")].set_index("month")["mt"]
    df = pd.DataFrame({"world": total, "china": china}).dropna().sort_index()
    df["rest"] = df["world"] - df["china"]
    x = pd.to_datetime(df.index)

    fig = go.Figure()
    for col, color, key in (("china", SERIES[0], "china"), ("rest", SERIES[1], "rest_of_world")):
        fig.add_trace(go.Scatter(x=x, y=df[col], mode="lines+markers", name=t(key, lang),
                                 line=dict(color=color, width=2), marker=dict(size=6),
                                 hovertemplate="%{x|%Y-%m}: %{y:.1f} Mt"))
    theme(fig, height=300)
    fig.update_layout(yaxis_title="Mt")

    # 最新月份：前 10 大生產國的年增率（發散橫條）
    latest = ws["month"].max()
    top = ws[(ws["month"] == latest) & (ws["kind"] == "country")].sort_values("yoy_pct")
    names = {"China": "中國", "India": "印度", "United States": "美國", "Japan": "日本", "Russia": "俄羅斯",
             "South Korea": "韓國", "Türkiye": "土耳其", "Germany": "德國", "Brazil": "巴西",
             "Viet Nam": "越南", "Iran": "伊朗", "Italy": "義大利", "Taiwan, China": "台灣", "Mexico": "墨西哥"}
    labels = [names.get(e, e) if lang == "zh" else e for e in top["entity"]]
    bar = go.Figure(go.Bar(
        x=top["yoy_pct"], y=labels, orientation="h", text=[f"{v:+.1f}%" for v in top["yoy_pct"]],
        textposition="outside", textfont=dict(color=COLORS["text_2"]),
        marker=dict(color=[GOOD if v >= 0 else BAD for v in top["yoy_pct"]], cornerradius=3),
        customdata=top["mt"], hovertemplate="%{y}: %{customdata:.1f} Mt (%{x:+.1f}%)<extra></extra>"))
    lim = max(5, top["yoy_pct"].abs().max() * 1.35)
    theme(bar, height=300, legend=False)
    bar.update_layout(hovermode="closest", xaxis=dict(range=[-lim, lim], ticksuffix="%"))
    bar.update_traces(cliponaxis=False)

    w = df.iloc[-1]
    world_yoy = ws[(ws["month"] == latest) & ws["entity"].str.startswith("Total")]["yoy_pct"].iloc[0]
    stats = html.Div([
        stat(t("world_output", lang) + f" ({latest})", f"{w['world']:.1f} Mt", _chg(world_yoy, lang, "yoy")),
        stat(t("china", lang), f"{w['china']:.1f} Mt", f"{w['china'] / w['world'] * 100:.0f}% {t('of_world', lang)}"),
    ], className="stat-row")
    return card(t("ws_monthly_title", lang), stats,
                html.Div([html.Div(dcc.Graph(figure=fig, config={"displayModeBar": False})),
                          html.Div([html.H3(f"{t('top10_yoy', lang)} ({latest})", className="card-title"),
                                    dcc.Graph(figure=bar, config={"displayModeBar": False})])],
                         className="grid-2"),
                note=t("ws_monthly_note", lang))


# ---------------------------------------------------------------------------
# 3. 中鋼月盤
# ---------------------------------------------------------------------------
def _csc_block(lang: str):
    raw = data.csc_prices()
    df = pd.DataFrame(raw.get("changes", []))
    if df.empty:
        return card(t("csc_title", lang), html.P(t("no_data", lang)))
    df["month_dt"] = pd.to_datetime(df["month"])
    df["cum"] = df["hrc"].cumsum()
    notes = [pick(r, "note", lang) for _, r in df.iterrows()]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["month_dt"], y=df["hrc"], name=t("monthly_change", lang),
                         marker=dict(color=[GOOD if v >= 0 else BAD for v in df["hrc"]], cornerradius=3),
                         text=[f"{v:+,}" if v else "0" for v in df["hrc"]], textposition="outside",
                         textfont=dict(color=COLORS["text_2"]), customdata=notes,
                         hovertemplate="%{x|%Y-%m}: %{y:+,} TWD/t<br>%{customdata}<extra></extra>"))
    fig.add_trace(go.Scatter(x=df["month_dt"], y=df["cum"], name=t("cumulative", lang), mode="lines+markers",
                             line=dict(color=COLORS["text_2"], width=2, dash="dot"), marker=dict(size=6),
                             hovertemplate="%{y:+,} TWD/t"))
    fig.add_hline(y=0, line=dict(color=COLORS["border"], width=1))
    theme(fig, height=320)
    fig.update_layout(yaxis_title="TWD/t", bargap=0.3)
    fig.update_traces(cliponaxis=False, selector=dict(type="bar"))

    last = df.iloc[-1]
    stats = html.Div([
        stat(t("latest_month", lang) + f" ({last['month']})", f"{last['hrc']:+,}", "TWD/t"),
        stat(t("ytd", lang) + f" {last['month'][:4]}", f"{int(last['cum']):+,}", "TWD/t"),
        stat(t("ups_downs", lang), f"{(df['hrc'] > 0).sum()} / {(df['hrc'] < 0).sum()}",
             t("months_up_down", lang)),
    ], className="stat-row")
    return card(t("csc_title", lang), stats, dcc.Graph(figure=fig, config={"displayModeBar": False}),
                note=pick(raw["_meta"], "", lang))


@cached()
def layout(lang: str):
    """月度數據頁（內容只跟語言與資料有關，整頁快取）。"""
    return html.Div([
        html.Div([html.H2(t("nav_monthly", lang))], className="page-head"),
        html.P(t("monthly_intro", lang), className="muted"),
        _exports_block(lang),
        _production_block(lang),
        _csc_block(lang),
        source_line(lang, "GACC via SteelOrbis / SMM / SunSirs / GMK Center; worldsteel monthly press releases; "
                          "CSC price announcements via Taiwanese media (see data/static/*.json for links)"),
    ])

