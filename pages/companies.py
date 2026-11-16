"""公司分析：公司檔案、同業相對分數、股價表現、同業比較表。

--- English ---
Companies: profile, peer-relative scores, share performance, quarterly margins, peer table.
"""
from __future__ import annotations

import math
from urllib.parse import parse_qs

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dash_table, dcc, html
from plotly.subplots import make_subplots

from core import analytics as an
from core import data
from core.cache import cached
from core.config import COLORS
from core.i18n import pick, t

from .common import GRAPH_CONFIG, RANGES, SERIES, card, empty_fig, peers, source_line, stat, theme

DEFAULT_COMPANY = "csc"
DEFAULT_PEERS = ["posco", "nippon", "jfe", "hyundai", "baowu", "hoaphat"]
MAX_PEERS = 6  # 主角 + 6 家 = 7 條線，不超過 8 個分類色


def _options(lang: str):
    """下拉選單選項：鋼廠依全球排名排序，礦商排最後並加註。"""
    cos = data.companies().sort_values(["role", "rank_2024"], na_position="last")
    return [{"label": pick(r, "name", lang) + ("" if r["role"] == "producer" else f" ({t('miner', lang)})"),
             "value": r["id"]} for _, r in cos.iterrows()]


def layout(lang: str, search: str = ""):
    """公司分析版面。`search` 是網址的查詢字串，例如 ?c=posco 會預選 POSCO。"""
    q = parse_qs((search or "").lstrip("?"))
    sel = q.get("c", [DEFAULT_COMPANY])[0]
    if not data.company(sel):
        sel = DEFAULT_COMPANY
    return _layout(lang, sel)


@cached()
def _layout(lang: str, sel: str):
    """實際的版面（含初始圖表），依（語言, 選定公司）快取。"""
    opts = _options(lang)
    peer_ids = tuple(p for p in DEFAULT_PEERS if p != sel)
    profile, scores, table = _main(sel, peer_ids, lang)
    return html.Div([
        html.Div([html.H2(t("nav_companies", lang))], className="page-head"),
        html.Div([
            html.Div([html.Label(t("select_company", lang), className="ctl-label"),
                      dcc.Dropdown(id="co-select", options=opts, value=sel, clearable=False, className="dd")],
                     className="ctl"),
            html.Div([html.Label(t("compare_with", lang), className="ctl-label"),
                      dcc.Dropdown(id="co-peers", options=opts, value=list(peer_ids),
                                   multi=True, className="dd")], className="ctl grow"),
        ], className="controls"),
        html.Div(profile, id="co-profile"),
        html.Div([
            card(t("scores_title", lang), dcc.Graph(id="co-scores", figure=scores, config=GRAPH_CONFIG),
                 note=t("scores_note", lang)),
            card(t("perf_title", lang),
                 dcc.RadioItems(id="co-range", options=[{"label": k, "value": k} for k in ("1Y", "3Y", "5Y")],
                                value="3Y", inline=True, className="seg"),
                 dcc.Graph(id="co-perf", figure=_perf_fig((sel,) + peer_ids, "3Y", lang),
                           config=GRAPH_CONFIG),
                 note=t("rebased_note", lang)),
        ], className="grid-2"),
        card(t("quarterly_title", lang),
             dcc.RadioItems(id="co-qmetric", value="ebitda_margin", inline=True, className="seg",
                            options=[{"label": t(k, lang), "value": k}
                                     for k in ("ebitda_margin", "operating_margin", "net_margin")]),
             dcc.Graph(id="co-quarterly", figure=_quarterly_fig((sel,) + peer_ids, "ebitda_margin", lang),
                       config=GRAPH_CONFIG),
             note=t("quarterly_note", lang)),
        card(t("peer_table", lang), html.Div(table, id="co-table"), note=t("ebitda_t_note", lang)),
        source_line(lang, "worldsteel 2024 (output); Yahoo Finance (prices, fundamentals snapshot)"),
    ])


def _num(v):
    """NaN 轉成 None，方便用 if 判斷有沒有值。"""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _profile(cid: str, pt: pd.DataFrame, lang: str):
    """上方的公司檔案卡：基本資料＋關鍵財務數字。"""
    c = data.company(cid)
    if not c:
        return None
    m = pt.loc[cid].to_dict() if cid in pt.index else {}
    out = _num(c.get("output_2024_mt"))
    fund = data.fundamentals()
    head = [html.H3(pick(c, "name", lang), className="profile-name"),
            html.Span(f"{pick(c, 'country', lang)} · {c.get('ticker') or t('unlisted', lang)}"
                      + (f" · {pick(c, 'ticker_note', lang)}" if pick(c, "ticker_note", lang) else ""),
                      className="muted")]
    if c.get("sanctions"):
        head.append(html.Div(f"⚠ {t('sanctions_flag', lang)}", className="badge-warn"))
    stats = html.Div([
        stat(t("output", lang), f"{out:,.2f} Mt" if out else "—",
             f"#{int(c['rank_2024'])} {t('rank', lang)}" if out else None),
        stat(t("route", lang), t(f"route_{c['route']}", lang) if c.get("route") else t("miner", lang)),
        stat(t("mcap", lang), an.fmt(m.get("mcap_usd_bn"), 1, " bn"), "USD"),
        stat(t("ebitda_margin", lang), an.fmt(m.get("ebitda_margin"), 1, "%")),
        stat(t("ebitda_per_t", lang), an.fmt(m.get("ebitda_per_t"), 0), t("per_t", lang)),
        stat(t("pb", lang), an.fmt(m.get("pb"), 2)),
        stat(t("debt_to_equity", lang), an.fmt(m.get("debt_to_equity"), 2, "x")),
        stat(t("div_yield", lang), an.fmt(m.get("div_yield"), 1, "%")),
        stat(t("ret_1y", lang), an.fmt(m.get("ret_1y"), 1, "%", sign=True)),
    ], className="stat-row")
    return card(None, html.Div(head, className="profile-head"), stats,
                html.P([html.B(t("products", lang) + ": "), pick(c, "products", lang)], className="small"),
                html.P(pick(c, "notes", lang), className="small muted"),
                note=f"{t('fundamentals_as_of', lang)} · {fund.get('_updated', '')[:10]}")


def _scores_fig(ids: list[str], pt: pd.DataFrame, lang: str) -> go.Figure:
    """小倍數圖：每個分數一個橫條面板。主角公司用藍色，其他用灰色。"""
    keys = ["score_health", "score_value", "score_momentum"]
    ids = [i for i in ids if i in pt.index]
    if not ids:
        return empty_fig(t("no_data", lang))
    names = {i: pick(data.company(i), "name", lang) for i in ids}
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=[t(k, lang) for k in keys])
    order = list(reversed(ids))  # 橫條圖由下往上畫，反轉後主角才會在最上面
    for j, k in enumerate(keys, start=1):
        vals = [pt.loc[i, k] for i in order]
        fig.add_trace(go.Bar(
            y=[names[i] for i in order], x=vals, orientation="h",
            marker=dict(color=[SERIES[0] if i == ids[0] else "#5f5e58" for i in order],
                        line=dict(width=0), cornerradius=4),
            text=[an.fmt(v, 0) for v in vals], textposition="outside", textfont=dict(color=COLORS["text_2"]),
            hovertemplate="%{y}: %{x:.0f}<extra></extra>", showlegend=False,
        ), row=1, col=j)
        fig.update_xaxes(range=[0, 115], showticklabels=False, row=1, col=j)
    fig.update_annotations(font=dict(color=COLORS["text_2"], size=12))
    theme(fig, height=60 + 34 * len(ids), legend=False)
    fig.update_layout(hovermode="closest", margin=dict(l=8, t=28), bargap=0.35)
    fig.update_yaxes(automargin=True)
    return fig


@cached()
def _perf_fig(ids: tuple, rng: str, lang: str) -> go.Figure:
    """股價走勢比較（指數化 = 100）。"""
    stocks = data.stock_prices()
    cos = {i: data.company(i) for i in ids}
    tick = {i: c.get("ticker") for i, c in cos.items() if isinstance(c.get("ticker"), str)}
    if stocks.empty or not tick:
        return empty_fig(t("no_data", lang))
    start = stocks.index.max() - pd.DateOffset(years=RANGES[rng])
    reb = an.downsample(an.rebased(stocks, list(tick.values()), start), RANGES[rng]).round(1)
    fig = go.Figure()
    # 顏色跟著公司在使用者清單中的位置（主角 = 第 1 色），不跟著排名變，避免切換時顏色亂跳
    for n, i in enumerate(ids):
        tk = tick.get(i)
        if tk not in reb.columns:
            continue
        fig.add_trace(go.Scatter(x=reb.index, y=reb[tk], mode="lines", name=pick(cos[i], "name", lang),
                                 line=dict(color=SERIES[n % len(SERIES)], width=2.4 if n == 0 else 1.6),
                                 hovertemplate="%{y:.0f}"))
    fig.add_hline(y=100, line=dict(color=COLORS["muted"], width=1))
    return theme(fig, height=360)


def _table(sel: str, pt: pd.DataFrame, lang: str):
    """同業比較表（可點欄位排序），主角公司那一列反白。"""
    cos = data.companies().set_index("id")
    role = cos.loc[sel, "role"] if sel in cos.index else "producer"
    df = pt[pt["role"] == role].copy()
    df.insert(0, "name", [pick(cos.loc[i], "name", lang) for i in df.index])
    cols = ["name", "output_mt", "mcap_usd_bn", "ebitda_margin", "ebitda_per_t", "roe", "pb",
            "debt_to_equity", "div_yield", "ret_1y", "score_health", "score_value", "score_momentum"]
    labels = {"name": t("select_company", lang), "output_mt": t("output", lang) + " (Mt)",
              "mcap_usd_bn": t("mcap", lang) + " (USD bn)", "ebitda_margin": t("ebitda_margin", lang) + " %",
              "ebitda_per_t": t("ebitda_per_t", lang), "roe": t("roe", lang) + " %", "pb": t("pb", lang),
              "debt_to_equity": t("debt_to_equity", lang), "div_yield": t("div_yield", lang) + " %",
              "ret_1y": t("ret_1y", lang) + " %", "score_health": t("score_health", lang),
              "score_value": t("score_value", lang), "score_momentum": t("score_momentum", lang)}
    df = df.reset_index()[["id"] + cols]
    df[cols[1:]] = df[cols[1:]].astype(float).round(1)
    df = df.sort_values("output_mt", ascending=False, na_position="last")
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": labels[c], "id": c, "type": "numeric" if c != "name" else "text"} for c in cols],
        sort_action="native", page_size=25, style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": COLORS["surface_2"], "color": COLORS["text_2"], "fontWeight": 600,
                      "border": "none", "whiteSpace": "normal", "height": "auto"},
        style_cell={"backgroundColor": COLORS["surface"], "color": COLORS["text"], "border": "none",
                    "borderBottom": f"1px solid {COLORS['border']}", "fontFamily": "inherit", "fontSize": 13,
                    "padding": "6px 10px", "textAlign": "right", "minWidth": "84px"},
        style_cell_conditional=[{"if": {"column_id": "name"}, "textAlign": "left", "minWidth": "180px"}],
        style_data_conditional=[{"if": {"filter_query": f'{{id}} = "{sel}"'},
                                 "backgroundColor": "#1c2a3d", "fontWeight": 600}],
    )


@cached()
def _quarterly_fig(ids: tuple, metric: str, lang: str) -> go.Figure:
    """各公司每季利潤率（%）。利潤率不受幣別影響，可以直接跨國比較。"""
    q = data.quarterly()
    if q.empty:
        return empty_fig(t("no_data", lang))
    num = {"ebitda_margin": "ebitda", "operating_margin": "operating_income", "net_margin": "net_income"}[metric]
    fig = go.Figure()
    for n, cid in enumerate(ids):
        c = data.company(cid)
        g = q[q["ticker"] == c.get("ticker")].sort_values("quarter_end")
        g = g[g["revenue"] > 0]
        if g.empty:
            continue
        margin = (g[num] / g["revenue"] * 100).round(1)
        fig.add_trace(go.Scatter(
            x=g["quarter_end"], y=margin, mode="lines+markers", name=pick(c, "name", lang),
            line=dict(color=SERIES[n % len(SERIES)], width=2.4 if n == 0 else 1.6), marker=dict(size=7),
            hovertemplate="%{x|%Y-Q%q}: %{y:.1f}%"))
    if not fig.data:
        return empty_fig(t("no_data", lang))
    fig.add_hline(y=0, line=dict(color=COLORS["muted"], width=1))
    theme(fig, height=340)
    fig.update_layout(yaxis=dict(ticksuffix="%"))
    return fig


@cached()
def _main(sel: str, peer_ids: tuple, lang: str):
    """公司檔案卡、同業分數圖、比較表（依選擇快取）。"""
    pt = peers()
    ids = [sel] + [p for p in peer_ids if p != sel][:MAX_PEERS]
    return _profile(sel, pt, lang), _scores_fig(ids, pt, lang), _table(sel, pt, lang)


def _ids(sel, chosen) -> tuple:
    return tuple(p for p in (chosen or []) if p != sel)[:MAX_PEERS]


def register(app):
    # 初始內容已在 layout 畫好；只有使用者改選項才觸發。語言改變時整頁會重畫，所以語言用 State
    @app.callback(Output("co-profile", "children"), Output("co-scores", "figure"), Output("co-table", "children"),
                  Input("co-select", "value"), Input("co-peers", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def update(sel, chosen, lang):
        return _main(sel, _ids(sel, chosen), lang)

    @app.callback(Output("co-perf", "figure"),
                  Input("co-select", "value"), Input("co-peers", "value"), Input("co-range", "value"),
                  State("lang", "data"), prevent_initial_call=True)
    def perf(sel, chosen, rng, lang):
        return _perf_fig((sel,) + _ids(sel, chosen), rng, lang)

    @app.callback(Output("co-quarterly", "figure"),
                  Input("co-select", "value"), Input("co-peers", "value"), Input("co-qmetric", "value"),
                  State("lang", "data"), prevent_initial_call=True)
    def quarterly(sel, chosen, metric, lang):
        return _quarterly_fig((sel,) + _ids(sel, chosen), metric, lang)
