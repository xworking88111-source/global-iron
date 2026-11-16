"""貿易與風險：誰賣鋼給誰、淨出口國、鐵礦依賴度、咽喉要道清單、政策時間軸。
主要給地緣政治研究者與航運保險從業者使用。
"""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dash_table, dcc, html

from core import data
from core.cache import cached
from core.config import COLORS
from core.i18n import pick, t

from .common import SERIES, card, source_line, stat, theme

# 熱力圖用的單一藍色深淺色階（數值越大越亮）
SEQ_BLUE = [[0, "#1a1a19"], [0.15, "#184f95"], [0.5, "#2a78d6"], [1, "#9ec5f4"]]


@cached()
def layout(lang: str):
    """這頁內容只跟語言有關（沒有互動選項），所以整頁一次畫好並快取。"""
    ws = data.worldsteel()
    world = ws.get("world_crude_steel", {}).get("2024")
    china = next((c["p2024"] for c in ws.get("country_production", []) if c["iso3"] == "CHN"), None)
    share = f"{china / world * 100:.1f}%" if world and china else "—"
    china_net = next((r["net"] for r in ws.get("steel_net_exports", []) if r["iso3"] == "CHN"), None)
    return html.Div([
        html.Div([html.H2(t("risk_title", lang))], className="page-head"),
        html.Div([
            stat(t("china_share", lang), share, "2024"),
            stat(t("world_output", lang), f"{world:,.0f} Mt" if world else "—", "2024"),
            stat(t("china_net_exports", lang), f"+{china_net:,.1f} Mt" if china_net else "—", "2024"),
        ], className="stat-row"),
        html.Div([
            card(t("trade_matrix", lang),
                 # 矩陣有 10 欄，手機上壓縮會擠成一團：給最小寬度，窄螢幕改為左右滑動
                 html.Div(dcc.Graph(id="rk-matrix", figure=_matrix_fig(lang), config={"displayModeBar": False}, style={"minWidth": "560px"}),
                          className="scroll-x")),
            card(t("net_exports", lang), dcc.Graph(id="rk-net", figure=_net_fig(lang), config={"displayModeBar": False})),
        ], className="grid-2"),
        html.Div([
            card(t("ore_trade", lang), dcc.Graph(id="rk-ore", figure=_ore_fig(lang), config={"displayModeBar": False})),
            card(t("country_output", lang), dcc.Graph(id="rk-country", figure=_country_fig(lang), config={"displayModeBar": False})),
        ], className="grid-2"),
        card(t("chokepoint_table", lang), html.Div(_choke_table(lang), id="rk-choke"), note=t("risk_review_note", lang)),
        card(t("timeline", lang), html.Div(_timeline_table(lang), id="rk-timeline")),
        source_line(lang, "worldsteel, World Steel in Figures 2025; curated chokepoint and event registers"),
    ])


def _matrix_fig(lang):
    """貿易矩陣熱力圖：列 = 進口地區，欄 = 出口地區。"""
    ws = data.worldsteel()
    regs, exps, mat = ws["trade_regions"], ws["trade_exporters"], ws["trade_matrix"]
    importers = list(mat.keys())
    z, txt = [], []
    for imp in importers:
        row, trow = [], []
        for exp, v in zip(exps, mat[imp]):
            intra = exp == imp or (exp == "AFME" and imp in ("AFR", "ME"))
            row.append(None if intra or not v else v)   # 區域內貿易留白（例如歐盟內部互賣）
            trow.append("" if intra or not v or v < 1 else f"{v:.0f}")
        z.append(row)
        txt.append(trow)
    short = lambda k: regs[k][lang].split("（")[0].split(" (")[0]  # noqa: E731  去掉括號說明，軸標籤才不會太長
    fig = go.Figure(go.Heatmap(
        z=z, x=[short(e) for e in exps], y=[short(i) for i in importers], text=txt, texttemplate="%{text}",
        textfont=dict(color=COLORS["text"], size=11), colorscale=SEQ_BLUE, showscale=False, xgap=2, ygap=2,
        hovertemplate=f"{t('exporter', lang)}: %{{x}}<br>{t('importer', lang)}: %{{y}}<br>%{{z:.1f}} Mt<extra></extra>",
    ))
    theme(fig, height=420, legend=False)
    fig.update_layout(hovermode="closest", xaxis=dict(title=t("exporter", lang), side="top", tickangle=-35),
                      yaxis=dict(title=t("importer", lang), autorange="reversed"), margin=dict(t=90))
    return fig


def _net_fig(lang):
    """淨出口（藍）／淨進口（紅）橫條圖。"""
    rows = sorted(data.worldsteel()["steel_net_exports"], key=lambda r: r["net"])
    vals = [r["net"] for r in rows]
    fig = go.Figure(go.Bar(
        x=vals, y=[r[lang] for r in rows], orientation="h",
        marker=dict(color=[SERIES[0] if v >= 0 else SERIES[7] for v in vals], cornerradius=4),
        text=[f"{v:+.1f}" for v in vals], textposition="outside", textfont=dict(color=COLORS["text_2"]),
        hovertemplate="%{y}: %{x:+.1f} Mt<extra></extra>",
    ))
    theme(fig, height=420, legend=False)
    fig.update_layout(hovermode="closest", xaxis=dict(range=[-32, 135], title="Mt"))
    fig.update_traces(cliponaxis=False)
    return fig


def _ore_fig(lang):
    """鐵礦：各國產量、出口、進口並排比較。"""
    ore = data.worldsteel()["iron_ore_2024"]["rows"]
    ore = sorted(ore, key=lambda r: max(r["production"], r["imports"]))
    fig = go.Figure()
    for i, k in enumerate(["production", "exports", "imports"]):
        fig.add_trace(go.Bar(y=[r[lang] for r in ore], x=[r[k] for r in ore], orientation="h", name=t(k, lang),
                             marker=dict(color=SERIES[i], cornerradius=3, line=dict(width=0)),
                             hovertemplate="%{y} · " + t(k, lang) + ": %{x:,.0f} Mt<extra></extra>"))
    theme(fig, height=420)
    fig.update_layout(barmode="group", hovermode="closest", bargap=0.25, bargroupgap=0.1, xaxis_title="Mt")
    return fig


def _country_fig(lang):
    """前 15 大產鋼國，台灣用白色標出。"""
    cp = sorted(data.worldsteel()["country_production"], key=lambda r: -r["p2024"])[:15][::-1]
    fig = go.Figure(go.Bar(
        x=[r["p2024"] for r in cp], y=[r[lang] for r in cp], orientation="h",
        marker=dict(color=[COLORS["text"] if r["iso3"] == "TWN" else SERIES[0] for r in cp], cornerradius=4),
        text=[f"{r['p2024']:,.0f}" for r in cp], textposition="outside", textfont=dict(color=COLORS["text_2"]),
        customdata=[(r["p2024"] / r["p2023"] - 1) * 100 for r in cp],
        hovertemplate="%{y}: %{x:,.1f} Mt (%{customdata:+.1f}% y/y)<extra></extra>",
    ))
    theme(fig, height=420, legend=False)
    # 刻意用線性座標：中國和其他國家的規模差距本身就是重點
    fig.update_layout(hovermode="closest", xaxis=dict(title="Mt", range=[0, 1150]))
    fig.update_traces(cliponaxis=False)
    return fig


def _table(rows, cols, labels, wrap=True, markdown=()):
    """深色樣式的資料表（可排序、長文字自動換行）。markdown 欄位可以放連結。"""
    return dash_table.DataTable(
        data=rows, style_as_list_view=True, markdown_options={"link_target": "_blank"},
        columns=[{"name": labels[c], "id": c, **({"presentation": "markdown"} if c in markdown else {})}
                 for c in cols],
        sort_action="native", page_size=20,
        style_header={"backgroundColor": COLORS["surface_2"], "color": COLORS["text_2"], "fontWeight": 600, "border": "none"},
        style_cell={"backgroundColor": COLORS["surface"], "color": COLORS["text"], "border": "none",
                    "borderBottom": f"1px solid {COLORS['border']}", "fontFamily": "inherit", "fontSize": 13,
                    "padding": "8px 10px", "textAlign": "left",
                    "whiteSpace": "normal" if wrap else "nowrap", "height": "auto", "maxWidth": "420px"},
    )


def _choke_table(lang):
    """咽喉要道表。"""
    geo = data.geo_layers()
    chokes = [{"name": pick(c, "", lang), "relevance": pick(c, "relevance", lang), "risks": pick(c, "risks", lang),
               # 官方即時公告連結（點開看最新狀態；本站不轉載內容）
               "advisories": " · ".join(f"[{a['name']}]({a['url']})" for a in c.get("advisories", [])) or "—"}
              for c in geo.get("chokepoints", [])]
    return _table(chokes, ["name", "relevance", "risks", "advisories"],
                  {"name": t("layer_chokepoints", lang), "relevance": t("relevance", lang), "risks": t("risks", lang),
                   "advisories": t("advisories", lang)}, markdown=("advisories",))


def _timeline_table(lang):
    """政策與事件時間軸（新到舊）。"""
    ev = data.events()
    cats = data.event_categories()
    rows = [{"date": r["date"].strftime("%Y-%m" if r["precision"] == "month" else "%Y-%m-%d"),
             "category": pick(cats.get(r["cat"], {}), "", lang), "event": pick(r, "", lang)}
            for _, r in ev.sort_values("date", ascending=False).iterrows()]
    return _table(rows, ["date", "category", "event"],
                  {"date": t("date", lang), "category": t("category", lang), "event": t("event", lang)})
