# Global Iron 全球鋼鐵市場觀測

一眼掌握鋼價、全球鋼廠、貿易流向與航運風險的中英雙語網站。
目標使用者：全球股票投資人、地緣政治研究者、航運保險從業者。

全部使用免費資料來源。

## 頁面

| 頁面 | 內容 |
|---|---|
| 市場總覽 `/` | 6 個指標卡（價格、週/月/年漲跌、10 年分位）、市場狀態判斷、高爐利潤代理、美中熱軋價差、原料走勢＋事件標註 |
| 全球地圖 `/map` | 51 家鋼廠與礦商（泡泡 = 產量、顏色 = 製程）、各國產量底色、鐵礦／煤／鋼材航線、11 個咽喉要道、港口、2024 貿易流、AIS 船位 |
| 公司分析 `/companies` | 公司檔案、同業相對分數（體質／價值／動能）、股價走勢比較、同業比較表（可排序）。支援 `?c=posco` 直接連結 |
| 情境模擬 `/scenario` | 調整熱軋／鐵礦／焦炭價格，看每噸利潤瀑布圖、年度影響與敏感度 |
| 貿易與風險 `/risk` | 區域鋼材貿易矩陣、淨出口國、鐵礦供需、各國產量、咽喉要道風險表、政策時間軸 |
| 資料與方法 `/about` | 資料來源、計算方法、已知限制、最近更新時間 |

## 本機執行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/update_data.py      # 抓資料（約 2–4 分鐘）
.venv/bin/python app.py                      # 開 http://127.0.0.1:8050
```

## 專案結構

```
app.py                  入口：版面外框、路由、語言切換
core/                   與介面無關的邏輯（第二階段可直接給 FastAPI 重用）
  config.py             路徑、價格序列定義、色票
  fetch.py              抓資料（新浪期貨、Yahoo Finance）。只有更新腳本會呼叫
  data.py               讀取 static/cache 資料（檔案變動自動重新載入）
  analytics.py          利差、分位數、同業評分、情境模型
  i18n.py               中英文字串
pages/                  每頁一個模組：layout(lang) + register(app)
scripts/
  update_data.py        更新價格、股價、基本面 → data/cache/
  collect_ais.py        收集 AIS 船位快照 → data/cache/ais_snapshot.json
data/static/            人工整理資料（可直接編輯 JSON，不用改程式）
  companies.json        公司清單、座標、產量、代碼
  worldsteel_2024.json  各國產量、貿易矩陣、鐵礦貿易
  geo_layers.json       咽喉要道、港口、航線
  events.json           政策／事件時間軸
  fleet.json            要追蹤的船（MMSI）
data/cache/             機器抓的資料（由排程更新並 commit）
.github/workflows/      GitHub Actions 每日更新
```

## 開啟 AIS 即時船位（免費）

1. 到 https://aisstream.io 用 GitHub 登入，建立 API key
2. 本機：`export AISSTREAM_API_KEY=你的key` 後執行 `.venv/bin/python scripts/collect_ais.py --seconds 300`
3. 線上：GitHub repo → Settings → Secrets → Actions 新增 `AISSTREAM_API_KEY`，每日排程就會順便抓
4. 要追蹤特定船（例如中鋼運通船隊），把 MMSI 填進 `data/static/fleet.json`

## 部署上線（免費方案）

1. 建 GitHub repo，把專案 push 上去
2. [Render](https://render.com) → New → Web Service → 連到 repo
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:server --workers 2 --timeout 120`
   - Instance type: Free
3. GitHub Actions 每個平日自動更新資料並 commit，Render 偵測到 push 會自動重新部署

Render 免費方案閒置 15 分鐘會休眠，下一次開啟要等約 30–60 秒。不想要休眠時再升級（約 USD 7/月）。

## 新增其他產業

1. 新增 `data/static/<industry>_companies.json`（格式同 `companies.json`）
2. 在 `core/config.py` 的 `PRICE_SERIES` 加入該產業價格（設定 `industry` 標籤）
3. 頁面加產業選擇器，`data.companies(industry)` 已預留參數

## 免責聲明

僅供參考，非投資建議。免費資料可能延遲或有誤，決策前請查核原始資料。
