"""情境模擬：調整熱軋／鐵礦／焦炭價格，看對某家鋼廠利潤的影響。"""
from __future__ import annotations

import math

import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from core import analytics as an
from core import data
from core.cache import cached
from core.config import COLORS
from core.i18n import pick, t

from .common import SERIES, card, empty_fig, stat, theme

DEFAULT_OTHER_COST = 100  # 美元/噸：一貫作業鋼廠原料以外的加工成本粗估


def _mills(lang: str):
    """有產量資料的鋼廠清單（情境需要年產量）。"""
    cos = data.companies()
    cos = cos[(cos["role"] == "producer") & cos["output_2024_mt"].notna()].sort_values("rank_2024")
    return [{"label": f"{pick(r, 'name', lang)} ({r['output_2024_mt']:.1f} Mt)", "value": r["id"]}
            for _, r in cos.iterrows()]


def _slider(id_: str):
    """-30% 到 +30% 的價格變動滑桿。"""
    return dcc.Slider(id=id_, min=-30, max=30, step=1, value=0,
                      marks={v: f"{v:+d}%" if v else "0" for v in range(-30, 31, 10)},
                      tooltip={"placement": "bottom", "always_visible": False}, className="slider")


@cached()
def layout(lang: str):
    stats, wf, sb = compute("csc", "intl", 0, 0, 0, DEFAULT_OTHER_COST, lang)  # 初始結果直接畫好
    return html.Div([
        html.Div([html.H2(t("scn_title", lang))], className="page-head"),
        html.P(t("scn_intro", lang), className="muted"),
        html.Div([
            card(None,
                 html.Label(t("scn_mill", lang), className="ctl-label"),
                 dcc.Dropdown(id="scn-mill", options=_mills(lang), value="csc", clearable=False, className="dd"),
                 html.Label(t("scn_base_market", lang), className="ctl-label"),
                 dcc.RadioItems(id="scn-basis", value="intl", className="seg-v",
                                options=[{"label": t("scn_basis_intl", lang), "value": "intl"},
                                         {"label": t("scn_basis_cn", lang), "value": "cn"}]),
                 html.Label(t("scn_hrc", lang), className="ctl-label"), _slider("scn-hrc"),
                 html.Label(t("scn_ore", lang), className="ctl-label"), _slider("scn-ore"),
                 html.Label(t("scn_coke", lang), className="ctl-label"), _slider("scn-coke"),
                 html.Label(t("scn_other", lang), className="ctl-label"),
                 dcc.Input(id="scn-other", type="number", value=DEFAULT_OTHER_COST, min=0, max=500, step=10,
                           className="num-input"),
                 className="scn-controls"),
            html.Div([
                html.Div(stats, id="scn-stats"),
                html.Div([
                    card(None, dcc.Graph(id="scn-waterfall", figure=wf, config={"displayModeBar": False})),
                    card(t("scn_sens", lang), dcc.Graph(id="scn-sens", figure=sb, config={"displayModeBar": False})),
                ], className="grid-2"),
            ], className="scn-out"),
        ], className="scn-wrap"),
        html.P(t("scn_caveat", lang), className="card-note"),
    ])


def _base_prices(basis: str) -> dict | None:
    """最新價格換算成美元/公噸。basis="intl" 時鐵礦改用海運 62% 價格。"""
    px = data.prices()
    need = ["cn_hrc", "cn_ore", "cn_coke", "fx_cny"]
    if px.empty or any(c not in px for c in need):
        return None
    last = px[need + (["ore_62"] if "ore_62" in px else [])].ffill().iloc[-1]
    fx = last["fx_cny"]
    base = {"hrc": last["cn_hrc"] / fx, "ore": last["cn_ore"] / fx, "coke": last["cn_coke"] / fx}
    if basis == "intl" and "ore_62" in last and not math.isnan(last["ore_62"]):
        base["ore"] = float(last["ore_62"])
    return {k: float(v) for k, v in base.items()}


def register(app):
    # 初始結果已在 layout 畫好；只有使用者調整才觸發
    @app.callback(Output("scn-stats", "children"), Output("scn-waterfall", "figure"), Output("scn-sens", "figure"),
                  Input("scn-mill", "value"), Input("scn-basis", "value"), Input("scn-hrc", "value"),
                  Input("scn-ore", "value"), Input("scn-coke", "value"), Input("scn-other", "value"),
                  State("lang", "data"), prevent_initial_call=True)
    def update(mill, basis, d_hrc, d_ore, d_coke, other, lang):
        return compute(mill, basis, d_hrc, d_ore, d_coke, other, lang)


@cached(maxsize=512)
def compute(mill, basis, d_hrc, d_ore, d_coke, other, lang):
    """情境計算＋三個輸出（數字方塊、瀑布圖、敏感度圖）。同樣的輸入直接用快取結果。"""
    base = _base_prices(basis)
    if base is None:
        e = empty_fig(t("no_data", lang))
        return None, e, e
    c = data.company(mill)
    out_mt = float(c.get("output_2024_mt") or 0)
    other = float(other or 0)
    r = an.scenario(base, {"hrc": d_hrc or 0, "ore": d_ore or 0, "coke": d_coke or 0}, out_mt, other)

    stats = html.Div([
        stat(t("scn_margin_base", lang), an.fmt(r["margin_base"], 0), t("per_t", lang)),
        stat(t("scn_margin_new", lang), an.fmt(r["margin_new"], 0),
             f"{an.fmt(r['margin_delta'], 0, sign=True)} {t('per_t', lang)}"),
        stat(t("scn_annual", lang), an.fmt(r["annual_delta_usd_m"], 0, sign=True), t("usd_m", lang)),
        stat(t("output", lang), f"{out_mt:,.2f} Mt", pick(c, "name", lang)),
    ], className="stat-row")

    # 瀑布圖：售價 → 逐項扣成本 → 每噸利潤（情境價格）
    p = r["new_prices"]
    steps = [(t("kpi_cn_hrc", lang), p["hrc"]), (f"{t('kpi_ore', lang)} ×1.6", -1.6 * p["ore"]),
             (f"{t('kpi_coke', lang)} ×0.5", -0.5 * p["coke"]), (t("scn_other_short", lang), -other)]
    wf = go.Figure(go.Waterfall(
        x=[s[0] for s in steps] + [t("scn_margin_short", lang)], y=[s[1] for s in steps] + [0],
        measure=["absolute", "relative", "relative", "relative", "total"],
        text=[an.fmt(s[1], 0) for s in steps] + [an.fmt(r["margin_new"], 0)], textposition="outside",
        textfont=dict(color=COLORS["text_2"]),
        increasing=dict(marker=dict(color=SERIES[0])), decreasing=dict(marker=dict(color=SERIES[7])),
        totals=dict(marker=dict(color=SERIES[2])), connector=dict(line=dict(color=COLORS["border"], width=1)),
        hovertemplate="%{x}: %{y:,.0f} USD/t<extra></extra>",
    ))
    theme(wf, height=320, legend=False)
    wf.update_layout(hovermode="closest", yaxis_title=t("per_t", lang))
    wf.update_traces(cliponaxis=False)

    # 敏感度橫條：發散配色（藍 = 有利利潤，紅 = 不利）
    sens = r["sens_per_1pct"]
    labels = [t("scn_hrc", lang), t("scn_ore", lang), t("scn_coke", lang)]
    vals = [sens["hrc"], sens["ore"], sens["coke"]]
    sb = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h", text=[f"{v:+,.0f}" for v in vals], textposition="outside",
        textfont=dict(color=COLORS["text_2"]),
        marker=dict(color=[SERIES[0] if v >= 0 else SERIES[7] for v in vals], cornerradius=4),
        hovertemplate="+1%: %{x:+,.0f} " + t("usd_m", lang) + "<extra></extra>",
    ))
    theme(sb, height=320, legend=False)
    lim = max(abs(v) for v in vals) * 1.6 or 1
    sb.update_layout(hovermode="closest", xaxis=dict(range=[-lim, lim], title=t("usd_m", lang)))
    sb.update_yaxes(automargin=True)
    sb.update_traces(cliponaxis=False)
    return stats, wf, sb
