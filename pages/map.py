"""全球地圖：鋼廠、礦商、港口、航線、咽喉要道、貿易流、AIS 船位。

使用 Plotly 的 `scattergeo`（向量世界地圖，不需要圖磚伺服器或 API 金鑰）。
每個圖層是獨立的 trace，右側勾選清單才能逐一開關。
"""
from __future__ import annotations

import math

import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from core import analytics as an
from core import data
from core.cache import cached
from core.config import COLORS, ROUTE_COLOR
from core.i18n import ownership_label, pick, t

from .common import SERIES, card, peers, source_line

# 所有圖層與預設開啟的圖層
LAYERS = ["producers", "miners", "routes", "chokepoints", "ports", "country", "trade", "ais"]
DEFAULT_LAYERS = ["producers", "miners", "routes", "chokepoints", "country"]

# 航線樣式：顏色＋虛實線，讓航線不只靠顏色區分
ROUTE_STYLE = {
    "ore": dict(color=SERIES[3], dash="solid"),
    "coal": dict(color=SERIES[6], dash="dot"),
    "steel": dict(color=SERIES[4], dash="solid"),
    "diversion": dict(color=SERIES[4], dash="dash"),
}
PORT_SYMBOL = {"ore_export": "square", "coal_export": "square-open", "ore_import": "circle-open"}


@cached()
def layout(lang: str):
    """地圖版面，預設圖層的地圖直接畫好（不用等第二趟請求）。"""
    return html.Div([
        html.Div([html.H2(t("map_title", lang))], className="page-head"),
        html.Div([
            html.Div([
                # 關掉滾輪縮放：否則捲動頁面經過地圖時會誤觸縮放。改用右上角的放大／縮小／重設按鈕
                dcc.Graph(id="map-graph", figure=build_figure(tuple(DEFAULT_LAYERS), lang),
                          style={"height": "68vh"}, config={
                    "scrollZoom": False, "displaylogo": False, "displayModeBar": True,
                    "modeBarButtonsToRemove": ["toImage", "pan2d", "select2d", "lasso2d", "hoverClosestGeo"],
                }),
            ], className="map-main"),
            html.Div([
                card(t("layers", lang), dcc.Checklist(
                    id="map-layers", value=DEFAULT_LAYERS, className="layer-list",
                    options=[{"label": t(f"layer_{k}", lang), "value": k} for k in LAYERS])),
                html.Div(id="map-detail", children=card(None, html.P(t("click_hint", lang), className="muted"))),
                html.Div(id="map-ais-summary"),
            ], className="map-side"),
        ], className="map-wrap"),
        html.P(t("size_by", lang), className="card-note"),
        source_line(lang, "worldsteel 2024 (output, trade); curated coordinates; AISStream.io (vessels)"),
    ])


# ---------------------------------------------------------------------------
# 地圖繪製
# ---------------------------------------------------------------------------
def _bubble_size(mt) -> float:
    """泡泡大小：直徑與產量的平方根成正比，面積才會和產量成正比。產量不明時用固定小尺寸。"""
    if mt is None or (isinstance(mt, float) and math.isnan(mt)):
        return 7
    return 6 + 3.2 * math.sqrt(mt)


@cached()
def build_figure(layers: tuple, lang: str) -> go.Figure:
    """依勾選的圖層組出整張地圖。圖層由下往上疊：底色 → 線 → 點。"""
    fig = go.Figure()
    geo = data.geo_layers()
    ws = data.worldsteel()
    cos = data.companies()

    # 1. 各國粗鋼產量底色（單一色相深淺；取平方根，避免中國把其他國家都壓成同一色）
    if "country" in layers:
        cp = ws.get("country_production", [])
        fig.add_trace(go.Choropleth(
            locations=[c["iso3"] for c in cp], z=[math.sqrt(c["p2024"]) for c in cp],
            text=[f"{c[lang]}: {c['p2024']:,.1f} Mt" for c in cp], hoverinfo="text",
            colorscale=[[0, "#1c2a3d"], [0.5, "#1c5cab"], [1, "#6da7ec"]], showscale=False,
            marker_line_color=COLORS["border"], marker_line_width=0.4, name=t("layer_country", lang),
        ))

    # 2. 海運航線
    if "routes" in layers:
        seen = set()
        for r in geo.get("routes", []):
            st = ROUTE_STYLE.get(r["kind"], ROUTE_STYLE["steel"])
            lats, lons = zip(*r["points"])
            fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode="lines", name=t(f"route_{r['kind']}", lang),
                legendgroup=r["kind"], showlegend=r["kind"] not in seen,
                line=dict(width=1.6, color=st["color"], dash=st["dash"]), opacity=0.75,
                hoverinfo="text", text=pick(r, "", lang),
            ))
            seen.add(r["kind"])

    # 3. 區域間鋼材貿易流（只畫量最大的 14 條，避免太亂）
    if "trade" in layers:
        regions = ws["trade_regions"]
        flows = []
        for imp, row in ws["trade_matrix"].items():
            for exp, v in zip(ws["trade_exporters"], row):
                same = exp == imp or (exp == "AFME" and imp in ("AFR", "ME"))
                if v and not same:
                    flows.append((v, exp, imp))
        flows.sort(reverse=True)
        vmax = flows[0][0] if flows else 1
        for i, (v, exp, imp) in enumerate(flows[:14]):
            a, b = regions[exp], regions[imp]
            fig.add_trace(go.Scattergeo(
                lat=[a["lat"], b["lat"]], lon=[a["lon"], b["lon"]], mode="lines",
                line=dict(width=1 + 7 * v / vmax, color=COLORS["text_2"]), opacity=0.45,
                name=t("layer_trade", lang), legendgroup="trade", showlegend=i == 0,
                hoverinfo="text", text=f"{a[lang]} → {b[lang]}: {v:.1f} {t('flow_label', lang)}",
            ))

    # 4. 港口
    if "ports" in layers:
        ports = geo.get("ports", [])
        for kind in PORT_SYMBOL:
            ps = [p for p in ports if p["kind"] == kind]
            fig.add_trace(go.Scattergeo(
                lat=[p["lat"] for p in ps], lon=[p["lon"] for p in ps], mode="markers",
                marker=dict(size=7, symbol=PORT_SYMBOL[kind], color=COLORS["text"], line=dict(width=1, color=COLORS["text"])),
                name=t(f"port_{kind}", lang), hoverinfo="text",
                text=[f"{pick(p, '', lang)}<br>{t('port_' + kind, lang)}" for p in ps],
            ))

    # 5. 咽喉要道（用警示狀態色＋文字標籤，表示這是風險點）
    if "chokepoints" in layers:
        cps = geo.get("chokepoints", [])
        fig.add_trace(go.Scattergeo(
            lat=[c["lat"] for c in cps], lon=[c["lon"] for c in cps], mode="markers+text",
            marker=dict(size=11, symbol="triangle-up", color=COLORS["warning"], line=dict(width=1, color=COLORS["surface"])),
            text=[pick(c, "", lang) for c in cps], textposition="bottom center",
            textfont=dict(size=9, color=COLORS["muted"]),
            name=t("layer_chokepoints", lang),
            customdata=[f"{pick(c, '', lang)}<br><b>{t('relevance', lang)}:</b> {pick(c, 'relevance', lang)}"
                        f"<br><b>{t('risks', lang)}:</b> {pick(c, 'risks', lang)}" for c in cps],
            hovertemplate="%{customdata}<extra></extra>",
        ))

    # 6. 鋼廠：每種製程一個 trace（3 種分類色）
    if "producers" in layers:
        prod = cos[cos["role"] == "producer"]
        for route in ("BF", "EAF", "MIX"):
            g = prod[prod["route"] == route]
            fig.add_trace(go.Scattergeo(
                lat=g["lat"], lon=g["lon"], mode="markers", name=t(f"route_{route}", lang),
                marker=dict(size=[_bubble_size(v) for v in g["output_2024_mt"]], color=ROUTE_COLOR[route],
                            opacity=0.85,
                            # 泡泡外加一圈底色描邊，重疊時才分得開；中鋼用亮白色外框強調
                            line=dict(width=[3 if h else 1.5 for h in g["highlight"]],
                                      color=[COLORS["text"] if h else COLORS["surface"] for h in g["highlight"]])),
                customdata=g["id"],
                text=[_hover_company(r, lang) for _, r in g.iterrows()],
                hovertemplate="%{text}<extra></extra>",
            ))

    # 7. 鐵礦商
    if "miners" in layers:
        m = cos[cos["role"] == "miner"]
        fig.add_trace(go.Scattergeo(
            lat=m["lat"], lon=m["lon"], mode="markers", name=t("miner", lang),
            marker=dict(size=13, symbol="diamond", color=COLORS["text_2"], line=dict(width=1.5, color=COLORS["surface"])),
            customdata=m["id"], text=[_hover_company(r, lang) for _, r in m.iterrows()],
            hovertemplate="%{text}<extra></extra>",
        ))

    # 8. 最新 AIS 快照中的船舶：一般貨船用小點，追蹤船隊（例如中鋼運通）用醒目的大標記
    if "ais" in layers:
        snap = data.ais_snapshot()
        ships = snap.get("vessels", [])

        def ship_text(s):
            name = s.get("name") or s["mmsi"]
            if s.get("tracked") and lang == "zh" and s.get("name_zh"):
                name = f"{s['name_zh']}（{name}）"
            op = s.get(f"operator_{lang}") or s.get("operator_en")
            return (f"<b>{name}</b>" + (f"<br>{op}" if op else "")
                    + f"<br>{s.get('zone') or '—'} · {s.get('sog', '—')} kn"
                    + f"<br>→ {s.get('destination') or '—'}<br>{(s.get('time') or '')[:16]}")

        others = [s for s in ships if not s.get("tracked")]
        fleet = [s for s in ships if s.get("tracked")]
        if others:
            fig.add_trace(go.Scattergeo(
                lat=[s["lat"] for s in others], lon=[s["lon"] for s in others], mode="markers",
                marker=dict(size=4, color=SERIES[2], opacity=0.8), name=t("layer_ais", lang),
                hoverinfo="text", text=[ship_text(s) for s in others],
            ))
        if fleet:
            fig.add_trace(go.Scattergeo(
                lat=[s["lat"] for s in fleet], lon=[s["lon"] for s in fleet], mode="markers",
                marker=dict(size=12, symbol="star", color=COLORS["text"], line=dict(width=1.5, color=SERIES[0])),
                name=t("layer_fleet", lang), hoverinfo="text", text=[ship_text(s) for s in fleet],
            ))

    fig.update_geos(
        # 米勒投影並裁掉兩極：比整顆地球的投影更能填滿版面，也不會讓極區佔掉大片空間。
        projection_type="miller", showframe=False, showcoastlines=True,
        coastlinecolor=COLORS["border"], showland=True, landcolor="#262624", showocean=True,
        oceancolor="#141413", showcountries=True, countrycolor=COLORS["border"], countrywidth=0.4,
        showlakes=False, bgcolor=COLORS["surface"],
        lataxis_range=[-42, 70], lonaxis_range=[-128, 165],
    )
    fig.update_layout(
        paper_bgcolor=COLORS["surface"], margin=dict(l=0, r=0, t=0, b=0),
        font=dict(color=COLORS["text_2"], family="Inter, 'Noto Sans TC', system-ui, sans-serif"),
        legend=dict(orientation="h", y=0.0, x=0.0, yanchor="top", bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hoverlabel=dict(bgcolor=COLORS["surface_2"], bordercolor=COLORS["border"], font_color=COLORS["text"]),
        uirevision="keep",  # 切換圖層時保留使用者的縮放與平移
    )
    return fig


def _hover_company(r, lang: str) -> str:
    """滑鼠停在公司泡泡上時顯示的文字。⚠ 表示有制裁曝險。"""
    out = r.get("output_2024_mt")
    out_s = f"{out:,.1f} Mt (#{int(r['rank_2024'])})" if isinstance(out, float) and not math.isnan(out) else "—"
    flag = " ⚠" if r.get("sanctions") else ""
    return f"<b>{pick(r, 'name', lang)}</b>{flag}<br>{pick(r, 'country', lang)}<br>{t('output', lang)}: {out_s}"


# ---------------------------------------------------------------------------
# 右側詳情面板
# ---------------------------------------------------------------------------
def company_panel(cid: str, lang: str):
    """點擊公司泡泡後，右側顯示的公司摘要。"""
    c = data.company(cid)
    if not c:
        return card(None, html.P(t("click_hint", lang), className="muted"))
    pt = peers()
    m = pt.loc[cid].to_dict() if cid in pt.index else {}
    out = c.get("output_2024_mt")
    has_out = isinstance(out, (int, float)) and not math.isnan(out)
    rows = [
        (t("country", lang), pick(c, "country", lang)),
        (t("rank", lang), f"#{int(c['rank_2024'])}" if has_out else "—"),
        (t("output", lang), f"{out:,.2f} Mt" if has_out else "—"),
        (t("route", lang), t(f"route_{c['route']}", lang) if c.get("route") else t("miner", lang)),
        (t("ownership", lang), ownership_label(c.get("ownership"), lang)),
        (t("ticker", lang), c.get("ticker") or t("unlisted", lang)),
        (t("mcap", lang), an.fmt(m.get("mcap_usd_bn"), 1, " bn USD")),
        (t("ebitda_margin", lang), an.fmt(m.get("ebitda_margin"), 1, "%")),
        (t("pb", lang), an.fmt(m.get("pb"), 2)),
        (t("ret_1y", lang), an.fmt(m.get("ret_1y"), 1, "%", sign=True)),
    ]
    body = [html.Table([html.Tr([html.Td(k, className="k"), html.Td(v, className="v")]) for k, v in rows],
                       className="kv")]
    if c.get("sanctions"):
        body.insert(0, html.Div(f"⚠ {t('sanctions_flag', lang)}", className="badge-warn"))
    body.append(html.P(pick(c, "products", lang), className="small"))
    body.append(html.P(pick(c, "notes", lang), className="small muted"))
    body.append(dcc.Link("→ " + t("nav_companies", lang), href=f"/companies?c={cid}", className="link"))
    return card(pick(c, "name", lang), *body)


def ais_summary(lang: str):
    """AIS 圖層開啟時，右側顯示各區域的船數統計。"""
    snap = data.ais_snapshot()
    if not snap:
        return card(t("ais_summary", lang), html.P(t("ais_none", lang), className="small muted"))
    zones = snap.get("zone_counts", {})
    cargo = snap.get("cargo_counts", {})
    # 「已確認貨船 / 全部」：很多船在收聽期間還沒回報船型，所以全部數字會偏高
    rows = [html.Tr([html.Td(z), html.Td(f"{cargo.get(z, 0)} / {n}", className="v")])
            for z, n in sorted(zones.items(), key=lambda x: -x[1])]
    fleet = [s for s in snap.get("vessels", []) if s.get("tracked")]
    fleet_rows = [html.Tr([html.Td(s.get("name_zh") if lang == "zh" and s.get("name_zh") else s.get("name")),
                           html.Td(s.get("zone") or f"{s['lat']:.1f}, {s['lon']:.1f}", className="v")]) for s in fleet]
    parts = [html.P(f"{len(snap.get('vessels', []))} {t('ais_vessels', lang)}", className="small"),
             html.Table([html.Tr([html.Th(t("zone", lang)), html.Th(t("vessels_cargo_all", lang))])] + rows, className="kv"),
             html.P(t("ais_coverage_note", lang), className="card-note")]
    if fleet_rows:
        parts += [html.H3(t("layer_fleet", lang), className="card-title"),
                  html.Table(fleet_rows, className="kv")]
    return card(f"{t('ais_summary', lang)} · {snap.get('collected_at', '')[:16]} UTC", *parts)


def register(app):
    # 初始狀態已在 layout 畫好，所以三個 callback 都設 prevent_initial_call；語言改變時整頁會重畫
    @app.callback(Output("map-graph", "figure"), Input("map-layers", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def _fig(layers, lang):
        return build_figure(tuple(layers or []), lang)

    @app.callback(Output("map-detail", "children"), Input("map-graph", "clickData"), State("lang", "data"),
                  prevent_initial_call=True)
    def _detail(click, lang):
        if not click:
            return card(None, html.P(t("click_hint", lang), className="muted"))
        cid = click["points"][0].get("customdata")
        return company_panel(cid, lang) if isinstance(cid, str) else card(None, html.P(t("click_hint", lang)))

    @app.callback(Output("map-ais-summary", "children"), Input("map-layers", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def _ais(layers, lang):
        return ais_summary(lang) if "ais" in (layers or []) else None
