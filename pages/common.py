"""共用介面元件：圖表樣式、指標卡、卡片、事件標註。

--- English ---
Shared UI building blocks: chart style, KPI tiles, cards, event overlays.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html

from core import analytics as an
from core import data
from core.cache import cached
from core.config import COLORS
from core.i18n import pick, t

SERIES = COLORS["series"]

@cached(maxsize=4)
def peers():
    """同業比較表（多個頁面都會用到，算一次大家共用；資料更新時自動重算）。"""
    return an.peer_table(data.companies(), data.fundamentals(), data.stock_prices())


# 所有圖表共用的工具列設定：只留一顆「還原」按鈕且常駐顯示（手機沒有滑鼠停留，不能等 hover 才出現）。
# 使用者框選放大後，按這顆按鈕或雙擊圖表就能回到原本的刻度。
GRAPH_CONFIG = {
    "displaylogo": False,
    "displayModeBar": True,
    "modeBarButtons": [["resetScale2d"]],
    "doubleClick": "reset",
}


# 時間序列頁面共用的區間選項：標籤 -> 往回幾年
RANGES = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10}


def theme(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    """套用深色圖表樣式：淡格線、細座標軸、同一時間點的數值一起顯示在提示框。"""
    fig.update_layout(
        height=height,
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        font=dict(family="Inter, 'Noto Sans TC', system-ui, sans-serif", size=12, color=COLORS["text_2"]),
        margin=dict(l=48, r=16, t=16, b=36),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=COLORS["surface_2"], bordercolor=COLORS["border"], font_color=COLORS["text"]),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=COLORS["text_2"])),
    )
    axis = dict(gridcolor=COLORS["border"], gridwidth=0.5, zeroline=False, linecolor=COLORS["border"],
                tickfont=dict(color=COLORS["muted"]), title_font=dict(color=COLORS["muted"]))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def empty_fig(msg: str, height: int = 300) -> go.Figure:
    """沒資料時顯示的空白圖（中間一行提示文字）。"""
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=COLORS["muted"], size=14),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return theme(fig, height=height, legend=False)


def add_end_labels(fig: go.Figure, df: pd.DataFrame, names: dict[str, str], colors: dict[str, str]) -> None:
    """在每條線的最後一點直接標上名稱（線條 4 條以內時使用，讀者不用來回對照圖例）。"""
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            continue
        fig.add_annotation(x=s.index[-1], y=s.iloc[-1], text=names.get(col, col), showarrow=False,
                           xanchor="left", xshift=6, font=dict(size=11, color=COLORS["text_2"]))
        # 線尾的小圓點，讓標籤和線條對得起來
        fig.add_trace(go.Scatter(x=[s.index[-1]], y=[s.iloc[-1]], mode="markers", showlegend=False,
                                 hoverinfo="skip", marker=dict(size=8, color=colors[col],
                                                               line=dict(width=2, color=COLORS["surface"]))))


def add_events(fig: go.Figure, start: pd.Timestamp, lang: str, y_top: float | None = None) -> None:
    """把事件畫成虛線直線，頂端放可滑鼠停留查看的小三角形。"""
    ev = data.events()
    if ev.empty:
        return
    ev = ev[ev["date"] >= start]
    if ev.empty:
        return
    cats = data.event_categories()
    for d in ev["date"]:
        fig.add_vline(x=d, line=dict(color=COLORS["muted"], width=1, dash="dot"), opacity=0.6)
    if y_top is not None:
        fig.add_trace(go.Scatter(
            x=ev["date"], y=[y_top] * len(ev), mode="markers", name=t("show_events", lang),
            marker=dict(symbol="triangle-down", size=10, color=COLORS["text_2"],
                        line=dict(width=1, color=COLORS["surface"])),
            hovertemplate="%{text}<extra></extra>",
            text=[f"{r['date']:%Y-%m-%d} · {pick(cats.get(r['cat'], {}), '', lang)}<br>{pick(r, '', lang)}"
                  for _, r in ev.iterrows()],
            showlegend=False,
        ))


# ---------------------------------------------------------------------------
# HTML 元件
# ---------------------------------------------------------------------------
def card(title: str | None, *children, note: str | None = None, className: str = "") -> html.Div:
    """卡片容器：標題（可省略）＋內容＋底部灰色說明。"""
    parts = []
    if title:
        parts.append(html.H3(title, className="card-title"))
    parts.extend(children)
    if note:
        parts.append(html.P(note, className="card-note"))
    return html.Div(parts, className=f"gi-card {className}")


def delta_span(label: str, pct: float | None) -> html.Span:
    """漲跌幅加上 ▲/▼ 箭頭，讓方向不只靠顏色辨認（色盲讀者也看得懂）。"""
    if pct is None:
        return html.Span(f"{label} —", className="delta")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "•")
    cls = "delta up" if pct > 0 else ("delta down" if pct < 0 else "delta")
    return html.Span(f"{label} {arrow}{abs(pct):.1f}%", className=cls)


def kpi_tile(label: str, value: str, unit: str, summary: dict, lang: str, extra: str | None = None) -> html.Div:
    """指標卡：名稱、最新值、週／月／年漲跌、10 年分位條。"""
    pctl = summary.get("pctl_10y")
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div([html.Span(value, className="kpi-value"), html.Span(unit, className="kpi-unit")]),
        html.Div([delta_span(t("chg_1w", lang), summary.get("chg_1w")),
                  delta_span(t("chg_1m", lang), summary.get("chg_1m")),
                  delta_span(t("chg_1y", lang), summary.get("chg_1y"))], className="kpi-deltas"),
        # 分位條：今天的值落在過去 10 年區間的哪裡
        html.Div([
            html.Div(className="pctl-track", children=html.Div(className="pctl-fill",
                                                               style={"width": f"{pctl or 0:.0f}%"})),
            html.Span(f"{t('pctl_10y', lang)} {pctl:.0f}" if pctl is not None else "", className="pctl-text"),
        ], className="pctl", title=t("pctl_hint", lang)),
        html.Div(extra, className="kpi-extra") if extra else None,
    ], className="kpi-tile")


def stat(label: str, value: str, sub: str | None = None) -> html.Div:
    """小型數字方塊：標籤、數值、副標。"""
    return html.Div([html.Div(label, className="stat-label"), html.Div(value, className="stat-value"),
                     html.Div(sub, className="stat-sub") if sub else None], className="stat")


def source_line(lang: str, text: str) -> html.P:
    """頁面底部的資料來源說明。"""
    return html.P(f"{t('source', lang)}: {text}", className="source-line")
