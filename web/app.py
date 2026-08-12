"""
RWA / 美股永续资金费率对比 API + 静态前端。

启动:
  cd web && ../venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from calendar_events import fetch_week_calendar
from collector import FETCHERS, FundingCollector, build_matrix
from live import live_hub
from prices import DEFAULT_EXCHANGES, fetch_multi_history
from valuation import fetch_trailing_pe, list_top_tickers, search_tickers

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Funding Matrix", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

collector = FundingCollector(ttl_seconds=45.0)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/funding/exchanges")
def list_exchanges():
    return {"exchanges": list(FETCHERS.keys())}


@app.get("/api/funding/matrix")
def funding_matrix(
    category: Optional[str] = Query(
        default="rwa",
        description="逗号分隔: rwa,stock,crypto,commodity,index,etf；空=全部。rwa=股票+商品+ETF+指数",
    ),
    pairs: Optional[str] = Query(default=None, description="逗号分隔交易对，如 AAPL,NVDA"),
    exchanges: Optional[str] = Query(
        default="ondo,arcus,standx,hype,lighter",
        description="逗号分隔交易所",
    ),
    display: str = Query(
        default="rate_1h",
        description="展示字段: rate | rate_1h | rate_8h | apr（各所均为 1h 结算）",
    ),
    min_venues: int = Query(default=1, ge=1, le=10),
    force: bool = Query(default=False),
):
    if display not in ("rate", "rate_1h", "rate_8h", "apr"):
        display = "rate_8h"

    ex_list = [x.strip().lower() for x in (exchanges or "").split(",") if x.strip()]
    cat_list = [x.strip().lower() for x in (category or "").split(",") if x.strip()]
    pair_list = [x.strip().upper() for x in (pairs or "").split(",") if x.strip()]

    payload = collector.collect(exchanges=ex_list or None, force=force)
    return build_matrix(
        payload,
        categories=cat_list or None,
        pairs=pair_list or None,
        exchanges=ex_list or None,
        display=display,
        min_venues=min_venues,
    )


@app.get("/api/calendar/week")
def calendar_week(force: bool = Query(default=False)):
    """本周（美东周一–周五）财报 + 美国/重要经济数据，按发布时间排序。"""
    # 用矩阵缓存标记哪些 ticker 有永续
    payload = collector.collect(force=False)
    perps = {
        str(s.get("pair") or "").upper()
        for s in payload.get("snapshots") or []
        if s.get("pair")
    }
    return fetch_week_calendar(perps_pairs=perps, force=force)


@app.get("/api/prices/history")
def prices_history(
    pair: str = Query(..., description="统一交易对，如 AAPL / XAU"),
    exchanges: Optional[str] = Query(default="ondo,arcus,standx,hype,lighter"),
    interval: str = Query(default="5m"),
    hours: float = Query(default=48.0, ge=1.0, le=720.0),
):
    ex_list = [x.strip().lower() for x in (exchanges or "").split(",") if x.strip()]
    return fetch_multi_history(
        pair,
        exchanges=ex_list or None,
        interval=interval,
        hours=hours,
    )


@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket, pair: str = Query(default="AAPL")):
    await live_hub.connect(
        websocket,
        pair=pair,
        exchanges=list(DEFAULT_EXCHANGES),
    )


@app.get("/api/valuation/pe")
def valuation_pe(
    symbol: str = Query(..., description="美股代码，如 AAPL / GOOG"),
    range: str = Query(default="5y", description="1y | 3y | 5y | max"),
    force: bool = Query(default=False),
):
    """自建 Trailing P/E（TTM）日频序列。"""
    try:
        return fetch_trailing_pe(symbol, range_key=range, force=force)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/valuation/tickers/top")
def valuation_tickers_top(limit: int = Query(default=10, ge=1, le=20)):
    """市值前列默认下拉（用于估值搜索）。"""
    return {"items": list_top_tickers(limit=limit), "source": "curated_mktcap"}


@app.get("/api/valuation/tickers/search")
def valuation_tickers_search(
    q: str = Query(default="", description="代码或公司名"),
    limit: int = Query(default=12, ge=1, le=30),
):
    """搜索美股代码；空查询返回市值前十。"""
    return {"q": q, "items": search_tickers(q, limit=limit)}


@app.get("/chart")
def chart_page():
    return FileResponse(os.path.join(STATIC_DIR, "chart.html"))


@app.get("/valuation")
def valuation_page():
    return FileResponse(os.path.join(STATIC_DIR, "valuation.html"))


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
