"""集中設定：檔案路徑、價格序列定義、配色。

之後要加入新產業（例如鋁）：新增一份公司 JSON，並在 PRICE_SERIES 加上帶有
`industry` 標籤的價格序列即可。其他地方不應該把 "steel" 寫死。
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 路徑
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "data" / "static"   # 人工整理、納入版本控制的資料
CACHE_DIR = ROOT / "data" / "cache"     # 程式自動抓的資料（由 scripts/ 更新）
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PRICES_FILE = CACHE_DIR / "prices.csv"            # 長格式：date, series, value
STOCKS_FILE = CACHE_DIR / "stock_prices.csv"      # 長格式：date, ticker, close
FUNDAMENTALS_FILE = CACHE_DIR / "fundamentals.json"
AIS_FILE = CACHE_DIR / "ais_snapshot.json"
META_FILE = CACHE_DIR / "meta.json"               # 各類資料最後更新時間
QUARTERLY_FILE = CACHE_DIR / "quarterly.csv"      # 各公司季報重點（當地幣別）
WS_MONTHLY_FILE = CACHE_DIR / "worldsteel_monthly.csv"  # worldsteel 每月產量（區域＋前 10 大國）
CSC_OFFICIAL_FILE = CACHE_DIR / "csc_official.json"     # 中鋼官網盤價新聞稿（自動抓取）

# ---------------------------------------------------------------------------
# 價格序列
#   source: "sina"     -> 中國期貨主力連續合約（新浪財經）
#           "yfinance" -> Yahoo Finance 代碼
#   unit 是原始資料的單位；需要比較時由 analytics 換算。
# ---------------------------------------------------------------------------
PRICE_SERIES: dict[str, dict] = {
    "cn_hrc":   {"source": "sina", "symbol": "HC0", "unit": "CNY/t", "industry": "steel",
                 "en": "China HRC (SHFE)", "zh": "中國熱軋卷（上期所）"},
    "cn_rebar": {"source": "sina", "symbol": "RB0", "unit": "CNY/t", "industry": "steel",
                 "en": "China Rebar (SHFE)", "zh": "中國螺紋鋼（上期所）"},
    "cn_ore":   {"source": "sina", "symbol": "I0", "unit": "CNY/t", "industry": "steel",
                 "en": "Iron Ore (DCE)", "zh": "鐵礦砂（大商所）"},
    "cn_coke":  {"source": "sina", "symbol": "J0", "unit": "CNY/t", "industry": "steel",
                 "en": "Met. Coke (DCE)", "zh": "焦炭（大商所）"},
    "cn_cokingcoal": {"source": "sina", "symbol": "JM0", "unit": "CNY/t", "industry": "steel",
                 "en": "Coking Coal (DCE)", "zh": "焦煤（大商所）"},
    "us_hrc":   {"source": "yfinance", "symbol": "HRC=F", "unit": "USD/st", "industry": "steel",
                 "en": "US Midwest HRC (CME)", "zh": "美國中西部熱軋卷（CME）"},
    "ore_62":   {"source": "yfinance", "symbol": "TIO=F", "unit": "USD/t", "industry": "steel",
                 "en": "Iron Ore 62% Fe CFR China (SGX/CME)", "zh": "鐵礦 62% 到岸中國（SGX/CME）"},
    "dry_bulk": {"source": "yfinance", "symbol": "BDRY", "unit": "USD", "industry": "shipping",
                 "en": "Dry-bulk freight proxy (BDRY ETF)", "zh": "乾散貨運價代理（BDRY ETF）"},
    "brent":    {"source": "yfinance", "symbol": "BZ=F", "unit": "USD/bbl", "industry": "energy",
                 "en": "Brent crude", "zh": "布蘭特原油"},
    # 匯率：Yahoo 的 "XXX=X" 代表「1 美元可換多少 XXX」
    "fx_cny":   {"source": "yfinance", "symbol": "CNY=X", "unit": "CNY per USD", "industry": "fx", "en": "USD/CNY", "zh": "美元/人民幣"},
    "fx_twd":   {"source": "yfinance", "symbol": "TWD=X", "unit": "TWD per USD", "industry": "fx", "en": "USD/TWD", "zh": "美元/新台幣"},
    "fx_jpy":   {"source": "yfinance", "symbol": "JPY=X", "unit": "JPY per USD", "industry": "fx", "en": "USD/JPY", "zh": "美元/日圓"},
    "fx_krw":   {"source": "yfinance", "symbol": "KRW=X", "unit": "KRW per USD", "industry": "fx", "en": "USD/KRW", "zh": "美元/韓元"},
    "fx_eur":   {"source": "yfinance", "symbol": "EUR=X", "unit": "EUR per USD", "industry": "fx", "en": "USD/EUR", "zh": "美元/歐元"},
    "fx_inr":   {"source": "yfinance", "symbol": "INR=X", "unit": "INR per USD", "industry": "fx", "en": "USD/INR", "zh": "美元/印度盧比"},
    "fx_vnd":   {"source": "yfinance", "symbol": "VND=X", "unit": "VND per USD", "industry": "fx", "en": "USD/VND", "zh": "美元/越南盾"},
    "fx_sek":   {"source": "yfinance", "symbol": "SEK=X", "unit": "SEK per USD", "industry": "fx", "en": "USD/SEK", "zh": "美元/瑞典克朗"},
    "fx_try":   {"source": "yfinance", "symbol": "TRY=X", "unit": "TRY per USD", "industry": "fx", "en": "USD/TRY", "zh": "美元/土耳其里拉"},
    "fx_aud":   {"source": "yfinance", "symbol": "AUD=X", "unit": "AUD per USD", "industry": "fx", "en": "USD/AUD", "zh": "美元/澳幣"},
}

# 更新腳本抓取的歷史長度
HISTORY_START = "2015-01-01"
STOCK_HISTORY_PERIOD = "5y"

SHORT_TON_IN_TONNES = 0.90718474   # CME 美國熱軋卷以「短噸」報價，1 短噸 = 0.907 公噸

# ---------------------------------------------------------------------------
# 利差模型（高爐利潤的粗略代理）
#   煉 1 噸鐵水約需 1.6 噸鐵礦、0.5 噸焦炭。
#   這是中國期貨交易員常用的「盤面利潤」估算法。
# ---------------------------------------------------------------------------
SPREAD_ORE_RATIO = 1.6
SPREAD_COKE_RATIO = 0.5

# ---------------------------------------------------------------------------
# 配色（dataviz 參考色票的深色模式版本）
# 分類色依固定順序使用，不可循環重複。
# ---------------------------------------------------------------------------
COLORS = {
    "surface": "#1a1a19",     # 卡片／圖表底色
    "surface_2": "#232322",   # 次一層底色（表頭、輸入框）
    "border": "#383835",
    "text": "#f0efec",
    "text_2": "#c3c2b7",
    "muted": "#8a8980",
    "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"],
    # 狀態色只用來表示好／警告／危險，絕不拿來當資料序列的顏色
    "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
}

# 煉鋼製程 -> 分類色（只用 3 類，讓地圖上的散點對色盲讀者也分得出來）
ROUTE_COLOR = {"BF": COLORS["series"][0], "EAF": COLORS["series"][1], "MIX": COLORS["series"][2]}
