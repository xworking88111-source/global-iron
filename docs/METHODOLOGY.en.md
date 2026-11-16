# Global Iron methodology

Where every number on the site comes from, how it is calculated, how to read it, and its limits. This document is what the site's "Data & Method" page displays.

## 1. Data pipeline

```
Free data sources ──► Fetch (scripts/) ──► Cache files (data/cache/) ──► Analytics (core/analytics.py) ──► Web pages (pages/)
Curated data (data/static/*.json) ──────────────────────────────────┘
```

| Step | What | Code | Frequency |
|---|---|---|---|
| 1. Fetch | Futures, equities, fundamentals, quarterly results, worldsteel monthly output, China Steel prices | `scripts/update_data.py` | Weekdays (GitHub Actions) |
| 1. Fetch | AIS vessels, China Steel Express fleet | `scripts/collect_ais.py` | 4× daily |
| 2. Store | CSV / JSON committed back to GitHub, keeping full history | `data/cache/` | After each fetch |
| 3. Analyse | Spreads, percentiles, peer scores, scenario model, weekly highlights | `core/analytics.py`, `core/highlights.py` | On page view, results cached |
| 4. Present | Charts, map, tables, bilingual | `pages/*.py` | Live |

**Design principle:** the site never calls external sources while you browse; it only reads the cache. If a source is down, data goes stale but the site keeps working, and every page shows an as-of date.

## 2. Sources and reliability

| Data | Source | How obtained | Reliability |
|---|---|---|---|
| China HRC, rebar, iron ore, coke, coking coal | SHFE / DCE main continuous contracts | Sina Finance public endpoint, automatic | High: exchange prices. Include 13% VAT; small jumps at contract rolls |
| US HRC | CME `HRC=F` | Yahoo Finance, automatic | High: front-month futures, USD per short ton |
| Seaborne iron ore 62% | SGX / CME `TIO=F` | Yahoo Finance, automatic | High |
| Dry-bulk freight | BDRY ETF | Yahoo Finance, automatic | Medium: an ETF tracking freight futures, a proxy not the rate itself |
| Share prices, fundamentals, quarterly results | Exchanges via Yahoo Finance | Automatic | Medium-high: occasional gaps; zero values treated as missing |
| Annual company / country output, trade | worldsteel *World Steel in Figures 2025* | Curated from the PDF | High: official statistics |
| Monthly global production | worldsteel monthly press releases | Automatic (web tables) | High: official (some countries estimated) |
| China Steel list prices | CSC newsroom | **Automatic** from official releases; earlier months from media | High (official) / medium-high (media) |
| China steel exports | China Customs (GACC) | Curated from trade-press reports; monthly automatic reminder | Medium-high: reported months cross-checked; derived months flagged |
| Vessel positions | AISStream terrestrial AIS | Automatic | Uneven: good in Europe/Japan, sparse in China/Taiwan/Australia |
| Chokepoints, events | Curated | Event dates checked against legal and press sources | Structural notes; follow official links for live status |

**Why are China's exports not fully automatic?** The customs site blocks automated access, there is no free API, and headline formats are inconsistent, so scraped numbers would be unreliable. Instead a monthly reminder opens automatically and a person updates after checking two sources.

**Quality checks:**
- China exports: monthly figures must add up to the official year-to-date total (e.g. Jan–Sep sum 85.66 vs reported 85.64 Mt)
- China Steel prices: official releases compared month by month with earlier media-based figures (Oct–Dec identical)
- worldsteel: tables parsed by column header (old and new layouts differ); space thousand separators stripped

## 3. Metrics and calculations

### 3.1 KPI tiles
- **Latest value**: last trading day with data.
- **1W / 1M / 1Y change**: latest vs the value 7 / 30 / 365 calendar days earlier.
- **10-year percentile**: share of trading days in the last 10 years with a lower value than today. 0 = 10-year low, 100 = 10-year high.
- **Unit toggle**: "All in USD per tonne" converts the whole history with **daily** FX, so changes and percentiles are in USD terms too. When the yuan strengthens, a price can fall in CNY and rise in USD; that difference is information.

### 3.2 China blast-furnace margin proxy (the core cycle indicator)
```
Margin proxy = HRC futures − 1.6 × iron ore futures − 0.5 × coke futures   (CNY/t)
```
- **Why 1.6 and 0.5**: one tonne of hot metal needs roughly 1.6 t of ore and 0.5 t of coke; this is the standard "futures margin" heuristic on Chinese trading desks.
- **Limit**: excludes energy, labour, alloys and other conversion costs (about CNY 600–900/t), so **the level is not a profit figure**. Read the **trend and 10-year percentile**.
- **Market regime**: percentile below 20 = margins squeezed, 20–45 weak, 45–70 normal, above 70 strong.

### 3.3 US vs China HRC gap
```
China (USD/t) = SHFE HRC ÷ USD/CNY
US (USD/t)    = CME HRC ÷ 0.907 (short ton to metric tonne)
```
The gap roughly reflects US tariff protection (Section 232), freight and US supply tightness.

### 3.4 Peer scores (0–100, relative ranks)
Companies are ranked **within their group** (steelmakers vs steelmakers, miners vs miners), because miners' ~50% margins would make every steelmaker look poor.

| Score | Inputs | Direction |
|---|---|---|
| Health | Average percentile of EBITDA margin, ROE, debt/equity, current ratio (needs at least 2) | Higher margins, lower debt are better |
| Value | Price-to-book | Cheaper scores higher. Steel is cyclical; P/B is steadier than P/E |
| Momentum | 1-year share return | Higher is better |

80 means "better than 80% of the group", not an absolute grade.
- **EBITDA per tonne** = group EBITDA (USD) ÷ 2024 crude steel output. Inflated for diversified groups (e.g. thyssenkrupp).
- **Quarterly margins** = quarterly EBITDA (or operating income, net income) ÷ revenue. Currency-neutral, so comparable across countries.

### 3.5 Scenario model
```
Unit margin    = HRC − 1.6 × ore − 0.5 × coke − other conversion cost
Annual impact  = change in unit margin × 2024 crude steel output
Sensitivity    = annual impact of a 1% move in each price
```
Assumes all crude steel sells at the HRC price: a reasonable upper bound for flat-product mills such as China Steel, an overstatement for long-product mills. Use it for **direction and orders of magnitude**.

### 3.6 This week at a glance (home page)
Generated by fixed rules; every bullet traces back to a number on the site:
1. The two biggest weekly moves above 1%
2. Margin-proxy percentile ≤ 10 flags "squeezed", ≥ 80 flags "rich"
3. US HRC at 1.5× China's or more flags the tariff wall
4. Latest China exports, global production, China Steel price
5. Policy events in the last 60 days

### 3.7 AIS vessels
- Listen for 5 minutes inside boxes around ports (~65 km) and chokepoints; keep each ship's latest position.
- "Cargo / all": AIS type codes 70–79 are confirmed cargo ships; many ships have not broadcast their type during the window, so "all" runs high.
- China Steel Express fleet: MMSIs are found by ship-name matching, then tracked worldwide by MMSI.

## 4. Known limits
- No Platts / Argus physical assessments, European HRC or scrap (licensed data).
- Chinese futures include VAT; keep that in mind against international quotes.
- Free AIS is terrestrial only; open ocean and some Asian ports are not covered.
- Yahoo's free quarterly data covers about 5–6 quarters; history accumulates over time.
- No free financials for unlisted groups (Jianlong, Delong, Tsingshan…) or sanctioned Russian and Iranian mills.

## 5. Disclaimer
For information only, not investment advice. Check primary sources before acting.
