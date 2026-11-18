"""月報：把各頁的資料整理成一份雙語的每月情勢報告。

1. 一句話總結
2. 各段落：牆內外價差、中國、亞洲盤價、台灣、貿易壁壘、航運與政策、下個月觀察
3. 期數選單：「最新（即時）」或過去歸檔的月份
4. 下載 Markdown：方便貼到筆記、電子報或簡報

--- English ---
Monthly brief: the site's data written up as a bilingual monthly situation report.

1. One-line summary
2. Sections: price gap, China, Asian list prices, Taiwan, trade walls, shipping and policy, what to watch
3. Edition picker: "Latest (live)" or an archived month
4. Markdown download, for notes, newsletters or slides
"""
from __future__ import annotations

from dash import Input, Output, State, dcc, html

from core import report as rp
from core.cache import cached
from core.i18n import t

from .common import card

LIVE = "live"


def _edition(month: str) -> dict:
    return rp.build() if month == LIVE else rp.load(month)


def _title(rep: dict, lang: str) -> str:
    m = rep["month"]
    return t("rp_title", lang).format(m=rp._mzh(m) if lang == "zh" else rp._men(m))


@cached()
def body(month: str, lang: str):
    """某一期月報的內容（快取：資料版本不變就不重算）。"""
    rep = _edition(month)
    if not rep or not rep.get("sections"):
        return html.P(t("no_data", lang))
    asof = t("rp_asof", lang).format(d=rep["generated"]) + ("" if month != LIVE else " · " + t("rp_live_note", lang))
    parts = [
        html.Div([html.H3(_title(rep, lang), className="card-title"),
                  html.P(rep.get(f"headline_{lang}", ""), className="rp-headline"),
                  html.P(asof, className="muted small")], className="gi-card rp-lead"),
    ]
    for s in rep["sections"]:
        link = html.A(t("rp_more", lang) + " →", href=s["link"], className="link small") if s.get("link") else None
        parts.append(card(s[f"{lang}_title"], html.Ul([html.Li(x) for x in s[lang]], className="rp-list"), link))
    return html.Div(parts)


@cached()
def layout(lang: str):
    """月報頁。"""
    months = rp.archived()
    opts = [{"label": t("rp_live", lang), "value": LIVE}] + [
        {"label": rp._mzh(m) if lang == "zh" else rp._men(m), "value": m} for m in months]
    return html.Div([
        html.Div([html.H2(t("nav_report", lang))], className="page-head"),
        html.P(t("rp_intro", lang), className="muted"),
        html.Div([
            html.Div([html.Label(t("rp_edition", lang), className="ctl-label"),
                      dcc.Dropdown(id="rp-month", options=opts, value=LIVE, clearable=False, searchable=False,
                                   className="dd")], className="ctl"),
            html.Div([html.Button(t("rp_download", lang), id="rp-dl-btn", className="lang-btn"),
                      dcc.Download(id="rp-dl")], className="ctl"),
        ], className="controls"),
        html.Div(body(LIVE, lang), id="rp-body"),
        html.P(t("rp_method", lang), className="card-note"),
    ])


def register(app) -> None:
    @app.callback(Output("rp-body", "children"), Input("rp-month", "value"), State("lang", "data"),
                  prevent_initial_call=True)
    def _switch(month, lang):
        return body(month or LIVE, lang or "zh")

    @app.callback(Output("rp-dl", "data"), Input("rp-dl-btn", "n_clicks"), State("rp-month", "value"),
                  State("lang", "data"), prevent_initial_call=True)
    def _download(_, month, lang):
        rep = _edition(month or LIVE)
        lang = lang or "zh"
        return dict(content=rp.to_markdown(rep, lang), filename=f"global-iron-brief-{rep['month']}-{lang}.md")
