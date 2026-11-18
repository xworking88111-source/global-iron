"""貿易壁壘：誰在對鋼鐵築牆、牆主要對著誰。

1. 自動觀察：依固定規則從資料產生的重點
2. 每年新立案件數：反傾銷＋反補貼，對中國 vs 對其他國家
3. 誰在築牆：近兩年對中國（或台灣）鋼鐵立案最多的國家
4. 最新案件：日期、申報國、類型、產品、結果

--- English ---
Trade walls: who is building walls against steel imports, and whom they target.

1. Observations: rule-based bullets generated from the data
2. New investigations per year: anti-dumping + countervailing, against China vs others
3. Who builds the walls: members opening the most cases against Chinese (or Taiwanese) steel lately
4. Latest cases: date, reporting member, type, product, outcome
"""
from __future__ import annotations

import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from core import walls as w
from core.cache import cached
from core.config import COLORS
from core.i18n import t

from .common import GRAPH_CONFIG, SERIES, card, empty_fig, source_line, stat, theme

ICONS = {"up": "▲", "down": "▼", "warn": "⚠", "info": "•"}
CN_COLOR, OTHER_COLOR = SERIES[7], SERIES[0]  # 對中國用紅，對其他國家用藍


def _years_fig(lang: str):
    yr = w.by_year(2000)
    last = w.latest_date()
    if yr.empty or last is None:
        return empty_fig(t("no_data", lang))
    fig = go.Figure()
    for col, color, key in (("China", CN_COLOR, "wl_vs_china"), ("other", OTHER_COLOR, "wl_vs_other")):
        fig.add_trace(go.Bar(x=yr.index, y=yr[col], name=t(key, lang), marker=dict(color=color, cornerradius=2),
                             hovertemplate="%{y}"))
    if last.month < 12:  # 最後一年資料不完整：在長條上方標註「1–6 月」
        fig.add_annotation(x=yr.index[-1], y=int(yr.iloc[-1].sum()), yshift=10, xanchor="right", showarrow=False,
                           text=f"1–{last.month}月" if lang == "zh" else f"Jan–{last:%b}",
                           font=dict(size=11, color=COLORS["text_2"]))
    theme(fig, height=320)
    fig.update_layout(barmode="stack", bargap=0.25, yaxis_title=t("wl_cases", lang),
                      xaxis=dict(dtick=5 if len(yr) > 15 else 1))
    return fig


def _reporters_fig(target: str, since: int, lang: str):
    r = w.reporters_against(target, since).head(12).sort_values()
    if r.empty:
        return empty_fig(t("no_data", lang))
    fig = go.Figure(go.Bar(
        x=r.values, y=[w.name(k, lang) for k in r.index], orientation="h", text=r.values, textposition="outside",
        textfont=dict(color=COLORS["text_2"]), marker=dict(color=CN_COLOR if target == "China" else SERIES[2], cornerradius=3),
        hovertemplate="%{y}: %{x}<extra></extra>"))
    theme(fig, height=max(220, 28 * len(r) + 60), legend=False)
    fig.update_layout(hovermode="closest", xaxis=dict(title=t("wl_cases", lang), range=[0, r.max() * 1.2],
                                                 dtick=1 if r.max() <= 10 else None))  # 件數是整數，不要出現 0.5
    fig.update_traces(cliponaxis=False)
    return fig


def _recent_table(target: str, lang: str):
    """最新案件清單：每件一行摘要（日期、申報國、類型、結果）＋產品名稱。手機上比表格好讀。"""
    df = w.recent(target, 15)
    if df.empty:
        return html.P(t("no_data", lang))
    status = {"affirmative": "wl_st_aff", "negative": "wl_st_neg", "withdrawn": "wl_st_wd"}
    items = []
    for r in df.itertuples():
        st = status.get(r.conclusion, "wl_st_open")
        product = r.product if len(r.product) <= 140 else r.product[:137] + "…"
        items.append(html.Li([
            html.Div([html.Span(f"{r.initiated:%Y-%m-%d}"), html.B(w.name(r.reporter, lang)),
                      html.Span(t("wl_ad", lang) if r.type == "AD" else t("wl_cvd", lang)),
                      html.Span(t(st, lang), className="tag" + (" open" if st == "wl_st_open" else ""))],
                     className="case-meta"),
            html.Div(product, className="case-product"),
        ]))
    return html.Ul(items, className="case-list")


@cached()
def build(target_key: str, lang: str):
    """依「被調查國」切換：築牆國家圖、圖標題、最新案件表。"""
    target = w.TARGETS.get(target_key, "China")
    last = w.latest_date()
    since = (last.year - 1) if last is not None else 2025
    title = t("wl_who_title", lang).format(target=w.name(target, lang), since=since)
    return _reporters_fig(target, since, lang), title, _recent_table(target, lang)


@cached()
def layout(lang: str):
    """貿易壁壘頁。"""
    obs = w.observations()
    obs_box = html.Div([
        html.H3(t("wl_obs_title", lang), className="card-title"),
        html.Ul([html.Li([html.Span(ICONS[tone], className=f"hl-icon {tone}"), html.Span(zh if lang == "zh" else en)])
                 for tone, zh, en in obs], className="hl-list"),
    ], className="gi-card highlights") if obs else None

    yr, last = w.by_year(2000), w.latest_date()
    stats = None
    if not yr.empty and last is not None:
        full = [y for y in yr.index if y < last.year or last.month == 12]
        y = full[-1]
        tot, cn = int(yr.loc[y].sum()), int(yr.loc[y, "China"])
        avg = yr.loc[[v for v in yr.index if y - 10 <= v < y]].sum(axis=1).mean()
        stats = html.Div([
            stat(t("wl_stat_total", lang).format(y=y), f"{tot}", t("wl_stat_avg", lang).format(avg=avg)),
            stat(t("wl_stat_china", lang).format(y=y), f"{cn / tot:.0%}", t("wl_stat_china_sub", lang).format(n=cn)),
            stat(t("wl_stat_latest", lang), f"{last:%Y-%m-%d}", t("wl_stat_latest_sub", lang)),
        ], className="stat-row")

    fig_r, who_title, table = build("cn", lang)
    target_ctrl = html.Div([
        html.Span(t("wl_target", lang), className="ctl-label"),
        dcc.RadioItems(id="wl-target", value="cn", inline=True, className="seg",
                       options=[{"label": w.name(v, lang), "value": k} for k, v in w.TARGETS.items()]),
    ], className="controls")

    return html.Div([
        html.Div([html.H2(t("nav_walls", lang))], className="page-head"),
        html.P(t("wl_intro", lang), className="muted"),
        obs_box,
        card(t("wl_years_title", lang), stats, dcc.Graph(figure=_years_fig(lang), config=GRAPH_CONFIG),
             note=t("wl_years_note", lang)),
        card(None, target_ctrl,
             html.H3(who_title, id="wl-who-title", className="card-title"),
             dcc.Graph(id="wl-who", figure=fig_r, config=GRAPH_CONFIG),
             html.H3(t("wl_recent_title", lang), className="card-title"),
             html.Div(table, id="wl-recent"),
             note=t("wl_recent_note", lang)),
        source_line(lang, t("wl_source", lang)),
    ])


def register(app) -> None:
    @app.callback(Output("wl-who", "figure"), Output("wl-who-title", "children"), Output("wl-recent", "children"),
                  Input("wl-target", "value"), State("lang", "data"), prevent_initial_call=True)
    def _switch(target, lang):
        return build(target or "cn", lang or "zh")
