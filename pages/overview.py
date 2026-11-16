"""市場總覽：「一眼掌握」的首頁。

上方：指標卡（最新價、週／月／年漲跌、10 年分位）。
中間：依中國高爐利潤分位判斷的市場狀態。
下方：三張圖，共用一個區間選擇器與事件標註。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from core import analytics as an
from core import config, data
from core.i18n import t

from .common import RANGES, SERIES, add_end_labels, add_events, card, empty_fig, kpi_tile, source_line, theme


def layout(lang: str):
    """首頁版面。指標卡和市場狀態在這裡直接算好；圖表交給下面的 callback 畫。"""
    px = data.prices()
    if px.empty:
        return card(None, html.P(t("no_data", lang)))

    spread = an.china_bf_spread(px)
    s_spread = an.series_summary(spread)
    regime = an.regime_label(s_spread["pctl_10y"])
    as_of = s_spread["date"]

    def tile(sid, label_key, unit, nd=0, conv=None):
        """用價格序列 id 產生一張指標卡；conv 可選擇先換算單位。"""
        s = px[sid] if sid in px else pd.Series(dtype=float)
        if conv is not None:
            s = conv(s)
        summ = an.series_summary(s)
        return kpi_tile(t(label_key, lang), an.fmt(summ["value"], nd), unit, summ, lang)

    tiles = html.Div([
        tile("cn_hrc", "kpi_cn_hrc", "CNY/t"),
        tile("us_hrc", "kpi_us_hrc", "USD/st"),
        tile("ore_62", "kpi_ore", "USD/t", nd=1),
        tile("cn_coke", "kpi_coke", "CNY/t"),
        kpi_tile(t("kpi_spread", lang), an.fmt(s_spread["value"], 0), "CNY/t", s_spread, lang),
        tile("dry_bulk", "kpi_freight", "USD", nd=2),
    ], className="kpi-row")

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
        dcc.RadioItems(id="ov-range", options=[{"label": k, "value": k} for k in RANGES], value="3Y",
                       inline=True, className="seg"),
        dcc.Checklist(id="ov-events", options=[{"label": t("show_events", lang), "value": "on"}],
                      value=["on"], inline=True, className="seg"),
    ], className="controls")

    return html.Div([
        html.Div([html.H2(t("nav_overview", lang)),
                  html.Span(f"{t('data_as_of', lang)} {as_of:%Y-%m-%d}" if as_of is not None else "",
                            className="asof")], className="page-head"),
        tiles,
        regime_box,
        controls,
        html.Div([
            card(t("chart_spread", lang), dcc.Graph(id="ov-spread", config={"displayModeBar": False}),
                 note=t("chart_spread_note", lang)),
            card(t("chart_gap", lang), dcc.Graph(id="ov-gap", config={"displayModeBar": False}),
                 note=t("chart_gap_note", lang)),
        ], className="grid-2"),
        card(t("chart_prices", lang), dcc.Graph(id="ov-prices", config={"displayModeBar": False}),
             note=t("rebased_note", lang)),
        source_line(lang, "SHFE / DCE via Sina Finance; CME HRC, SGX/CME iron ore, BDRY via Yahoo Finance"),
    ])


def _start(px: pd.DataFrame, rng: str) -> pd.Timestamp:
    """區間選項（例如 3Y）換成起始日期。"""
    return px.index.max() - pd.DateOffset(years=RANGES.get(rng, 3))


def register(app):
    @app.callback(Output("ov-spread", "figure"), Output("ov-gap", "figure"), Output("ov-prices", "figure"),
                  Input("ov-range", "value"), Input("ov-events", "value"), Input("lang", "data"))
    def update(rng, ev_on, lang):
        px = data.prices()
        if px.empty:
            e = empty_fig(t("no_data", lang))
            return e, e, e
        start = _start(px, rng)
        show_ev = bool(ev_on)

        # --- 1. 高爐利潤代理，加上 10 年平均參考線 ---------------------------------
        sp = an.china_bf_spread(px)
        avg10 = sp[sp.index >= sp.index.max() - pd.DateOffset(years=10)].mean()
        spv = sp[sp.index >= start]
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
        gap = gap[gap.index >= start].ffill()
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
        reb = reb / reb.bfill().iloc[0] * 100
        lbl = {c: config.PRICE_SERIES[c][lang] for c in reb.columns}
        col_map = {c: SERIES[i] for i, c in enumerate(cols)}
        f3 = go.Figure()
        for c in reb.columns:
            f3.add_trace(go.Scatter(x=reb.index, y=reb[c], mode="lines", name=lbl[c],
                                    line=dict(color=col_map[c], width=2),
                                    customdata=px.loc[reb.index, c],
                                    hovertemplate="%{y:.0f} (%{customdata:,.0f})"))
        f3.add_hline(y=100, line=dict(color=COLOR_MUTED, width=1))
        add_end_labels(f3, reb, lbl, col_map)
        if show_ev and len(reb):
            add_events(f3, start, lang, y_top=float(reb.max().max()))
        theme(f3, height=380)
        f3.update_layout(margin=dict(r=170))
        return f1, f2, f3


COLOR_MUTED = config.COLORS["muted"]
