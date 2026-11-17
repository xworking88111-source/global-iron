"""從免費資料來源抓資料的函式。

只有 `scripts/update_data.py` 會呼叫這裡。網站本身在使用者瀏覽時「不會」連網抓
資料，只讀快取檔。好處：頁面快、不會被資料源限流；資料源掛掉時，網站只是資料
變舊，而不會整個壞掉。

--- English ---
Fetchers for free data sources.

Only `scripts/update_data.py` calls these. The site never fetches data while
someone is browsing; it reads cache files. Pages stay fast, sources are not
rate-limited, and an outage only makes data stale instead of breaking the site.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import pandas as pd

log = logging.getLogger(__name__)


def _retry(fn: Callable, tries: int = 3, wait: float = 3.0):
    """最多呼叫 fn() `tries` 次。新浪／Yahoo 偶爾會暫時逾時，重試通常就好了。"""
    last_err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 任何網路或解析錯誤都值得重試
            last_err = e
            log.warning("attempt %d/%d failed: %s", i + 1, tries, e)
            time.sleep(wait * (i + 1))  # 每次失敗等久一點再試
    raise last_err


# ---------------------------------------------------------------------------
# 中國期貨（上期所／大商所），來源：新浪財經
# ---------------------------------------------------------------------------
# 這就是 `akshare` 套件背後用的同一個公開介面。我們直接呼叫，
# 因為 akshare 把逾時寫死成 10 秒，鐵礦的長歷史資料常常超過。
_SINA_KLINE = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{sym}{tag}=/InnerFuturesNewService.getDailyKLine"


def fetch_cn_future(symbol: str, start: str) -> pd.Series:
    """主力連續合約的每日收盤價，例如 'HC0' = 上期所熱軋卷。

    「主力連續」會把持倉量最大的合約月份接起來，所以換月那天可能有小跳動。
    """
    import json
    import re

    import requests

    tag = pd.Timestamp.today().strftime("_%Y_%m_%d")

    def call():
        r = requests.get(_SINA_KLINE.format(sym=symbol, tag=tag),
                         params={"symbol": symbol, "type": tag[1:]},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        # 回應是 JSONP 格式：`var _X=([...]);`，用正規表達式取出中間的 JSON 陣列
        m = re.search(r"\((\[.*\])\)", r.text, re.S)
        if not m:
            raise ValueError(f"unexpected Sina response for {symbol}")
        return json.loads(m.group(1))

    rows = _retry(call)
    # 欄位：d=日期 o=開盤 h=最高 l=最低 c=收盤 v=成交量 p=持倉量 s=結算價
    df = pd.DataFrame(rows)
    s = pd.Series(df["c"].astype(float).values, index=pd.to_datetime(df["d"]), name=symbol)
    return s[s.index >= start].sort_index()


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def fetch_yf_history(tickers: list[str], start: str | None = None, period: str | None = None) -> pd.DataFrame:
    """每日收盤價，一個代碼一欄。抓不到的代碼會是整欄空值。"""
    import yfinance as yf

    kwargs = {"start": start} if start else {"period": period or "5y"}

    def call():
        # auto_adjust=True：股價已調整除權息，報酬率計算才正確
        return yf.download(tickers, auto_adjust=True, progress=False, threads=True, **kwargs)

    raw = _retry(call)
    if raw.empty:
        return pd.DataFrame(columns=tickers)
    # 多個代碼時欄位是兩層（欄位種類, 代碼），只取 Close 這層
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
    return close.reindex(columns=tickers)


# 從 yfinance 的 .info 中保留的欄位（原本有約 150 個，多數用不到）
_INFO_FIELDS = [
    "currency", "financialCurrency", "marketCap", "priceToBook", "trailingPE", "forwardPE",
    "debtToEquity", "ebitda", "totalRevenue", "ebitdaMargins", "profitMargins", "operatingMargins",
    "returnOnEquity", "dividendYield", "totalDebt", "totalCash", "currentRatio", "beta",
]


def fetch_yf_fundamentals(ticker: str) -> dict:
    """單一代碼的基本面快照。Yahoo 沒資料時各欄位為 None。"""
    import yfinance as yf

    info = _retry(lambda: yf.Ticker(ticker).info, tries=2)
    return {k: info.get(k) for k in _INFO_FIELDS}


def fetch_fx_to_usd(currencies: set[str]) -> dict[str, float]:
    """各幣別最新的「1 美元可換多少該幣」（USD 本身為 1.0）。用來把市值等換算成美元。"""
    out = {"USD": 1.0}
    need = sorted(c for c in currencies if c and c != "USD")
    if not need:
        return out
    df = fetch_yf_history([f"{c}=X" for c in need], period="10d")
    for c in need:
        col = df.get(f"{c}=X")
        if col is not None and col.dropna().size:
            out[c] = float(col.dropna().iloc[-1])
    return out


# ---------------------------------------------------------------------------
# 季報（每季營收、EBITDA、營業利益、淨利）
# ---------------------------------------------------------------------------
_QUARTER_ROWS = {"Total Revenue": "revenue", "EBITDA": "ebitda",
                 "Operating Income": "operating_income", "Net Income": "net_income"}


def fetch_yf_quarterly(ticker: str) -> pd.DataFrame:
    """近幾季的損益表重點（當地幣別）。Yahoo 免費版通常給 5–6 季。"""
    import yfinance as yf

    q = _retry(lambda: yf.Ticker(ticker).quarterly_income_stmt, tries=2)
    if q is None or q.empty:
        return pd.DataFrame()
    rows = [r for r in _QUARTER_ROWS if r in q.index]
    df = q.loc[rows].T.rename(columns=_QUARTER_ROWS)
    df.index = pd.to_datetime(df.index)
    df.index.name = "quarter_end"
    return df.reset_index().assign(ticker=ticker)


# ---------------------------------------------------------------------------
# worldsteel 每月粗鋼產量新聞稿（官方免費公布：8 大區域＋前 10 大生產國）
# ---------------------------------------------------------------------------
_WS_LIST = "https://worldsteel.org/media/press-releases/page/{page}/"
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120 Safari/537.36"}
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}


def list_worldsteel_monthly(pages: int = 3) -> dict[str, str]:
    """新聞稿列表 -> {"2026-09": 網址}。網址格式像 .../2026/september-2026-crude-steel-production/"""
    import re

    import requests

    found: dict[str, str] = {}
    for page in range(1, pages + 1):
        url = "https://worldsteel.org/media/press-releases/" if page == 1 else _WS_LIST.format(page=page)
        r = _retry(lambda: requests.get(url, headers=_UA, timeout=60))
        for link in re.findall(r'href=["\']?(https://worldsteel\.org/media/press-releases/[^\s"\'>]+)', r.text):
            m = re.search(r"/([a-z]+)-(\d{4})-crude-steel-production", link)
            if m and m.group(1) in _MONTHS:
                found[f"{m.group(2)}-{_MONTHS[m.group(1)]:02d}"] = link
    return found


def guess_worldsteel_url(month: str) -> str:
    """列表頁只列最近幾則；較舊的月份依固定網址格式推測（例如 2025/june-2025-crude-steel-production）。
    注意：每年 12 月的新聞稿在隔年 1 月發布，網址放在隔年的資料夾下。"""
    y, m = month.split("-")
    name = [k for k, v in _MONTHS.items() if v == int(m)][0]
    folder = int(y) + 1 if int(m) == 12 else int(y)
    return f"https://worldsteel.org/media/press-releases/{folder}/{name}-{y}-crude-steel-production/"


def fetch_worldsteel_month(url: str, month: str) -> pd.DataFrame:
    """解析單月新聞稿的兩張表：區域表與前 10 大國家表。"""
    import io

    import requests

    r = _retry(lambda: requests.get(url, headers=_UA, timeout=60))
    tables = pd.read_html(io.StringIO(r.text))  # 需要 lxml
    out = []
    for kind, t in zip(("region", "country"), tables[:2]):
        # 依「欄位標題」辨認欄位，而不是依位置：舊新聞稿的表格中間可能多一個空白欄
        cols = {"entity": t.columns[0]}
        for c in t.columns[1:]:
            name = str(c)
            ytd = "Jan" in name and "-" in name      # 例如 "Jan-Sep 2026 (Mt)"
            if "(Mt)" in name:
                cols["ytd_mt" if ytd else "mt"] = c
            elif "%" in name:
                cols["ytd_yoy_pct" if ytd else "yoy_pct"] = c
        t = t[list(cols.values())].copy()
        t.columns = list(cols.keys())
        for c in t.columns[1:]:
            # 數字可能用空格當千分位（例如 "1 016.5"），先清掉再轉成數字
            t[c] = pd.to_numeric(t[c].astype(str).str.replace(r"[\s\u00a0]", "", regex=True), errors="coerce")
        t["entity"] = t["entity"].astype(str).str.replace(r"\s*\(e\)", "", regex=True).str.strip()
        t["kind"] = kind
        out.append(t)
    df = pd.concat(out, ignore_index=True)
    df["month"] = month
    return df


# ---------------------------------------------------------------------------
# 中鋼官網盤價新聞稿（官方來源，含調幅表與市場評論）
# ---------------------------------------------------------------------------
_CSC_NEWS = "https://www.csc.com.tw/CS/CSC/NC/neli/"
_ZH_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _zh_year(s: str) -> int:
    """民國年中文數字逐字轉換：「一一五」-> 115 -> 西元 2026。"""
    return int("".join(str(_ZH_DIGIT[c]) for c in s)) + 1911


def _zh_month(s: str) -> int:
    """中文月份：「十二」-> 12、「十」-> 10、「三」-> 3。"""
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + _ZH_DIGIT[s[1]]
    return _ZH_DIGIT[s]


def _csc_sections(lines: list[str]) -> dict[str, str]:
    """新聞稿內文分段：總體經濟／鋼鐵市場／決議。"""
    out, key = {}, None
    for line in lines:
        if line in ("總體經濟", "鋼鐵市場", "決議"):
            key = line
            continue
        if key and line.startswith("中鋼公司") and "調幅表" in line:
            break
        if key:
            out[key] = (out.get(key, "") + line).strip()
    return out


def _csc_table(lines: list[str], header: str) -> dict[str, int]:
    """解析調幅表某一段（「月盤產品」或「季盤產品」）：品項 -> 每公噸調整金額。"""
    import re

    if header not in lines:
        return {}
    i = lines.index(header) + 1
    items: dict[str, int] = {}
    while i < len(lines) - 1:
        name, val = lines[i], lines[i + 1]
        # 遇到下一段表頭或表格底下的註解（例如「* 自115年第四季起…」）就停
        if name in ("月盤產品", "季盤產品") or name.startswith("* "):
            break
        if re.fullmatch(r"[+\-−]?\d[\d,]*", val.replace(" ", "")):
            items[name.lstrip("*")] = int(val.replace(",", "").replace("−", "-").replace("+", ""))
            i += 2
        else:
            i += 1  # 表頭（項目、調整金額…）跳過
    return items


def fetch_csc_price_releases() -> list[dict]:
    """抓中鋼新聞中心最新一頁中的盤價新聞稿（約涵蓋最近 3 個月）。"""
    import re

    import requests

    r = _retry(lambda: requests.get(_CSC_NEWS + "neli.aspx", headers=_UA, timeout=60))
    r.encoding = "utf-8"
    links = re.findall(r'href=["\'](neli_content\.aspx\?newid=[0-9A-F]+)["\'][^>]*>(.*?)</a>', r.text, re.S)
    out = []
    for href, label in links:
        label = re.sub(r"<[^>]+>|\s+", "", label)
        m = re.search(r"中鋼(.{3})年(十二|十一|十|[一二三四五六七八九])月盤", label)
        if not m:
            continue
        url = _CSC_NEWS + href
        page = _retry(lambda: requests.get(url, headers=_UA, timeout=60))
        page.encoding = "utf-8"
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page.text, flags=re.S)
        lines = [s.strip() for s in re.sub(r"<[^>]+>", "\n", text).splitlines()]
        lines = [s.replace("\xa0", "").strip() for s in lines if s.strip() and s.strip() != "\xa0"]
        pub = re.search(r"發佈日期：(\d{4}/\d{2}/\d{2})", text)
        monthly = _csc_table(lines, "月盤產品")
        hrc = monthly.get("熱軋鋼板、鋼捲(一般料)", monthly.get("熱軋鋼捲(軋延料)"))
        crc = monthly.get("冷軋鋼捲(一般料)")
        sec = _csc_sections(lines)
        out.append({
            "month": f"{_zh_year(m.group(1))}-{_zh_month(m.group(2)):02d}",
            "published": pub.group(1).replace("/", "-") if pub else None,
            "hrc": hrc, "crc": crc,
            "monthly_items": monthly, "quarterly_items": _csc_table(lines, "季盤產品"),
            "macro_zh": sec.get("總體經濟", ""), "market_zh": sec.get("鋼鐵市場", ""), "decision_zh": sec.get("決議", ""),
            "source": url, "official": True,
        })
    return out


# ---------------------------------------------------------------------------
# 台灣鋼材進出口：財政部統計資料庫（海關進出口貿易統計，政府資料開放授權）
# 網址參數格式：fldN=1 選第 N 個「統計項」（國家或貨品），codspc0=起點,個數 選「複分類」（貨品細分類）
# ym / ymt 是民國年月（例如 11510 = 2026 年 10 月）。沒有驗證碼，是公開的下載連結。
# ---------------------------------------------------------------------------
_MOF_DB = "https://web02.mof.gov.tw/njswww/webMain.aspx"


def _roc_ym(ts: pd.Timestamp) -> str:
    """西元年月 -> 民國年月代碼：2026-10 -> '11510'。"""
    return f"{ts.year - 1911}{ts.month:02d}"


def fetch_mof_table(funid: str, flds: list[int], codspc: str = "", start: str = "2016-01") -> pd.DataFrame:
    """下載財政部統計資料庫的一張表（CSV），轉成長格式：month, col, value。

    col 是原始欄位名稱，例如「中國大陸/ 鐵或非合金鋼及其製品」或「72. 鋼鐵」。
    只保留單月列（「115年 9月」），年度合計列（「114年」）丟掉；「－」代表沒有資料或還沒公布。
    """
    import io
    import re

    import requests

    end = pd.Timestamp.today()
    params = {"sys": 220, "ym": _roc_ym(pd.Timestamp(start)), "ymt": _roc_ym(end), "kind": 21, "type": 4,
              "funid": funid, "cycle": 41, "outmode": 12, "compmode": "00", "outkind": 1, "utf": 1}
    params.update({f"fld{i}": 1 for i in flds})
    if codspc:
        params["codspc0"] = codspc
    r = _retry(lambda: requests.get(_MOF_DB, params=params, headers=_UA, timeout=90))
    r.encoding = "utf-8-sig"
    if "功能代號不存在" in r.text[:50] or not r.text.lstrip().startswith('"'):
        raise ValueError(f"MOF {funid}: unexpected response {r.text[:80]!r}")
    df = pd.read_csv(io.StringIO(r.text), dtype=str)
    first = df.columns[0]
    rows = []
    for _, row in df.iterrows():
        m = re.fullmatch(r"\s*(\d+)年\s*(\d+)月\s*", str(row[first]))
        if not m:
            continue
        month = f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}"
        for col in df.columns[1:]:
            v = str(row[col]).replace(",", "").strip()
            if re.fullmatch(r"-?\d+(\.\d+)?", v):
                rows.append({"month": month, "col": col.strip(), "value": float(v)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 東京製鐵（日本最大電爐廠）每月販售價格表
# ---------------------------------------------------------------------------
# 官網「販売情報」頁列出 2007 年起每個月的價格表 PDF（文字型，可直接抽字）。
# 日本只有東京製鐵公開完整盤價；日本製鐵、JFE 只公布調幅，所以用它當日本鋼價的官方參考。
_TOKYO_STEEL = "https://www.tokyosteel.co.jp/"
# 代表性品項：(區段開頭, 區段結尾, 取區段內第幾個價格)
# 價格 = 「不帶 + 號、至少 2 萬日圓」的數字（帶 + 號的是規格加價）。
# 區段一定要有結尾：某品項當月停售時（例如 2009-06 熱軋寫「────」），才不會誤抓到下一個品項的價格。
TOKYO_STEEL_ITEMS = {
    "hrc":   (r"ホットコイル", r"酸洗コイル", 1),     # 熱軋鋼捲 1.7≦t≦22.0（第 0 個是較薄的 1.5–1.7mm）
    "hbeam": (r"中\s*巾", r"広\s*巾", 0),            # H 型鋼中幅基準尺寸（建築用，電爐廠主力）
    "plate": (r"厚\s*板", r"熱延鋼板", None),         # 厚板 9.0≦t≦40.0（有沒有 8.0mm 那一列，見下方）
    "rebar": (r"異形棒鋼", r"\*|＊|単位|$", 1),       # 鋼筋：D13 或 D13–D25（第 0 個是 D10）
}


def list_tokyo_steel_prices() -> dict[str, str]:
    """販売情報頁 -> {"2026-11": PDF 網址}。"""
    import re

    import requests

    r = _retry(lambda: requests.get(_TOKYO_STEEL + "salesprice/", headers=_UA, timeout=60))
    r.raise_for_status()
    out = {}
    for path, y, m in re.findall(r'href="(?:\.\./)?(assets/docs/salesprice/price/\d{4}/(\d{4})\.(\d{2})\.pdf)"', r.text):
        out[f"{y}-{m}"] = _TOKYO_STEEL + path
    return out


def parse_tokyo_steel_pdf(content: bytes) -> dict:
    """價格表 PDF -> {"announced": "10/19", "hrc": 106000, ...}（日圓／公噸，含運到工地的 O/T NET 價）。

    全形數字先用 NFKC 轉半形；只看第一頁以外的品項時，同一品項以第一次出現為準。
    """
    import io
    import re
    import unicodedata

    from pypdf import PdfReader

    pages = [p.extract_text() or "" for p in PdfReader(io.BytesIO(content)).pages]
    text = unicodedata.normalize("NFKC", "\n".join(pages))
    if "ホットコイル" not in text and sum(0x3E2E <= ord(c) <= 0x3E37 for c in text) > 200:
        return _parse_tokyo_steel_garbled(pages)
    out: dict = {}
    m = re.search(r"\n\s*(\d{1,2}/\d{1,2})\s*\n", text)  # 表頭下方的發布日期，例如 10/19
    if m:
        out["announced"] = m.group(1)
    for key, (start, end, idx) in TOKYO_STEEL_ITEMS.items():
        m = re.search(start, text)
        if not m:
            continue
        e = re.search(end, text[m.end():])
        seg = text[m.start():m.end() + (e.start() if e else len(text))]
        if idx is None:  # 厚板：較新的價格表第一列是 8.0mm，9–40mm 在第二列；舊表只有 9–40mm 起
            idx = 1 if re.match(r"厚\s*板\s*8\.0", seg) else 0
        nums = [int(n.replace(",", "")) for n in re.findall(r"(?<![+\d,])(\d{2,3},\d{3})(?![\d,])", seg)]
        nums = [n for n in nums if n >= 20000]
        if len(nums) > idx:
            out[key] = nums[idx]
    return out


def _parse_tokyo_steel_garbled(pages: list[str]) -> dict:
    """少數月份（例如 2025-06、2025-11）的 PDF 字型沒有對照表，抽出來的字是亂碼。

    數字仍是固定位移（U+3E2E = 0，\\x0f = 逗號，㸩 = +），可以還原；但標題文字還原不了，
    只好依版面順序取值：第 1 頁 = H 型鋼…鋼筋，第 2 頁 = 熱軋鋼捲…厚板。
    取到的值會在 update_tokyo_steel() 和前後月份比對，差太多就丟掉。
    """
    import re

    def nums(t: str) -> list[int]:
        t = "".join(chr(ord(c) - 0x3E2E + 48) if 0x3E2E <= ord(c) <= 0x3E37 else
                    "," if c == "\x0f" else "+" if c == "㸩" else c for c in t)
        return [v for v in (int(n.replace(",", "")) for n in re.findall(r"(?<![+\d,])(\d{2,3},\d{3})(?![\d,])", t))
                if v >= 20000]

    out: dict = {}
    if len(pages) >= 2:
        p1, p2 = nums(pages[0]), nums(pages[1])
        if len(p1) > 4:
            out["hbeam"] = p1[4]     # 細幅 4 個級距之後，就是中幅基準
            out["rebar"] = p1[-2]    # 鋼筋 D10、D13–D25、D29–D32 → 取中間
        if len(p2) > 12:
            out["hrc"] = p2[1]       # 熱軋 1.5–1.7、1.7–22 → 取第 2 個
            out["plate"] = p2[12]    # 熱軋 2、酸洗 2、鍍鋅 6、縞捲 1、厚板 8mm → 第 13 個是 9–40mm
    return out


def fetch_tokyo_steel_pdf(url: str) -> dict:
    import requests

    r = _retry(lambda: requests.get(url, headers=_UA, timeout=60))
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF: {url}")
    return parse_tokyo_steel_pdf(r.content)


def fetch_tokyo_steel_comment() -> str:
    """販売情報頁的「市況情報」：東京製鐵對下個月定價的說明（日文原文）。"""
    import re

    import requests

    r = _retry(lambda: requests.get(_TOKYO_STEEL + "salesprice/", headers=_UA, timeout=60))
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S)
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))
    m = re.search(r"MARKET INFORMATION\s*市況情報\s*(.+?)\s*(?:以上\s*)?PREVIOUS", s)
    return m.group(1).strip() if m else ""
