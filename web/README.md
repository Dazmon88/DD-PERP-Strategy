# FundRate — RWA 永续资金费率矩阵

对比 Ondo / Arcus / StandX / Hype / Lighter 公开资金费率，找出可做费率套利的 RWA（美股等）永续合约。

## RWA 标识说明

| 交易所 | 有官方 RWA/品类字段？ | 本站怎么认 |
|--------|----------------------|------------|
| **Ondo** | 有 `tags`：Stock / ETF / Index / Commodity / Crypto | 直接用 |
| **Arcus** | 有 `category`：EQUITIES / INDICES / COMMODITIES / CRYPTO | 直接用 |
| **StandX** | 无官方 RWA 字段 | `query_market_overview` + ticker 启发式（股票/商品/加密） |
| **Hype** | 主簿无；TradFi 在 HIP-3 dex **`xyz`**，符号 `xyz:AAPL` | 拉 `metaAndAssetCtxs&dex=xyz`，前缀即 RWA 标识 |
| **Lighter** | **无**官方 RWA 字段 | 用 `strategy_index`（5/6/7≈股权，3≈商品，2≈加密）+ ticker 细分 ETF/指数 |

## 启动

```bash
../venv/bin/pip install -r requirements.txt
../venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
```

浏览器打开 `http://localhost:8080`。

矩阵任意行点击 → `/chart?pair=AAPL`：Lightweight Charts 多所折线，悬停显示各所价格；历史走 REST，实时走本服务 WSS（服务端轮询各所 mid 后推送）。

## API

- `GET /api/health`
- `GET /api/funding/matrix?category=stock&display=rate_8h&exchanges=ondo,arcus,standx,hype,lighter`
- `GET /api/calendar/week` — 本周（美东周一–周五）财报 + 重要经济数据（Nasdaq 公开源）
- `GET /api/prices/history?pair=TSLA&interval=5m&hours=48&exchanges=ondo,arcus,standx,hype,lighter`
- `GET /api/valuation/pe?symbol=AAPL&range=5y` — 自建 Trailing P/E（TTM）日频；缓存 `data/valuation/`
- `WS /ws/prices?pair=AAPL` → `{type:"tick", prices:{ondo,arcus,...}, ts}`
- `GET /chart?pair=AAPL`
- `GET /valuation?symbol=AAPL` — 估值曲线页（日历财报点击进入）

估值说明：PE = 日收盘价 ÷ 近四季已披露稀释 EPS（SEC XBRL）。价格源优先 `yfinance`，失败时可设环境变量 `TWELVEDATA_API_KEY`（Twelve Data 免费 key）。非 Bloomberg BEst / Forward P/E。

`display`：`rate` | `rate_1h` | `rate_8h` | `apr`

说明：Lighter 公开 K 线常 403，图表上可能只有实时点；Ondo / Arcus / Hype 历史一般可用。
