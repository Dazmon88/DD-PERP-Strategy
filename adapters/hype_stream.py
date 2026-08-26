"""Hyperliquid 公共 WebSocket（行情 + 私有推送共用一条连接）。

协议很简单：
    发送 {"method":"subscribe","subscription":{...}} 订阅，
    发送 {"method":"ping"} 保活（官方要求 JSON，不是 protocol ping），
    推送形如 {"channel":"l2Book","data":{...}}。

不用 SDK 自带的 WebsocketManager：它是 threading.Thread + 同步回调，
而 strategy_vs 的 feeds 全是 asyncio 且回调是协程，桥接反而更脆。

builder dex（HIP-3）的 coin 形如 `io:ANTH`，订阅和推送都原样带前缀，
这里不做任何改写。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any, Callable, Dict, Optional

import websockets
from websockets.exceptions import ConnectionClosed

MAINNET_WS_URL = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"

WS_URLS = {
    "mainnet": MAINNET_WS_URL,
    "testnet": TESTNET_WS_URL,
}

# 服务端只认小写地址，传 checksum 大小写会直接回 error 且不订阅
_USER_FIELDS = ("user", "address")


def ws_url_for(base_url: Optional[str], network: str = "mainnet") -> str:
    """从 HTTP base_url 推 ws 地址；给不出就按 network 取默认。"""
    if base_url:
        text = str(base_url).strip().rstrip("/")
        if text.startswith("ws://") or text.startswith("wss://"):
            return text
        if text.startswith("http"):
            return "ws" + text[len("http") :] + "/ws"
    return WS_URLS.get(str(network or "mainnet").lower(), MAINNET_WS_URL)


def _norm_sub(sub: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(sub)
    for key in _USER_FIELDS:
        val = out.get(key)
        if isinstance(val, str) and val:
            out[key] = val.lower()
    return out


def sub_key(sub: Dict[str, Any]) -> str:
    """订阅的分发键，必须和 msg_key 对得上。"""
    typ = str(sub.get("type") or "")
    coin = str(sub.get("coin") or "")
    return f"{typ}:{coin.lower()}" if coin else typ


def msg_key(msg: Dict[str, Any]) -> Optional[str]:
    """推送的分发键。带 coin 的按 coin 细分，否则按 channel。"""
    channel = str(msg.get("channel") or "")
    if not channel or channel in ("pong", "subscriptionResponse"):
        return None
    data = msg.get("data")
    coin = ""
    if isinstance(data, dict):
        coin = str(data.get("coin") or "")
    return f"{channel}:{coin.lower()}" if coin else channel


class HypeMarketStream:
    """一条连接承载 l2Book / userFills / orderUpdates 等所有订阅。

    断线只把 connected 置 False，由调用方（feeds 的外层重试循环）决定
    何时重连；reconnect 时会自动重放已登记的订阅。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        ping_interval_sec: float = 30.0,
    ) -> None:
        self.base_url = ws_url_for(base_url, network)
        self.network = network
        self.ws: Optional[Any] = None
        self.connected = False
        self.ping_interval_sec = float(ping_interval_sec)
        self.last_msg_ts: float = 0.0
        self.last_error: str = ""
        # key -> 回调；key -> 订阅体。重连要按这个重放
        self.callbacks: Dict[str, Callable] = {}
        self._subs: Dict[str, Dict[str, Any]] = {}
        self._ping_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        try:
            self.ws = await websockets.connect(
                self.base_url,
                proxy=None,
                ping_interval=None,
                ping_timeout=None,
                max_size=8 * 1024 * 1024,
            )
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            raise Exception(f"Hype WebSocket 连接失败: {exc}") from exc
        self.connected = True
        self.last_error = ""
        self.last_msg_ts = time.time()
        self._recv_task = asyncio.create_task(self._receive_messages())
        self._ping_task = asyncio.create_task(self._ping_loop())
        # 重连后把之前登记的订阅原样重发
        for payload in list(self._subs.values()):
            with contextlib.suppress(Exception):
                await self._send_subscribe(payload)

    async def _send_subscribe(self, sub: Dict[str, Any]) -> None:
        if self.ws is None:
            raise RuntimeError("WebSocket 未连接")
        await self.ws.send(json.dumps({"method": "subscribe", "subscription": sub}))

    async def _receive_messages(self) -> None:
        try:
            async for raw in self.ws:  # type: ignore[union-attr]
                self.last_msg_ts = time.time()
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", "ignore")
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("channel") == "error":
                    # 订阅被拒（例如地址大小写不对）要看得见，否则会静默无数据
                    self.last_error = str(msg.get("data"))[:200]
                    continue
                key = msg_key(msg)
                if key is None:
                    continue
                callback = self.callbacks.get(key)
                if callback is None:
                    continue
                asyncio.create_task(self._invoke(callback, msg))
        except ConnectionClosed:
            pass
        except Exception as exc:
            self.last_error = str(exc)[:200]
        finally:
            self.connected = False

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval_sec)
                if self.ws is None or not self.connected:
                    return
                await self.ws.send(json.dumps({"method": "ping"}))
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self.last_error = str(exc)[:200]
            self.connected = False

    @staticmethod
    async def _invoke(callback: Callable, msg: Dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            if asyncio.iscoroutinefunction(callback):
                await callback(msg)
            else:
                callback(msg)

    async def subscribe(
        self, sub: Dict[str, Any], callback: Optional[Callable] = None
    ) -> None:
        """按 key 幂等登记：外层重连循环反复调用不会堆叠回调。"""
        payload = _norm_sub(sub)
        key = sub_key(payload)
        if callback is not None:
            self.callbacks[key] = callback
        already = key in self._subs
        self._subs[key] = payload
        if self.connected and not already:
            await self._send_subscribe(payload)

    async def subscribe_market(
        self,
        topic: str,
        symbol: str,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """topic: book/l2book → l2Book；bbo → bbo；trades → trades。"""
        name = str(topic or "").strip().lower()
        typ = {
            "book": "l2Book",
            "books": "l2Book",
            "l2book": "l2Book",
            "bbo": "bbo",
            "ticker": "bbo",
            "trade": "trades",
            "trades": "trades",
        }.get(name, "l2Book")
        await self.subscribe({"type": typ, "coin": symbol, **extra}, callback=callback)

    async def subscribe_account(
        self,
        topic: str,
        user: str,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """topic: fills → userFills；events → userEvents；orders → orderUpdates。

        注意 Hyperliquid 没有推全量持仓的公开频道（webData2 会被拒），
        所以持仓只能 REST 拉，userFills 用来在成交后立刻纠正。
        """
        name = str(topic or "").strip().lower()
        typ = {
            "fill": "userFills",
            "fills": "userFills",
            "userfills": "userFills",
            "event": "userEvents",
            "events": "userEvents",
            "userevents": "userEvents",
            "order": "orderUpdates",
            "orders": "orderUpdates",
            "orderupdates": "orderUpdates",
        }.get(name, name or "userFills")
        await self.subscribe({"type": typ, "user": user, **extra}, callback=callback)

    async def close(self) -> None:
        self.connected = False
        for task in (self._ping_task, self._recv_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._ping_task = None
        self._recv_task = None
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.close()
            self.ws = None


HypeAccountStream = HypeMarketStream


def bbo_from_l2(data: Dict[str, Any]) -> tuple[
    Optional[float], Optional[float], Optional[float], Optional[float]
]:
    """l2Book 推送取一档：levels = [bids, asks]，元素形如 {"px","sz","n"}。"""
    levels = data.get("levels")
    if not isinstance(levels, (list, tuple)) or len(levels) < 2:
        return None, None, None, None

    def top(side: Any) -> tuple[Optional[float], Optional[float]]:
        if not isinstance(side, (list, tuple)) or not side:
            return None, None
        row = side[0]
        if not isinstance(row, dict):
            return None, None
        try:
            return float(row.get("px")), float(row.get("sz"))
        except (TypeError, ValueError):
            return None, None

    bid, bid_sz = top(levels[0])
    ask, ask_sz = top(levels[1])
    return bid, ask, bid_sz, ask_sz


def bbo_from_bbo(data: Dict[str, Any]) -> tuple[
    Optional[float], Optional[float], Optional[float], Optional[float]
]:
    """bbo 推送：{"coin","time","bbo":[bid|null, ask|null]}。"""
    pair = data.get("bbo")
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return None, None, None, None

    def one(row: Any) -> tuple[Optional[float], Optional[float]]:
        if not isinstance(row, dict):
            return None, None
        try:
            return float(row.get("px")), float(row.get("sz"))
        except (TypeError, ValueError):
            return None, None

    bid, bid_sz = one(pair[0])
    ask, ask_sz = one(pair[1])
    return bid, ask, bid_sz, ask_sz
