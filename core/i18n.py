"""介面的中英文字串。

用法：  t("nav_overview", lang)  ->  "Market" 或 "市場總覽"
資料本身的名稱（公司、港口……）在 JSON 裡各自帶有 `en` / `zh` 欄位，
請用 `pick(record, "name", lang)` 取出。

找不到翻譯時先退回英文，再退回 key 本身：忘了翻譯的字會顯示出來，
但頁面不會因此壞掉。

--- English ---
UI strings in English and Traditional Chinese.

Usage:  t("nav_overview", lang)  ->  "Market" or "市場總覽"
Data-level names (companies, ports...) carry their own `en` / `zh` fields in
the JSON files; use `pick(record, "name", lang)` for those.

Missing keys fall back to English, then to the key itself, so a forgotten
translation is visible but never crashes a page.
"""
from __future__ import annotations

LANGS = ("en", "zh")
DEFAULT_LANG = "zh"

STRINGS: dict[str, dict[str, str]] = {
    # ---- 外框／導覽列 -------------------------------------------------------
    "app_title": {"en": "Global Iron — Steel Market Monitor", "zh": "Global Iron 全球鋼鐵市場觀測"},
    "app_tagline": {"en": "Tracking the split of the global steel market, seen from Taiwan",
                    "zh": "從台灣看全球鋼鐵市場的分裂：價差、貿易流向與航運風險"},
    "nav_overview": {"en": "Market", "zh": "市場總覽"},
    "nav_map": {"en": "Global Map", "zh": "全球地圖"},
    "nav_companies": {"en": "Companies", "zh": "公司分析"},
    "nav_scenario": {"en": "Scenario", "zh": "情境模擬"},
    "nav_risk": {"en": "Trade & Risk", "zh": "貿易與風險"},
    "nav_about": {"en": "Data & Method", "zh": "資料與方法"},
    "lang_toggle": {"en": "中文", "zh": "EN"},
    "data_as_of": {"en": "Market data as of", "zh": "市場資料截至"},
    "source": {"en": "Source", "zh": "來源"},
    "no_data": {"en": "No data yet — run scripts/update_data.py", "zh": "尚無資料，請執行 scripts/update_data.py"},
    "disclaimer": {"en": "For information only, not investment advice. Free data sources; check primary sources before acting.",
                   "zh": "僅供參考，非投資建議。資料來自免費來源，決策前請查核原始資料。"},

    # ---- 市場總覽 ------------------------------------------------------------
    "highlights_title": {"en": "This week at a glance", "zh": "本週重點"},
    "highlights_more": {"en": "Monthly data", "zh": "月度數據"},
    "unit_label": {"en": "Units", "zh": "單位"},
    "unit_local": {"en": "Local market units", "zh": "原幣原單位"},
    "unit_usd": {"en": "All in USD per tonne", "zh": "統一：美元／公噸"},
    "not_per_tonne": {"en": "ETF price, not per tonne", "zh": "ETF 價格，非每噸價格"},
    "kpi_cn_hrc": {"en": "China HRC", "zh": "中國熱軋卷"},
    "kpi_us_hrc": {"en": "US HRC", "zh": "美國熱軋卷"},
    "kpi_ore": {"en": "Iron ore 62%", "zh": "鐵礦 62%"},
    "kpi_coke": {"en": "Met. coke", "zh": "焦炭"},
    "kpi_spread": {"en": "China BF margin proxy", "zh": "中國高爐利潤代理"},
    "kpi_freight": {"en": "Dry-bulk freight (BDRY)", "zh": "乾散貨運價（BDRY）"},
    "chg_1w": {"en": "1W", "zh": "週"},
    "chg_1m": {"en": "1M", "zh": "月"},
    "chg_1y": {"en": "1Y", "zh": "年"},
    "pctl_10y": {"en": "10-yr percentile", "zh": "10 年分位"},
    "pctl_hint": {"en": "0 = lowest in 10 years, 100 = highest", "zh": "0 = 十年最低，100 = 十年最高"},
    "regime_title": {"en": "Market regime", "zh": "市場狀態"},
    "regime_squeezed": {"en": "Margins squeezed: mills near or below cash cost; expect output cuts, export push and trade defence.",
                        "zh": "利潤被擠壓：鋼廠接近或低於現金成本，可能減產、加大出口並引發貿易保護。"},
    "regime_weak": {"en": "Below-average margins: cautious restocking, price-sensitive buyers.",
                    "zh": "利潤低於平均：補庫謹慎，買方對價格敏感。"},
    "regime_normal": {"en": "Normal margins: balanced market.", "zh": "利潤正常：市場相對平衡。"},
    "regime_strong": {"en": "Strong margins: tight supply or strong demand; watch for capacity restarts.",
                      "zh": "利潤強勁：供給偏緊或需求強，留意產能復產。"},
    "regime_unknown": {"en": "Not enough data.", "zh": "資料不足。"},
    "chart_prices": {"en": "Steel and raw materials (futures, local units)", "zh": "鋼材與原料（期貨，原幣單位）"},
    "chart_spread": {"en": "China blast-furnace margin proxy: HRC − 1.6×ore − 0.5×coke (CNY/t)",
                     "zh": "中國高爐利潤代理：熱軋 − 1.6×鐵礦 − 0.5×焦炭（人民幣/噸）"},
    "chart_spread_note": {"en": "Excludes other conversion costs (~CNY 600–900/t). Read the trend and percentile, not the level.",
                          "zh": "未扣其他加工成本（約每噸 600–900 元人民幣）。請看趨勢與分位，不要看絕對值。"},
    "chart_gap": {"en": "HRC: US vs China (USD per tonne)", "zh": "熱軋卷：美國 vs 中國（美元/公噸）"},
    "chart_gap_note": {"en": "The gap reflects US tariff protection (Section 232), freight and domestic supply tightness.",
                       "zh": "價差反映美國關稅保護（232 條款）、運費與美國本土供給吃緊。"},
    "range": {"en": "Range", "zh": "區間"},
    "show_events": {"en": "Show events", "zh": "顯示事件"},
    "rebased_note": {"en": "Indexed to 100 at start of range so different units compare.",
                     "zh": "以區間起點 = 100 指數化，讓不同單位可比較。"},
    "spread_avg": {"en": "10-yr average", "zh": "10 年平均"},

    # ---- 月度數據 ------
    "nav_monthly": {"en": "Monthly", "zh": "月度數據"},
    "nav_taiwan": {"en": "Taiwan Lens", "zh": "台灣視角"},
    "monthly_intro": {"en": "Three monthly data sets that drive the steel cycle: China's exports, global production, and China Steel's domestic list prices.",
                      "zh": "推動鋼鐵景氣的三組月資料：中國出口、全球產量、中鋼內銷盤價。"},
    "cn_exports_title": {"en": "China finished-steel exports (monthly, Mt)", "zh": "中國成品鋼材出口（每月，百萬噸）"},
    "cn_exports_note": {"en": "Customs (GACC) figures via trade press. China's export surge is the main reason for weak global steel prices.",
                        "zh": "海關總署數字，經產業媒體轉載。中國出口暴增是這兩年全球鋼價低迷的主因。"},
    "reported": {"en": "Reported", "zh": "公布值"},
    "derived": {"en": "Derived", "zh": "推算值"},
    "avg_2025": {"en": "2025 monthly avg", "zh": "2025 月平均"},
    "latest_month": {"en": "Latest", "zh": "最新月份"},
    "mom": {"en": "MoM", "zh": "月增"},
    "yoy": {"en": "YoY", "zh": "年增"},
    "ytd": {"en": "YTD", "zh": "年初至今"},
    "ws_monthly_title": {"en": "Global crude steel production (worldsteel, monthly)", "zh": "全球粗鋼產量（worldsteel，每月）"},
    "ws_monthly_note": {"en": "70 reporting countries. Fetched automatically from worldsteel's monthly press releases (published ~3 weeks after month end). Taiwan is not in the monthly top 10.",
                        "zh": "70 個申報國家。自動抓取 worldsteel 每月新聞稿（約月底後 3 週公布）。台灣不在每月前 10 大名單內。"},
    "china": {"en": "China", "zh": "中國"},
    "rest_of_world": {"en": "Rest of world", "zh": "中國以外"},
    "of_world": {"en": "of world", "zh": "占全球"},
    "top10_yoy": {"en": "Top-10 producers, YoY", "zh": "前 10 大產鋼國年增率"},
    "csc_title": {"en": "China Steel monthly list-price changes (HRC/CRC, TWD per tonne)", "zh": "中鋼月盤調整（熱軋／冷軋，每公噸新台幣）"},
    "csc_view": {"en": "China Steel's own market view", "zh": "中鋼官方觀點"},
    "published": {"en": "published", "zh": "發布"},
    "csc_market": {"en": "Steel market", "zh": "鋼鐵市場"},
    "csc_decision": {"en": "Decision", "zh": "決議"},
    "csc_original": {"en": "Read the official release", "zh": "閱讀官網原文"},
    "csc_zh_only": {"en": "official text is in Chinese", "zh": ""},
    "csc_src_note": {"en": "Months marked 'official' are fetched daily from CSC's own press releases; earlier months come from media reports.",
                     "zh": "標示「官網」的月份每天自動從中鋼官網新聞稿抓取；較早的月份來自媒體報導。"},
    "src_official": {"en": "Source: CSC official release", "zh": "來源：中鋼官網新聞稿"},
    "src_media": {"en": "Source: media report", "zh": "來源：媒體報導"},
    "monthly_change": {"en": "Monthly change", "zh": "單月調整"},
    "cumulative": {"en": "Cumulative", "zh": "累計"},
    "ups_downs": {"en": "Up / down months", "zh": "調漲／調降月數"},
    "months_up_down": {"en": "months", "zh": "個月"},

    # ---- 地圖 ----------------------------------------------------------------
    "map_title": {"en": "Global steel producers, raw-material ports and sea lanes", "zh": "全球鋼廠、原料港口與海運航線"},
    "layers": {"en": "Layers", "zh": "圖層"},
    "layer_producers": {"en": "Steelmakers", "zh": "鋼廠"},
    "layer_miners": {"en": "Iron ore miners", "zh": "鐵礦商"},
    "layer_ports": {"en": "Ports", "zh": "港口"},
    "layer_routes": {"en": "Sea lanes", "zh": "航線"},
    "layer_chokepoints": {"en": "Chokepoints", "zh": "咽喉要道"},
    "layer_trade": {"en": "Steel trade flows 2024", "zh": "2024 鋼材貿易流"},
    "layer_ais": {"en": "Live vessels (AIS)", "zh": "即時船位（AIS）"},
    "layer_country": {"en": "Country output (shading)", "zh": "各國產量（底色）"},
    "size_by": {"en": "Bubble size = 2024 crude steel output", "zh": "泡泡大小 = 2024 粗鋼產量"},
    "route_BF": {"en": "Blast furnace (BF-BOF)", "zh": "高爐（一貫作業）"},
    "route_EAF": {"en": "Electric arc furnace", "zh": "電爐"},
    "route_MIX": {"en": "Mixed BF + EAF", "zh": "高爐＋電爐混合"},
    "miner": {"en": "Iron ore miner", "zh": "鐵礦商"},
    "click_hint": {"en": "Click a company bubble for details.", "zh": "點擊公司泡泡查看詳情。"},
    "ais_none": {"en": "No AIS snapshot yet. Get a free key at aisstream.io, set AISSTREAM_API_KEY, run scripts/collect_ais.py.",
                 "zh": "尚無 AIS 快照。請到 aisstream.io 免費申請金鑰，設定 AISSTREAM_API_KEY 後執行 scripts/collect_ais.py。"},
    "layer_fleet": {"en": "Tracked fleet (China Steel Express)", "zh": "追蹤船隊（中鋼運通）"},
    "ais_summary": {"en": "AIS snapshot", "zh": "AIS 快照"},
    "ais_vessels": {"en": "cargo vessels seen", "zh": "艘貨船"},
    "vessels_cargo_all": {"en": "Cargo / all", "zh": "貨船 / 全部"},
    "ais_coverage_note": {"en": "Free terrestrial AIS: coverage is strong in Europe and Japan, sparse in China, Taiwan and Australia. Zones with no receivers show no ships.",
                          "zh": "免費岸基 AIS：歐洲、日本涵蓋好，中國、台灣、澳洲較稀疏。沒有接收站的區域不會顯示船。"},
    "zone": {"en": "Zone", "zh": "區域"},
    "vessels": {"en": "Vessels", "zh": "船數"},
    "port_ore_export": {"en": "Ore export port", "zh": "鐵礦出口港"},
    "port_coal_export": {"en": "Coal export port", "zh": "煤炭出口港"},
    "port_ore_import": {"en": "Ore import / steel port", "zh": "鐵礦進口／鋼鐵港"},
    "route_ore": {"en": "Iron ore lane", "zh": "鐵礦航線"},
    "route_coal": {"en": "Coking coal lane", "zh": "冶金煤航線"},
    "route_steel": {"en": "Steel export lane", "zh": "鋼材出口航線"},
    "route_diversion": {"en": "Red Sea diversion", "zh": "紅海改道航線"},
    "flow_label": {"en": "Mt steel", "zh": "百萬噸鋼材"},

    # ---- 公司分析 ----------------------------------------------------------
    "select_company": {"en": "Company", "zh": "公司"},
    "compare_with": {"en": "Compare with (up to 6)", "zh": "比較對象（最多 6 家）"},
    "rank": {"en": "World rank 2024", "zh": "2024 全球排名"},
    "output": {"en": "Crude steel 2024", "zh": "2024 粗鋼產量"},
    "country": {"en": "Country", "zh": "國家"},
    "route": {"en": "Process route", "zh": "製程"},
    "ownership": {"en": "Ownership", "zh": "所有權"},
    "products": {"en": "Products", "zh": "產品"},
    "ticker": {"en": "Ticker", "zh": "股票代碼"},
    "unlisted": {"en": "Not listed / no free price data", "zh": "未上市／無免費股價資料"},
    "sanctions_flag": {"en": "Sanctions / trade-restriction exposure", "zh": "制裁／貿易限制曝險"},
    "mcap": {"en": "Market cap", "zh": "市值"},
    "revenue": {"en": "Revenue (TTM)", "zh": "營收（近四季）"},
    "ebitda_margin": {"en": "EBITDA margin", "zh": "EBITDA 利潤率"},
    "net_margin": {"en": "Net margin", "zh": "淨利率"},
    "ebitda_per_t": {"en": "EBITDA / tonne", "zh": "每噸 EBITDA"},
    "roe": {"en": "ROE", "zh": "股東權益報酬率"},
    "pb": {"en": "P/B", "zh": "股價淨值比"},
    "pe": {"en": "P/E", "zh": "本益比"},
    "debt_to_equity": {"en": "Debt / equity", "zh": "負債權益比"},
    "current_ratio": {"en": "Current ratio", "zh": "流動比率"},
    "div_yield": {"en": "Dividend yield", "zh": "殖利率"},
    "ret_1y": {"en": "1Y return", "zh": "一年報酬"},
    "ret_3y": {"en": "3Y return", "zh": "三年報酬"},
    "score_health": {"en": "Health", "zh": "體質"},
    "score_value": {"en": "Value", "zh": "價值"},
    "score_momentum": {"en": "Momentum", "zh": "動能"},
    "scores_title": {"en": "Peer-relative scores (0–100)", "zh": "同業相對分數（0–100）"},
    "scores_note": {"en": "80 = better than 80% of peers in the same group. Health = margins, ROE, leverage, liquidity; Value = cheapness on P/B; Momentum = 1-yr share return.",
                    "zh": "80 = 勝過同組 80% 的公司。體質 = 利潤率、ROE、槓桿、流動性；價值 = 股價淨值比便宜程度；動能 = 一年股價報酬。"},
    "quarterly_title": {"en": "Quarterly profitability trend", "zh": "季度獲利趨勢"},
    "quarterly_note": {"en": "Margins from quarterly income statements (Yahoo Finance, about 5–6 quarters; history builds up over time). Margins are currency-neutral, so companies compare directly.",
                       "zh": "利潤率取自季報（Yahoo Finance，約 5–6 季，之後會越累積越多）。利潤率不受幣別影響，可直接跨國比較。"},
    "operating_margin": {"en": "Operating margin", "zh": "營業利益率"},
    "perf_title": {"en": "Share price, indexed to 100", "zh": "股價走勢（指數化 = 100）"},
    "peer_table": {"en": "Peer comparison", "zh": "同業比較表"},
    "ebitda_t_note": {"en": "EBITDA/t = group EBITDA ÷ crude steel output; conglomerates look inflated.",
                      "zh": "每噸 EBITDA = 集團 EBITDA ÷ 粗鋼產量；多角化集團會偏高。"},
    "fundamentals_as_of": {"en": "Fundamentals snapshot (Yahoo Finance)", "zh": "基本面快照（Yahoo Finance）"},
    "all_peers": {"en": "All steelmakers", "zh": "全部鋼廠"},

    # ---- 情境模擬 ----------------------------------------------------------
    "scn_title": {"en": "Cost-shock scenario for a blast-furnace mill", "zh": "高爐鋼廠成本衝擊情境"},
    "scn_intro": {"en": "Move prices and see the unit margin and the rough annual impact for the chosen mill. Base prices are today's futures (USD/t).",
                  "zh": "調整價格，看所選鋼廠的每噸利潤與年度影響粗估。基準價為今日期貨（美元/噸）。"},
    "scn_mill": {"en": "Mill (sets annual tonnage)", "zh": "鋼廠（決定年產量）"},
    "scn_hrc": {"en": "HRC price change", "zh": "熱軋價格變動"},
    "scn_ore": {"en": "Iron ore change", "zh": "鐵礦價格變動"},
    "scn_coke": {"en": "Coke change", "zh": "焦炭價格變動"},
    "scn_other": {"en": "Other conversion cost (USD/t)", "zh": "其他加工成本（美元/噸）"},
    "scn_base_market": {"en": "Price basis", "zh": "價格基準"},
    "scn_basis_cn": {"en": "China futures (converted to USD)", "zh": "中國期貨（換算美元）"},
    "scn_basis_intl": {"en": "Seaborne ore 62% + China coke/HRC", "zh": "海運鐵礦 62%＋中國焦炭／熱軋"},
    "scn_margin_base": {"en": "Margin now", "zh": "目前每噸利潤"},
    "scn_margin_new": {"en": "Margin in scenario", "zh": "情境每噸利潤"},
    "scn_annual": {"en": "Annual margin impact", "zh": "年度利潤影響"},
    "scn_sens": {"en": "Sensitivity: annual impact of a 1% move", "zh": "敏感度：價格變動 1% 的年度影響"},
    "scn_caveat": {"en": "Simplified model: assumes all crude steel sells at the HRC price and that 1.6 t ore + 0.5 t coke make 1 t steel. Use for direction and orders of magnitude.",
                   "zh": "簡化模型：假設全部粗鋼以熱軋價格出售，且 1.6 噸鐵礦＋0.5 噸焦炭產 1 噸鋼。用來看方向與數量級。"},
    "scn_other_short": {"en": "Other cost", "zh": "其他成本"},
    "scn_margin_short": {"en": "Margin", "zh": "每噸利潤"},
    "usd_m": {"en": "USD m", "zh": "百萬美元"},
    "per_t": {"en": "USD/t", "zh": "美元/噸"},
    "price": {"en": "Price", "zh": "價格"},
    "base": {"en": "Base", "zh": "基準"},
    "scenario": {"en": "Scenario", "zh": "情境"},

    # ---- 貿易與風險 ----------------------------------------------------------
    "risk_title": {"en": "Trade flows, chokepoints and policy timeline", "zh": "貿易流向、咽喉要道與政策時間軸"},
    "trade_matrix": {"en": "Who ships steel to whom (2024, Mt, excluding intra-region)", "zh": "誰把鋼材賣給誰（2024，百萬噸，不含區域內）"},
    "importer": {"en": "Importing region", "zh": "進口地區"},
    "exporter": {"en": "Exporting region", "zh": "出口地區"},
    "net_exports": {"en": "Net steel exporters / importers 2024 (Mt)", "zh": "2024 鋼材淨出口／淨進口（百萬噸）"},
    "ore_trade": {"en": "Iron ore: who mines, who imports (2024, Mt)", "zh": "鐵礦：誰開採、誰進口（2024，百萬噸）"},
    "production": {"en": "Production", "zh": "產量"},
    "exports": {"en": "Exports", "zh": "出口"},
    "imports": {"en": "Imports", "zh": "進口"},
    "chokepoint_table": {"en": "Maritime chokepoints for steel and raw materials", "zh": "鋼鐵與原料的海上咽喉要道"},
    "relevance": {"en": "Why it matters", "zh": "重要性"},
    "risks": {"en": "Risk factors", "zh": "風險因子"},
    "risk_review_note": {"en": "Structural notes, not live status. Use the official links in the last column for current advisories before underwriting or routing decisions.",
                         "zh": "此為結構性說明，非即時狀態。核保或航線決策前，請點最後一欄的官方連結查看最新公告。"},
    "advisories": {"en": "Official live sources", "zh": "官方即時公告"},
    "timeline": {"en": "Policy and event timeline", "zh": "政策與事件時間軸"},
    "date": {"en": "Date", "zh": "日期"},
    "event": {"en": "Event", "zh": "事件"},
    "category": {"en": "Category", "zh": "類別"},
    "country_output": {"en": "Crude steel output by country 2024 (Mt)", "zh": "2024 各國粗鋼產量（百萬噸）"},
    "world_output": {"en": "World crude steel", "zh": "全球粗鋼產量"},
    "china_net_exports": {"en": "China net steel exports", "zh": "中國鋼材淨出口"},
    "china_share": {"en": "China share of world output", "zh": "中國占全球產量"},

    # ---- 台灣視角 -----------------------------------------------------------
    "tw_intro": {"en": "Tariff walls (US Section 232, EU safeguards and CBAM, China's export licences) are splitting steel into a protected high-price zone and a China-driven low-price zone. Taiwan sits in between. Official customs statistics show where Taiwan's steel now goes, where its imports come from, and what is happening to prices and volumes.",
                 "zh": "關稅牆（美國 232、歐盟防衛措施與 CBAM、中國出口許可證）正把鋼鐵市場切成「受保護的高價區」和「中國主導的低價區」，台灣夾在中間。這一頁用海關官方統計，看台灣的鋼材出口去了哪裡、進口從哪裡來、價格與數量怎麼變。"},
    "tw_obs_title": {"en": "What the data says", "zh": "資料告訴我們什麼"},
    "tw_latest": {"en": "Customs data through", "zh": "海關資料截至"},
    "tw_product": {"en": "Product", "zh": "貨品"},
    "tw_p_steel": {"en": "Carbon + stainless", "zh": "碳鋼＋不銹鋼"},
    "tw_p_carbon": {"en": "Carbon steel", "zh": "碳鋼"},
    "tw_p_stainless": {"en": "Stainless", "zh": "不銹鋼"},
    "tw_exports_ytd": {"en": "Exports, Jan–{m}", "zh": "出口（1–{m} 月）"},
    "tw_imports_ytd": {"en": "Imports, Jan–{m}", "zh": "進口（1–{m} 月）"},
    "tw_net": {"en": "Net exports", "zh": "出超"},
    "tw_usd_m": {"en": "USD m", "zh": "百萬美元"},
    "tw_usd_m_12m": {"en": "USD m, trailing 12 months", "zh": "百萬美元，近 12 個月累計"},
    "tw_total": {"en": "Total", "zh": "合計"},
    "tw_exports_title": {"en": "Where Taiwan's steel goes", "zh": "台灣鋼材出口去哪裡"},
    "tw_change_title": {"en": "Change by destination: Jan–{m} {yr} vs {base} (USD m)",
                        "zh": "各目的地增減：{yr} vs {base} 年 1–{m} 月（百萬美元）"},
    "tw_exports_note": {"en": "Left: trailing-12-month sums remove seasonality. Values are in US dollars, so they mix price and volume; read them with the volume index below. ASEAN = 10 members plus Timor-Leste.",
                        "zh": "左圖：近 12 個月累計，可消除季節性。金額以美元計，同時反映價格與數量，請搭配下方的數量指數一起看。東協 = 10 國加東帝汶。"},
    "tw_imports_title": {"en": "Where Taiwan's steel imports come from (share of trailing-12-month value)",
                         "zh": "台灣鋼材進口從哪裡來（近 12 個月金額占比）"},
    "tw_imports_note": {"en": "Indonesia dominates ASEAN's share through stainless steel. Hong Kong is counted under Other. Taiwan levies anti-dumping duties on some Chinese and Korean flat products, which shapes these shares.",
                        "zh": "東協的占比主要來自印尼的不銹鋼。香港併入「其他」。台灣對部分中國與韓國扁鋼產品課有反傾銷稅，也會影響這些占比。"},
    "tw_idx_import": {"en": "Imports: iron and steel (HS 72), 2021 = 100", "zh": "進口：鋼鐵（HS 72 章），2021 = 100"},
    "tw_idx_export": {"en": "Exports: articles of iron or steel (HS 73), 2021 = 100", "zh": "出口：鋼鐵製品（HS 73 章），2021 = 100"},
    "tw_unit_value": {"en": "Unit-value index (price)", "zh": "單價指數（價格）"},
    "tw_quantity": {"en": "Quantity index (volume)", "zh": "數量指數（數量）"},
    "tw_idx_note": {"en": "Official indices compiled by the Ministry of Finance, shown as 3-month moving averages. The statistics database publishes a steel (HS 72) index only for imports and a steel-products (HS 73) index only for exports, so the two charts cover different product groups. The latest month's index is released a month after the trade values.",
                    "zh": "財政部編製的官方指數，圖上為 3 個月移動平均。統計資料庫的進口只有鋼鐵（HS 72 章）指數、出口只有鋼鐵製品（HS 73 章）指數，所以兩張圖的貨品範圍不同。指數比金額晚一個月公布。"},
    "tw_source": {"en": "Ministry of Finance statistics database (customs trade statistics, general trade system), Government Open Data Licence; refreshed automatically",
                  "zh": "財政部統計資料庫（海關進出口貿易統計，一般貿易制度），政府資料開放授權；自動更新"},

    # ---- 資料與方法 ---------------------------------------------------------
    "about_title": {"en": "Data sources and methodology", "zh": "資料來源與方法"},
    "last_updates": {"en": "Last refresh", "zh": "最近更新"},
}


def t(key: str, lang: str = DEFAULT_LANG) -> str:
    """依 key 取出目前語言的字串。"""
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or key


def pick(record: dict, field: str, lang: str) -> str:
    """從資料紀錄取出 `欄位_zh` / `欄位_en`（field 為空字串時取 `zh` / `en`），缺中文時退回英文。"""
    keys = [f"{field}_{lang}", f"{field}_en"] if field else [lang, "en"]
    for k in keys:
        v = record.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


# companies.json 裡的所有權文字 -> 中文（英文介面直接顯示原文）
_OWNERSHIP_ZH = {
    "state": "國有", "listed": "上市", "private": "民營", "subsidiary": "子公司",
    "listed (state-linked)": "上市（官股）", "listed (MOEX)": "上市（莫斯科交易所）",
    "listed (TSE)": "上市（德黑蘭交易所）", "listed (CSC subsidiary)": "上市（中鋼子公司）",
    "private (Formosa Plastics Group, CSC minority stake)": "民營（台塑集團，中鋼少數持股）",
}


def ownership_label(value: str | None, lang: str) -> str:
    """所有權欄位的顯示文字。"""
    if not value:
        return "—"
    return _OWNERSHIP_ZH.get(value, value) if lang == "zh" else value
