"""图表页实时价：服务端聚合后经 WebSocket 推给前端。

MVP 用公开 REST 轮询各所 mid/mark；前端只连本服务一条 WSS。
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from normalize import canonical_base
from prices import DEFAULT_EXCHANGES, EXCHANGE_COLORS, fetch_live_mids


class LivePriceHub:
    def __init__(self, interval: float = 1.5):
        self.interval = interval
        self._subs: Dict[str, Set[WebSocket]] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, pair: str, exchanges: list[str]) -> None:
        await ws.accept()
        key = canonical_base(pair)
        async with self._lock:
            self._subs.setdefault(key, set()).add(ws)
            cached = self._cache.get(key)
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._loop())
        try:
            await ws.send_text(json.dumps({"type": "hello", "pair": key, "ts": int(time.time())}))
            if cached:
                await ws.send_text(json.dumps(cached))
            # 不阻塞收包循环；后台拉最新价
            asyncio.create_task(self._push_pair(key, exchanges))
            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                    try:
                        data = json.loads(msg)
                        if isinstance(data, dict) and data.get("exchanges"):
                            exchanges = [
                                str(x).lower()
                                for x in data["exchanges"]
                                if str(x).strip()
                            ]
                            asyncio.create_task(self._push_pair(key, exchanges))
                    except Exception:
                        pass
                except asyncio.TimeoutError:
                    await ws.send_text(json.dumps({"type": "ping", "ts": int(time.time())}))
        except Exception:
            pass
        finally:
            async with self._lock:
                if key in self._subs:
                    self._subs[key].discard(ws)
                    if not self._subs[key]:
                        del self._subs[key]

    async def _loop(self) -> None:
        while True:
            async with self._lock:
                pairs = list(self._subs.keys())
            if not pairs:
                await asyncio.sleep(self.interval)
                async with self._lock:
                    if not self._subs:
                        return
                continue
            await asyncio.gather(
                *[self._push_pair(p, list(DEFAULT_EXCHANGES)) for p in pairs],
                return_exceptions=True,
            )
            await asyncio.sleep(self.interval)

    async def _push_pair(self, pair: str, exchanges: list[str]) -> None:
        try:
            mids = await asyncio.to_thread(fetch_live_mids, pair, exchanges)
        except Exception:
            return
        # 合并缓存，避免某所超时导致价格闪断
        async with self._lock:
            prev = (self._cache.get(pair) or {}).get("prices") or {}
            merged = {**prev}
            for ex, v in mids.items():
                if v is not None:
                    merged[ex] = v
            payload = {
                "type": "tick",
                "pair": pair,
                "ts": int(time.time()),
                "prices": merged,
                "colors": {ex: EXCHANGE_COLORS.get(ex, "#aaa") for ex in merged},
            }
            self._cache[pair] = payload
            clients = list(self._subs.get(pair, set()))
        text = json.dumps(payload)
        dead = []
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._subs.get(pair, set()).discard(ws)


live_hub = LivePriceHub(interval=1.5)
