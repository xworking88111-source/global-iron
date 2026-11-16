"""資料與方法：資料來源、計算方法、限制、更新時間。公開透明是可信度的一部分。

內容直接讀取 docs/METHODOLOGY.zh.md / METHODOLOGY.en.md，
所以網站和 GitHub 上的說明永遠是同一份，不會各說各話。
"""
from __future__ import annotations

from dash import dcc, html

from core import config, data
from core.i18n import t

from .common import card

DOCS_DIR = config.ROOT / "docs"


def _doc(lang: str) -> str:
    p = DOCS_DIR / f"METHODOLOGY.{lang}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def layout(lang: str):
    meta = data.meta()
    upd = [html.Li(f"{k}: {v[:16].replace('T', ' ')} UTC") for k, v in meta.items()] or [html.Li("—")]
    ais = data.ais_snapshot()
    if ais:
        upd.append(html.Li(f"ais: {ais.get('collected_at', '')[:16].replace('T', ' ')} UTC"))
    return html.Div([
        html.Div([html.H2(t("about_title", lang))], className="page-head"),
        card(t("last_updates", lang), html.Ul(upd, className="small")),
        card(None, dcc.Markdown(_doc(lang), className="md")),
    ])
