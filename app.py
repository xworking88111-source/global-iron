"""Global Iron：網站入口。

本機開發：  python app.py            -> http://127.0.0.1:8050
正式上線：  gunicorn app:server      （Render / Railway / Fly.io 會執行這行）

整體運作方式
------------
* `dcc.Location` 記錄目前網址；`dcc.Store("lang")` 記錄語言，並存在瀏覽器的
  localStorage，所以訪客選過的語言重新整理後還會保留。
* 只有一個「路由」callback：網址或語言改變時，就重新產生頁面內容。
  每個頁面模組用 `layout(lang)` 產生自己的版面，並用 `register(app)`
  註冊自己的互動 callback。
"""
from __future__ import annotations

import os

from dash import Dash, Input, Output, State, dcc, html

from core import data
from core.i18n import DEFAULT_LANG, t
from pages import about, companies, map as map_page, overview, risk, scenario

# 網址路徑 -> （頁面模組, 導覽列文字的 key）
ROUTES = {
    "/": (overview, "nav_overview"),
    "/map": (map_page, "nav_map"),
    "/companies": (companies, "nav_companies"),
    "/scenario": (scenario, "nav_scenario"),
    "/risk": (risk, "nav_risk"),
    "/about": (about, "nav_about"),
}

app = Dash(
    __name__,
    title="Global Iron",
    suppress_callback_exceptions=True,  # 切換頁面時元件會出現／消失，關掉「找不到元件」的警告
    compress=True,  # 以 gzip 壓縮回應（需要 flask-compress）：圖表 JSON 通常可縮小 5–8 倍
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # Dash 底層的 Flask 物件，給 gunicorn 使用

app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="lang", storage_type="local", data=DEFAULT_LANG),
    html.Header([
        html.Div([
            dcc.Link([html.Span("◆", className="logo-mark"), html.Span("Global Iron", className="logo-text")],
                     href="/", className="logo"),
            html.Span(id="tagline", className="tagline"),
        ], className="brand"),
        html.Nav(id="nav", className="nav"),
        html.Button(id="lang-btn", n_clicks=0, className="lang-btn"),
    ], className="topbar"),
    html.Main(id="page", className="page"),
    html.Footer(id="footer", className="footer"),
])


@app.callback(Output("lang", "data"), Input("lang-btn", "n_clicks"), State("lang", "data"),
              prevent_initial_call=True)
def toggle_lang(_, lang):
    """按語言按鈕：中英互換。"""
    return "en" if lang == "zh" else "zh"


@app.callback(Output("nav", "children"), Output("lang-btn", "children"), Output("tagline", "children"),
              Output("footer", "children"), Input("url", "pathname"), Input("lang", "data"))
def render_shell(path, lang):
    """產生頁面外框：導覽列（標示目前所在頁）、語言按鈕、標語、頁尾。"""
    links = [dcc.Link(t(key, lang), href=p, className="nav-link active" if p == path else "nav-link")
             for p, (_, key) in ROUTES.items()]
    meta = data.meta()
    upd = meta.get("prices", "")[:10]
    footer = [html.Span(t("disclaimer", lang)),
              html.Span(f" · {t('last_updates', lang)} {upd}" if upd else "")]
    return links, t("lang_toggle", lang), t("app_tagline", lang), footer


@app.callback(Output("page", "children"), Input("url", "pathname"), Input("url", "search"), Input("lang", "data"))
def render_page(path, search, lang):
    """路由：依網址挑出頁面模組並產生內容；找不到的網址一律回首頁。"""
    module, _ = ROUTES.get(path, ROUTES["/"])
    if module is companies:
        return module.layout(lang, search)  # 支援直接連結，例如 /companies?c=posco
    return module.layout(lang)


# 啟動時把每個頁面的互動 callback 註冊一次
for _module, _ in ROUTES.values():
    if hasattr(_module, "register"):
        _module.register(app)


def warm_up() -> None:
    """預先算好兩種語言的所有頁面，放進快取。

    Render 免費方案 CPU 很弱，重啟或休眠醒來後第一個訪客原本要等每頁現算；
    預熱之後，第一位訪客也能直接拿到算好的結果。
    """
    for lang in ("zh", "en"):
        for module, _ in ROUTES.values():
            try:
                module.layout(lang)
            except Exception as e:  # noqa: BLE001 - 預熱失敗不該讓網站起不來
                print(f"warm-up failed for {module.__name__}/{lang}: {e}")


warm_up()


if __name__ == "__main__":
    # 本機執行時預設開除錯模式（右下角會出現 Dash 開發工具）；設 DASH_DEBUG=0 可關掉
    app.run(debug=os.environ.get("DASH_DEBUG", "1") == "1", host="127.0.0.1",
            port=int(os.environ.get("PORT", 8050)))
