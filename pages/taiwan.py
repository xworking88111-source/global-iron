"""台灣視角：全球鋼鐵市場分裂之後，台灣的鋼材往哪裡去、從哪裡來。

1. 自動觀察：依固定規則從資料產生的重點
2. 出口去哪裡：近 12 個月累計的出口目的地，以及和三年前同期比較
3. 進口從哪裡來：來源占比（中國、日本、韓國、東協、其他）
4. 價格與數量：官方的鋼鐵單價指數與數量指數（2021 = 100）

--- English ---
Taiwan lens: after the global steel market split, where Taiwan's steel goes and where it comes from.

1. Observations: rule-based bullets generated from the data
2. Exports: trailing-12-month value by destination, and change vs three years earlier
3. Imports: share by origin (China, Japan, Korea, ASEAN, other)
4. Prices and volumes: official steel unit-value and quantity indices (2021 = 100)
"""
from __future__ import annotations

import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from core import taiwan as tw
from core.cache import cached
from core.config import COLORS
from core.i18n import t

from .common import GRAPH_CONFIG, SERIES, card, empty_fig, source_line, stat, theme

GOOD, BAD = SERIES[0], SERIES[7]  # 發散配色：藍 = 增加，紅 = 減少
ICONS = {"up": "▲", "down": "▼", "warn": "⚠", "info": "•"}
# 每個國家固定一個顏色（依配色順序，不重複），兩張圖之間顏色一致
PARTNER_COLOR = {"us": SERIES[0], "eu": SERIES[1], "asean": SERIES[2], "mx": SERIES[3], "cn": SERIES[7],
                 "jp": SERIES[6], "kr": SERIES[4], "other": COLORS["muted"]}


def _mon(m: int, lang: str) -> str:
    """月份顯示：中文用數字（10），英文用縮寫（Oct）。"""
    return str(m) if lang == "zh" else ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[m - 1])


def _yoy(p: float, lang: str) -> str:
    """年增率文字：中文「年減 2%」，英文「-2% YoY」。"""
    return f"年{'增' if p >= 0 else '減'} {abs(p):.0f}%" if lang == "zh" else f"{p:+.0f}% YoY"


def _exports_fig(product: str, lang: str):
    r = tw.rolling12("export", product)
    if r.empty:
        return empty_fig(t("no_data", lang))
    fig = go.Figure()
    for code in tw.EXPORT_PARTNERS:
        if code in r:
            fig.add_trace(go.Scatter(x=r.index, y=r[code], mode="lines", name=tw.name(code, lang),
                                     line=dict(color=PARTNER_COLOR[code], width=2),
                                     hovertemplate="%{y:,.0f}"))
    theme(fig, height=340)
    fig.update_layout(yaxis_title=t("tw_usd_m_12m", lang))
    return fig


def _exports_change_fig(product: str, lang: str):
    """今年 1 月至最新月 vs 三年前同期：各目的地增減（百萬美元）。"""
    y = tw.ytd("export", product)
    if y.empty or len(y) < 4:
        return empty_fig(t("no_data", lang))
    yr, base = y.index.max(), y.index.max() - 3
    codes = [c for c in tw.EXPORT_PARTNERS if c in y] + (["world"] if "world" in y else [])
    chg = sorted(((c, y.loc[yr, c] - y.loc[base, c]) for c in codes), key=lambda kv: kv[1])
    labels = [tw.name(c, lang) if c != "world" else t("tw_total", lang) for c, _ in chg]
    vals = [v for _, v in chg]
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h", text=[f"{v:+,.0f}" for v in vals], textposition="outside",
        textfont=dict(color=COLORS["text_2"]),
        marker=dict(color=[GOOD if v >= 0 else BAD for v in vals], cornerradius=3),
        hovertemplate="%{y}: %{x:+,.0f}<extra></extra>"))
    lim = max(abs(v) for v in vals) * 1.6 or 1  # 留空間給長條外的數字，手機上才不會壓到國家名
    theme(fig, height=340, legend=False)
    fig.update_layout(hovermode="closest", xaxis=dict(range=[-lim, lim], title=t("tw_usd_m", lang)))
    fig.update_traces(cliponaxis=False)
    return fig, yr, base, y.attrs["last_month"]


def _imports_fig(product: str, lang: str):
    s = tw.import_shares(product)
    if s.empty:
        return empty_fig(t("no_data", lang))
    fig = go.Figure()
    for code in list(tw.IMPORT_PARTNERS) + ["other"]:
        if code in s:
            fig.add_trace(go.Scatter(x=s.index, y=s[code], mode="lines", stackgroup="one", name=tw.name(code, lang),
                                     line=dict(width=0.5, color=PARTNER_COLOR[code]),
                                     hovertemplate="%{y:.0f}%"))
    theme(fig, height=340)
    fig.update_layout(yaxis=dict(range=[0, 100], ticksuffix="%"))
    return fig


def _index_fig(prefix: str, lang: str):
    ix = tw.indices()
    cols = [f"{prefix}_uv", f"{prefix}_qty"]
    if ix.empty or not set(cols) <= set(ix.columns):
        return empty_fig(t("no_data", lang))
    fig = go.Figure()
    for col, color, key in ((cols[0], SERIES[0], "tw_unit_value"), (cols[1], SERIES[1], "tw_quantity")):
        s = ix[col].dropna().rolling(3).mean().dropna()  # 3 個月移動平均：單月數量波動很大
        fig.add_trace(go.Scatter(x=s.index, y=s, mode="lines", name=t(key, lang),
                                 line=dict(color=color, width=2), hovertemplate="%{y:.1f}"))
    fig.add_hline(y=100, line=dict(color=COLORS["border"], width=1, dash="dash"))
    theme(fig, height=300)
    fig.update_layout(yaxis_title="2021 = 100")
    return fig


@cached()
def build(product: str, lang: str):
    """依貨品切換產生三張圖與說明（快取：每種組合只算一次）。"""
    res = _exports_change_fig(product, lang)
    if isinstance(res, tuple):
        bar, yr, base, lm = res
        bar_title = t("tw_change_title", lang).format(yr=yr, base=base, m=_mon(lm, lang))
    else:
        bar, bar_title = res, ""
    return _exports_fig(product, lang), bar, bar_title, _imports_fig(product, lang)


@cached()
def layout(lang: str):
    """台灣視角頁。"""
    obs = tw.observations()
    obs_box = html.Div([
        html.H3(t("tw_obs_title", lang), className="card-title"),
        html.Ul([html.Li([html.Span(ICONS[tone], className=f"hl-icon {tone}"), html.Span(zh if lang == "zh" else en)])
                 for tone, zh, en in obs], className="hl-list"),
    ], className="gi-card highlights") if obs else None

    m = tw.monthly("export")
    latest = f"{m.index.max():%Y-%m}" if not m.empty else "—"
    ex, im = tw.ytd("export"), tw.ytd("import")
    stats = None
    if not ex.empty and not im.empty:
        yr = ex.index.max()
        lm = ex.attrs["last_month"]
        stats = html.Div([
            stat(t("tw_exports_ytd", lang).format(m=_mon(lm, lang)), f"{ex.loc[yr, 'world']:,.0f}",
                 f"{t('tw_usd_m', lang)} · {_yoy((ex.loc[yr, 'world'] / ex.loc[yr - 1, 'world'] - 1) * 100, lang)}"),
            stat(t("tw_imports_ytd", lang).format(m=_mon(lm, lang)), f"{im.loc[yr, 'world']:,.0f}",
                 f"{t('tw_usd_m', lang)} · {_yoy((im.loc[yr, 'world'] / im.loc[yr - 1, 'world'] - 1) * 100, lang)}"),
            stat(t("tw_net", lang), f"{ex.loc[yr, 'world'] - im.loc[yr, 'world']:+,.0f}", t("tw_usd_m", lang)),
        ], className="stat-row")

    f_ex, f_bar, bar_title, f_im = build("steel", lang)
    product_ctrl = html.Div([
        html.Span(t("tw_product", lang), className="ctl-label"),
        dcc.RadioItems(id="tw-product", value="steel", inline=True, className="seg",
                       options=[{"label": t(f"tw_p_{k}", lang), "value": k} for k in tw.PRODUCTS]),
    ], className="controls")

    return html.Div([
        html.Div([html.H2(t("nav_taiwan", lang)),
                  html.Span(f"{t('tw_latest', lang)} {latest}", className="asof")], className="page-head"),
        html.P(t("tw_intro", lang), className="muted"),
        obs_box,
        card(None, stats, product_ctrl) if stats else product_ctrl,
        card(t("tw_exports_title", lang),
             html.Div([html.Div(dcc.Graph(id="tw-exports", figure=f_ex, config=GRAPH_CONFIG)),
                       html.Div([html.H3(bar_title, id="tw-change-title", className="card-title"),
                                 dcc.Graph(id="tw-change", figure=f_bar, config=GRAPH_CONFIG)])],
                      className="grid-2"),
             note=t("tw_exports_note", lang)),
        card(t("tw_imports_title", lang), dcc.Graph(id="tw-imports", figure=f_im, config=GRAPH_CONFIG),
             note=t("tw_imports_note", lang)),
        html.Div([
            card(t("tw_idx_import", lang), dcc.Graph(figure=_index_fig("import", lang), config=GRAPH_CONFIG)),
            card(t("tw_idx_export", lang), dcc.Graph(figure=_index_fig("export", lang), config=GRAPH_CONFIG)),
        ], className="grid-2"),
        html.P(t("tw_idx_note", lang), className="card-note"),
        source_line(lang, t("tw_source", lang)),
    ])


def register(app) -> None:
    @app.callback(Output("tw-exports", "figure"), Output("tw-change", "figure"), Output("tw-change-title", "children"),
                  Output("tw-imports", "figure"), Input("tw-product", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def _switch(product, lang):
        return build(product or "steel", lang or "zh")
