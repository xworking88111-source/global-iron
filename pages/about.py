"""資料來源、方法、更新時間。公開透明是可信度的一部分。"""
from __future__ import annotations

from dash import dcc, html

from core import data
from core.i18n import t

from .common import card

# 長篇說明放在這裡而不是 i18n.py，因為只有這一頁用得到。
DOC = {
    "en": """
### Sources
| Data | Source | Refresh | Notes |
|---|---|---|---|
| China HRC, rebar, iron ore, coke, coking coal | SHFE / DCE main continuous futures via Sina Finance | daily | Prices include 13% VAT; contract rolls cause small jumps |
| US Midwest HRC | CME futures (HRC=F) via Yahoo Finance | daily | USD per short ton |
| Iron ore 62% Fe CFR China | SGX / CME (TIO=F) via Yahoo Finance | daily | Seaborne benchmark |
| Dry-bulk freight proxy | Breakwave Dry Bulk Shipping ETF (BDRY) | daily | Tracks Capesize/Panamax/Supramax freight futures; a free stand-in for the Baltic indices |
| Share prices & fundamentals | Yahoo Finance | daily | Fundamentals are a snapshot (trailing 12 months) |
| Company output, country output, steel & ore trade | worldsteel *World Steel in Figures 2025* | annual | 2024 data |
| Vessel positions | AISStream.io (free, terrestrial AIS) | on demand | Coverage is coastal; open ocean is sparse without satellite AIS |
| Chokepoints, sea lanes, events | Curated in `data/static/*.json` | manual | Edit the JSON to add or correct entries |

### Methods
- **China blast-furnace margin proxy** = HRC − 1.6 × iron ore − 0.5 × coke (CNY/t). Standard futures-desk heuristic; excludes conversion costs. Use its percentile and trend.
- **10-year percentile**: share of trading days in the last 10 years with a lower value than today.
- **Peer scores** are percentile ranks within the same group (steelmakers vs miners). *Health* = average rank of EBITDA margin, ROE, low debt/equity and current ratio; *Value* = low P/B; *Momentum* = 1-year share return.
- **EBITDA per tonne** = group EBITDA (USD) ÷ 2024 crude steel output. Inflated for diversified groups.
- **Scenario**: unit margin = HRC − 1.6 × ore − 0.5 × coke − other cost; annual impact = Δmargin × 2024 output.

### Known limits of the free tier
- No European HRC, scrap or Platts/Argus physical assessments (licensed data).
- AIS cannot tell what a ship carries; ore-carrier counts near ports are a congestion and activity signal.
- Unlisted groups (Jianlong, Delong, Tsingshan…) and sanctioned Russian/Iranian firms have no free financial data.
""",
    "zh": """
### 資料來源
| 資料 | 來源 | 更新頻率 | 備註 |
|---|---|---|---|
| 中國熱軋、螺紋鋼、鐵礦、焦炭、焦煤 | 上期所／大商所主力連續期貨（新浪財經） | 每日 | 價格含 13% 增值稅；換月會有小幅跳動 |
| 美國中西部熱軋卷 | CME 期貨（HRC=F，Yahoo Finance） | 每日 | 美元／短噸 |
| 鐵礦 62% 到岸中國 | SGX／CME（TIO=F，Yahoo Finance） | 每日 | 海運鐵礦基準 |
| 乾散貨運價代理 | Breakwave 乾散貨航運 ETF（BDRY） | 每日 | 追蹤海岬型／巴拿馬型／超輕便型運價期貨，作為波羅的海指數的免費替代 |
| 股價與基本面 | Yahoo Finance | 每日 | 基本面為近四季快照 |
| 公司產量、各國產量、鋼材與鐵礦貿易 | worldsteel《World Steel in Figures 2025》 | 每年 | 2024 年資料 |
| 船舶位置 | AISStream.io（免費岸基 AIS） | 手動或排程 | 涵蓋沿岸，遠洋若無衛星 AIS 會稀疏 |
| 咽喉要道、航線、事件 | 人工整理於 `data/static/*.json` | 手動 | 直接編輯 JSON 即可新增或修正 |

### 方法
- **中國高爐利潤代理** = 熱軋 − 1.6 × 鐵礦 − 0.5 × 焦炭（人民幣/噸）。期貨交易員常用的估算，未扣加工成本，請看分位與趨勢。
- **10 年分位**：過去 10 年中，價格低於今天的交易日比例。
- **同業分數**為同組（鋼廠 vs 礦商）內的百分位排名。*體質* = EBITDA 利潤率、ROE、低負債權益比、流動比率的平均排名；*價值* = 低股價淨值比；*動能* = 一年股價報酬。
- **每噸 EBITDA** = 集團 EBITDA（美元）÷ 2024 粗鋼產量，多角化集團會偏高。
- **情境模擬**：每噸利潤 = 熱軋 − 1.6 × 鐵礦 − 0.5 × 焦炭 − 其他成本；年度影響 = 每噸利潤變化 × 2024 產量。

### 免費資料的已知限制
- 沒有歐洲熱軋、廢鋼，也沒有 Platts／Argus 現貨評估價（需授權）。
- AIS 無法得知船上貨物；港口附近礦砂船數量只能當作壅塞與活動訊號。
- 未上市集團（建龍、德龍、青山…）及受制裁的俄羅斯／伊朗公司沒有免費財務資料。
""",
}


def layout(lang: str):
    meta = data.meta()
    upd = [html.Li(f"{k}: {v[:16].replace('T', ' ')} UTC") for k, v in meta.items()] or [html.Li("—")]
    ais = data.ais_snapshot()
    if ais:
        upd.append(html.Li(f"ais: {ais.get('collected_at', '')[:16].replace('T', ' ')} UTC"))
    return html.Div([
        html.Div([html.H2(t("about_title", lang))], className="page-head"),
        card(t("last_updates", lang), html.Ul(upd, className="small")),
        card(None, dcc.Markdown(DOC[lang], className="md")),
        html.P(t("disclaimer", lang), className="card-note"),
    ])
