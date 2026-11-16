"""市場總覽：「一眼掌握」的首頁。

上方：指標卡（最新價、週／月／年漲跌、10 年分位）。
中間：依中國高爐利潤分位判斷的市場狀態。
下方：三張圖，共用一個區間選擇器與事件標註。

--- English ---
Market overview: the "one glance" home page.

Top: weekly highlights and KPI tiles (latest price, 1W/1M/1Y change, 10-year percentile).
Middle: market regime from the China blast-furnace margin percentile.
Bottom: three charts sharing one range selector and an event overlay.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from core import analytics as an
from core import config, data, highlights
from core.cache import cached
from core.i18n import t

from .common import GRAPH_CONFIG, RANGES, SERIES, add_end_labels, add_events, card, empty_fig, kpi_tile, source_line, theme


DEFAULT_RANGE = "3Y"


@cached()
def layout(lang: str):
    """首頁版面（含預設圖表）。

    圖表直接在第一次回應就畫好，不用等第二趟 callback：少一次來回、也不會先閃白框。
    結果會快取，同一份資料下所有訪客共用。
    """
    px = data.prices()
    if px.empty:
        return card(None, html.P(t("no_data", lang)))

    spread = an.china_bf_spread(px)
    s_spread = an.series_summary(spread)
    regime = an.regime_label(s_spread["pctl_10y"])
    as_of = s_spread["date"]

    # 單位切換：原幣原單位（交易員習慣）或統一美元／公噸（跨市場比較）
    unit_ctl = html.Div([
        html.Span(t("unit_label", lang), className="ctl-label"),
        dcc.RadioItems(id="ov-unit", value="local", inline=True, className="seg",
                       options=[{"label": t("unit_local", lang), "value": "local"},
                                {"label": t("unit_usd", lang), "value": "usd_t"}]),
    ], className="controls unit-ctl")
    tiles = html.Div(build_tiles("local", lang), id="ov-tiles", className="kpi-row")

    # 市場狀態的燈號顏色（狀態色）
    regime_cls = {"regime_squeezed": "critical", "regime_weak": "warning",
                  "regime_normal": "good", "regime_strong": "good"}.get(regime, "")
    regime_box = html.Div([
        html.Span(t("regime_title", lang), className="regime-label"),
        html.Span("●", className=f"regime-dot {regime_cls}"),
        html.Span(t(regime, lang), className="regime-text"),
    ], className="regime")

    controls = html.Div([
        html.Span(t("range", lang), className="ctl-label"),
        dcc.RadioItems(id="ov-range", options=[{"label": k, "value": k} for k in RANGES], value=DEFAULT_RANGE,
                       inline=True, className="seg"),
        dcc.Checklist(id="ov-events", options=[{"label": t("show_events", lang), "value": "on"}],
                      value=["on"], inline=True, className="seg"),
    ], className="controls")

    f1, f2, f3 = build_charts(DEFAULT_RANGE, True, lang)

    # 本週重點：箭頭／圖示表示方向，不只靠顏色
    icons = {"up": "▲", "down": "▼", "warn": "⚠", "info": "•"}
    hl = highlights.build()
    hl_box = html.Div([
        html.Div([html.H3(t("highlights_title", lang), className="card-title"),
                  dcc.Link(t("highlights_more", lang) + " →", href="/monthly", className="link small")],
                 className="hl-head"),
        html.Ul([html.Li([html.Span(icons[tone], className=f"hl-icon {tone}"),
                          html.Span(zh if lang == "zh" else en)]) for tone, zh, en in hl],
                className="hl-list"),
    ], className="gi-card highlights") if hl else None

    return html.Div([
        html.Div([html.H2(t("nav_overview", lang)),
                  html.Span(f"{t('data_as_of', lang)} {as_of:%Y-%m-%d}" if as_of is not None else "",
                            className="asof")], className="page-head"),
        hl_box,
        unit_ctl,
        tiles,
        regime_box,
        controls,
        html.Div([
            card(t("chart_spread", lang), dcc.Graph(id="ov-spread", figure=f1, config=GRAPH_CONFIG),
                 note=t("chart_spread_note", lang)),
            card(t("chart_gap", lang), dcc.Graph(id="ov-gap", figure=f2, config=GRAPH_CONFIG),
                 note=t("chart_gap_note", lang)),
        ], className="grid-2"),
        card(t("chart_prices", lang), dcc.Graph(id="ov-prices", figure=f3, config=GRAPH_CONFIG),
             note=t("rebased_note", lang)),
        source_line(lang, "SHFE / DCE via Sina Finance; CME HRC, SGX/CME iron ore, BDRY via Yahoo Finance"),
    ])


def _start(px: pd.DataFrame, rng: str) -> pd.Timestamp:
    """區間選項（例如 3Y）換成起始日期。"""
    return px.index.max() - pd.DateOffset(years=RANGES.get(rng, 3))


# 指標卡定義：(序列 id, 標籤 key, 原始單位, 小數位, 換算成美元／公噸的方式)
#   "cny" = 人民幣／噸 ÷ 匯率；"st" = 美元／短噸 ÷ 0.907；None = 不是每噸價格，不換算
TILES = [
    ("cn_hrc", "kpi_cn_hrc", "CNY/t", 0, "cny"),
    ("us_hrc", "kpi_us_hrc", "USD/st", 0, "st"),
    ("ore_62", "kpi_ore", "USD/t", 1, "usd"),
    ("cn_coke", "kpi_coke", "CNY/t", 0, "cny"),
    ("spread", "kpi_spread", "CNY/t", 0, "cny"),
    ("dry_bulk", "kpi_freight", "USD", 2, None),
]


def _to_usd_t(s: pd.Series, how: str | None, px: pd.DataFrame) -> pd.Series:
    """把整條序列換成美元／公噸（用每天的匯率，所以漲跌幅與分位也是美元口徑）。"""
    if how == "cny":
        return (s / px["fx_cny"].ffill().reindex(s.index, method="ffill")).dropna()
    if how == "st":
        return s / config.SHORT_TON_IN_TONNES
    return s


@cached()
def build_tiles(unit: str, lang: str) -> list:
    """六張指標卡。unit = "local"（原幣原單位）或 "usd_t"（統一美元／公噸）。"""
    px = data.prices()
    out = []
    for sid, key, raw_unit, nd, how in TILES:
        s = an.china_bf_spread(px) if sid == "spread" else (px[sid] if sid in px else pd.Series(dtype=float))
        shown_unit = raw_unit
        if unit == "usd_t" and how is not None:
            s = _to_usd_t(s, how, px)
            shown_unit = "USD/t"
            nd = 0 if how != "usd" else nd
        summ = an.series_summary(s)
        extra = t("not_per_tonne", lang) if unit == "usd_t" and how is None else None
        out.append(kpi_tile(t(key, lang), an.fmt(summ["value"], nd), shown_unit, summ, lang, extra=extra))
    return out


@cached()
def build_charts(rng: str, show_ev: bool, lang: str):
    """三張圖（利潤代理、美中熱軋價差、指數化價格）。結果快取，換區間時才重算。"""
    px = data.prices()
    if px.empty:
        e = empty_fig(t("no_data", lang))
        return e, e, e
    start = _start(px, rng)
    years = RANGES.get(rng, 3)

    # --- 1. 高爐利潤代理，加上 10 年平均參考線 ---------------------------------
    sp = an.china_bf_spread(px)
    avg10 = sp[sp.index >= sp.index.max() - pd.DateOffset(years=10)].mean()
    spv = an.downsample(sp[sp.index >= start], years).round(0)
    f1 = go.Figure()
    f1.add_trace(go.Scatter(x=spv.index, y=spv.values, mode="lines", name=t("kpi_spread", lang),
                            line=dict(color=SERIES[0], width=2),
                            hovertemplate="%{y:,.0f} CNY/t<extra></extra>"))
    f1.add_hline(y=avg10, line=dict(color=COLOR_MUTED, width=1, dash="dash"),
                 annotation_text=f"{t('spread_avg', lang)} {avg10:,.0f}",
                 annotation_font_color=COLOR_MUTED, annotation_position="top left")
    if show_ev and len(spv):
        add_events(f1, start, lang, y_top=float(spv.max()))
    theme(f1, legend=False)

    # --- 2. 美國 vs 中國熱軋（美元/公噸）-----------------------------------------
    gap = an.hrc_usd_per_tonne(px)
    gap = an.downsample(gap[gap.index >= start].ffill(), years).round(0)
    names = {"China": t("kpi_cn_hrc", lang), "US": t("kpi_us_hrc", lang)}
    colors = {"China": SERIES[0], "US": SERIES[1]}
    f2 = go.Figure()
    for col in gap.columns:
        f2.add_trace(go.Scatter(x=gap.index, y=gap[col], mode="lines", name=names[col],
                                line=dict(color=colors[col], width=2),
                                hovertemplate="%{y:,.0f} USD/t"))
    add_end_labels(f2, gap, names, colors)
    if show_ev and len(gap):
        add_events(f2, start, lang, y_top=float(gap.max().max()))
    theme(f2)
    f2.update_layout(margin=dict(r=90))  # 右側留空間給線尾標籤

    # --- 3. 指數化價格：只用一個 Y 軸，起點 = 100（不同單位才能比較）----------------
    cols = ["cn_hrc", "cn_ore", "cn_coke", "us_hrc"]
    reb = px.loc[px.index >= start, [c for c in cols if c in px]].ffill().dropna(how="all")
    reb = an.downsample(reb / reb.bfill().iloc[0] * 100, years).round(1)
    lbl = {c: config.PRICE_SERIES[c][lang] for c in reb.columns}
    col_map = {c: SERIES[i] for i, c in enumerate(cols)}
    f3 = go.Figure()
    for c in reb.columns:
        f3.add_trace(go.Scatter(x=reb.index, y=reb[c], mode="lines", name=lbl[c],
                                line=dict(color=col_map[c], width=2),
                                customdata=px[c].reindex(reb.index, method="ffill").round(1),
                                hovertemplate="%{y:.0f} (%{customdata:,.0f})"))
    f3.add_hline(y=100, line=dict(color=COLOR_MUTED, width=1))
    add_end_labels(f3, reb, lbl, col_map)
    if show_ev and len(reb):
        add_events(f3, start, lang, y_top=float(reb.max().max()))
    theme(f3, height=380)
    f3.update_layout(margin=dict(r=170))
    return f1, f2, f3


def register(app):
    @app.callback(Output("ov-tiles", "children"), Input("ov-unit", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def tiles(unit, lang):
        return build_tiles(unit, lang)

    # 只有使用者改了區間或事件開關才觸發（初始圖已在 layout 畫好）；語言改變時整頁會重畫
    @app.callback(Output("ov-spread", "figure"), Output("ov-gap", "figure"), Output("ov-prices", "figure"),
                  Input("ov-range", "value"), Input("ov-events", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def update(rng, ev_on, lang):
        return build_charts(rng, bool(ev_on), lang)


COLOR_MUTED = config.COLORS["muted"]
