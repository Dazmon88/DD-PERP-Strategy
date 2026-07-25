"""
Ondo Perps WebSocket 客户端

端点: wss://api.ondoperps.xyz/ws
心跳: {"op":"ping"} → {"type":"pong"}；空闲约 180s 断开
私有频道需先 login（JWT 或 API Key HMAC）
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

import websockets
from websockets.exceptions import ConnectionClosed

from .perps_auth import OndoPerpAuth

WS_URLS = {
    "mainnet": "wss://api.ondoperps.xyz/ws",
    "sandbox": "wss://api.ondoperps-sandbox.xyz/ws",
}

PUBLIC_CHANNELS = {
    "topOfBooksPerps",
    "depthBooksPerps",
    "tradesPerps",
    "fundingRatesPerps",
    "markPricesPerps",
    "kLinePerps",
}

PRIVATE_CHANNELS = {
    "ordersPerps",
    "fillsPerps",
    "positionsPerps",
    "balancePerps",
    "ordersSummariesPerps",
    "fundingPaymentsPerps",
    "liquidationPerps",
    "liquidationAnnouncementsPerps",
    "marginTransfersPerps",
    "cancelAllOrdersAfterPerps",
    "deposits",
    "withdrawals",
}


class OndoPerpStream:
    """
    Ondo Perps WebSocket（行情 + 私有推送共用一端点）。

    用法:
        stream = OndoPerpStream(auth=auth)
        await stream.connect()
        await stream.login()
        await stream.subscribe("ordersPerps", markets=["AAPL-USD.P"], callback=...)
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        auth: Optional[OndoPerpAuth] = None,
        ping_interval_sec: float = 30.0,
    ):
        if base_url:
            self.base_url = base_url
        else:
            if network not in WS_URLS:
                raise ValueError(f"未知 network: {network}")
            self.base_url = WS_URLS[network]
        self.network = network
        self.auth = auth
        self.ws: Optional[Any] = None
        self.callbacks: Dict[str, Callable] = {}
        self.connected = False
        self.logged_in = False
        self._connect_time: Optional[float] = None
        self.ping_interval_sec = ping_interval_sec
        self._ping_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        try:
            self.ws = await websockets.connect(
                self.base_url,
                proxy=None,
                ping_interval=None,
                ping_timeout=None,
                max_size=32 * 1024,
            )
            self.connected = True
            self.logged_in = False
            self._connect_time = time.time()
            self._recv_task = asyncio.create_task(self._receive_messages())
            self._ping_task = asyncio.create_task(self._ping_loop())
        except Exception as e:
            self.connected = False
            raise Exception(f"WebSocket 连接失败: {e}") from e

    async def _receive_messages(self) -> None:
        try:
            async for message in self.ws:
                try:
                    if isinstance(message, (bytes, bytearray)):
                        message = message.decode("utf-8")
                    data = json.loads(message)
                    asyncio.create_task(self._handle_message(data))
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"处理消息错误: {e}")
        except ConnectionClosed:
            self.connected = False
            self.logged_in = False

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval_sec)
                if self.ws and self.connected:
                    await self.ws.send(json.dumps({"op": "ping"}))
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"心跳错误: {e}")
            self.connected = False

    async def _invoke_callback(self, callback: Callable, data: Dict[str, Any]) -> None:
        if asyncio.iscoroutinefunction(callback):
            await callback(data)
        else:
            callback(data)

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        msg_type = data.get("type")
        if msg_type == "loggedIn":
            self.logged_in = True
        if msg_type and msg_type in self.callbacks:
            await self._invoke_callback(self.callbacks[msg_type], data)

        channel = data.get("channel")
        if channel and str(channel) in self.callbacks:
            await self._invoke_callback(self.callbacks[str(channel)], data)
            return

        # 兜底：任意 update
        if msg_type == "update" and "*" in self.callbacks:
            await self._invoke_callback(self.callbacks["*"], data)

    async def send(self, payload: Dict[str, Any]) -> None:
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        await self.ws.send(json.dumps(payload, separators=(",", ":")))

    async def login(self, *, use_jwt: Optional[bool] = None) -> None:
        if not self.auth:
            raise ValueError("login 需要 OndoPerpAuth")
        await self.send(self.auth.ws_login_message(use_jwt=use_jwt))

    async def subscribe(
        self,
        channel: str,
        *,
        markets: Optional[Sequence[str]] = None,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """
        订阅频道。

        报文: {"op":"subscribe","channel":"...","markets":[...], ...}
        """
        if callback:
            self.callbacks[channel] = callback
        msg: Dict[str, Any] = {"op": "subscribe", "channel": channel, **extra}
        if markets is not None:
            msg["markets"] = list(markets)
        await self.send(msg)

    async def unsubscribe(
        self,
        channel: str,
        *,
        markets: Optional[Sequence[str]] = None,
        **extra: Any,
    ) -> None:
        msg: Dict[str, Any] = {"op": "unsubscribe", "channel": channel, **extra}
        if markets is not None:
            msg["markets"] = list(markets)
        await self.send(msg)
        self.callbacks.pop(channel, None)

    async def subscribe_market(
        self,
        channel: str,
        markets: Optional[Sequence[str]] = None,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """订阅公共行情频道（topOfBooksPerps / depthBooksPerps / ...）。"""
        await self.subscribe(
            channel, markets=markets, callback=callback, **extra
        )

    async def subscribe_private(
        self,
        channel: str,
        markets: Optional[Sequence[str]] = None,
        callback: Optional[Callable] = None,
        *,
        auto_login: bool = True,
        **extra: Any,
    ) -> None:
        """订阅私有频道；必要时自动 login。"""
        if auto_login and not self.logged_in:
            await self.login()
            # 短暂等待 loggedIn（不阻塞太久）
            for _ in range(20):
                if self.logged_in:
                    break
                await asyncio.sleep(0.05)
        await self.subscribe(
            channel, markets=markets, callback=callback, **extra
        )

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
            self.connected = False
            self.logged_in = False
            self._connect_time = None
        for task in (self._ping_task, self._recv_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._ping_task = None
        self._recv_task = None


# 别名：对齐 popdex / standx 命名
OndoMarketStream = OndoPerpStream
OndoAccountStream = OndoPerpStream
