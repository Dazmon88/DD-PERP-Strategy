"""
Arcus WebSocket 客户端

端点:
  主网  wss://api.arcus.xyz/v1/ws
  测试网 wss://api.testnet.arcus.xyz/v1/ws

一连接复用：频道订阅 + 交易 RPC（post/get）。
下单无 cancel-on-disconnect。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any, Callable, Dict, Optional, Union

import websockets
from websockets.exceptions import ConnectionClosed

from .orders import (
    build_cancel_order_body,
    build_cancel_typed_payload,
    build_place_order_body,
    build_place_typed_payload,
    default_good_til_time_us,
)
from .perps_auth import ArcusAuth, timestamp_ns

WS_URLS = {
    "mainnet": "wss://api.arcus.xyz/v1/ws",
    "testnet": "wss://api.testnet.arcus.xyz/v1/ws",
    "staging": "wss://api.staging.arcus.xyz/v1/ws",
}

# 常见频道名（以官方 Channels 文档为准；大小写保持文档形式）
PUBLIC_CHANNELS = {
    "bbo",
    "candles",
    "l2Orderbook",
    "l2OrderbookUpdates",
    "trades",
    "markets",
    "oraclePrices",
    "predictedFunding",
    "exchangeAttributeUpdates",
}

PRIVATE_CHANNELS = {
    "account",
    "accountAttributeUpdates",
    "accountTransferUpdates",
    "funding",
    "orders",
    "positions",
    "userFills",
}


class ArcusPerpStream:
    """
    Arcus WebSocket（行情 + 账户 + 交易 RPC）。

    用法:
        stream = ArcusPerpStream(auth=auth, network="testnet")
        await stream.connect()
        await stream.subscribe("bbo", id="btc", callback=...)
        resp = await stream.place_order(...)
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        auth: Optional[ArcusAuth] = None,
        ping_interval_sec: float = 20.0,
        request_timeout_sec: float = 15.0,
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
        self._connect_time: Optional[float] = None
        self.ping_interval_sec = ping_interval_sec
        self.request_timeout_sec = request_timeout_sec
        self._ping_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._req_id = 0
        self._pending: Dict[int, asyncio.Future] = {}

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def connect(self) -> None:
        try:
            self.ws = await websockets.connect(
                self.base_url,
                proxy=None,
                ping_interval=None,
                ping_timeout=None,
                max_size=8 * 1024 * 1024,
            )
            self.connected = True
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
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionClosed(None, None))
            self._pending.clear()

    async def _ping_loop(self) -> None:
        """依赖 websockets 底层或应用层；此处发空闲保活 get time（若失败则忽略）。"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval_sec)
                if not (self.ws and self.connected):
                    continue
                # 官方未强制应用层 ping；用轻量 get 探活（失败不抛）
                try:
                    await self.rpc_get("time", {}, wait=False)
                except Exception:
                    pass
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
        # RPC 响应：带数字 id
        req_id = data.get("id")
        if isinstance(req_id, int) and req_id in self._pending:
            fut = self._pending.pop(req_id)
            if not fut.done():
                fut.set_result(data)
            return

        msg_type = data.get("type")
        if msg_type and msg_type in self.callbacks:
            await self._invoke_callback(self.callbacks[msg_type], data)

        channel = data.get("channel")
        if channel and str(channel) in self.callbacks:
            await self._invoke_callback(self.callbacks[str(channel)], data)
            return

        # 订阅 id 回调
        sub_id = data.get("id")
        if isinstance(sub_id, str) and sub_id in self.callbacks:
            await self._invoke_callback(self.callbacks[sub_id], data)
            return

        if "*" in self.callbacks:
            await self._invoke_callback(self.callbacks["*"], data)

    async def send(self, payload: Dict[str, Any]) -> None:
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        await self.ws.send(json.dumps(payload, separators=(",", ":")))

    async def subscribe(
        self,
        channel: str,
        *,
        id: Optional[str] = None,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """
        {"type":"subscribe","channel":"...","id":"..."}
        """
        sub_id = id or channel
        if callback:
            self.callbacks[channel] = callback
            self.callbacks[sub_id] = callback
        msg: Dict[str, Any] = {
            "type": "subscribe",
            "channel": channel,
            "id": sub_id,
            **extra,
        }
        await self.send(msg)

    async def unsubscribe(self, channel: str, *, id: Optional[str] = None) -> None:
        sub_id = id or channel
        await self.send({"type": "unsubscribe", "channel": channel, "id": sub_id})
        self.callbacks.pop(channel, None)
        self.callbacks.pop(sub_id, None)

    async def rpc_post(
        self,
        method: str,
        payload: Dict[str, Any],
        *,
        signature: str,
        timestamp: Union[int, str],
        wait: bool = True,
        req_id: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("交易 RPC 需要 ArcusAuth")
        rid = req_id if req_id is not None else self._next_id()
        envelope = {
            "type": "post",
            "id": rid,
            "request": {
                "type": method,
                "payload": payload,
                "apiKey": self.auth.api_key,
                "timestamp": str(timestamp),
                "signature": signature,
            },
        }
        if not wait:
            await self.send(envelope)
            return None

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[rid] = fut
        await self.send(envelope)
        try:
            return await asyncio.wait_for(fut, timeout=self.request_timeout_sec)
        except Exception:
            self._pending.pop(rid, None)
            raise

    async def rpc_get(
        self,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        wait: bool = True,
    ) -> Any:
        rid = self._next_id()
        envelope = {
            "type": "get",
            "id": rid,
            "request": {"type": method, "payload": payload or {}},
        }
        if not wait:
            await self.send(envelope)
            return None
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[rid] = fut
        await self.send(envelope)
        try:
            return await asyncio.wait_for(fut, timeout=self.request_timeout_sec)
        except Exception:
            self._pending.pop(rid, None)
            raise

    async def place_order(
        self,
        *,
        address: str,
        account_index: int,
        market_id: int,
        side: str,
        quantity: Union[str, int, float],
        price: Union[str, int, float],
        tick_size: Union[str, float],
        step_size: Union[str, float],
        order_type: str = "LIMIT",
        time_in_force: str = "GTT",
        reduce_only: bool = False,
        client_id: Optional[str] = None,
        good_til_time_us: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("place_order 需要 ArcusAuth")
        gtt = int(good_til_time_us or default_good_til_time_us())
        ts = timestamp_ns()
        typed = build_place_typed_payload(
            address=address,
            account_index=account_index,
            market_id=market_id,
            side=side,
            price=price,
            quantity=quantity,
            tick_size=tick_size,
            step_size=step_size,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            good_til_time_us=gtt,
            client_id=client_id,
            timestamp_ns=ts,
        )
        sig = self.auth.sign_typed_payload(typed)
        body = build_place_order_body(
            address=address,
            account_index=account_index,
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            good_til_time_us=gtt,
            client_id=client_id,
            timestamp_ns=ts,
        )
        return await self.rpc_post(
            "placeOrder", body, signature=sig, timestamp=ts
        )

    async def cancel_order(
        self,
        *,
        address: str,
        account_index: int,
        market_id: int,
        order_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("cancel_order 需要 ArcusAuth")
        ts = timestamp_ns()
        typed = build_cancel_typed_payload(
            address=address,
            account_index=account_index,
            market_id=market_id,
            order_id=order_id,
            client_id=client_id,
            timestamp_ns=ts,
        )
        sig = self.auth.sign_typed_payload(typed)
        body = build_cancel_order_body(
            address=address,
            account_index=account_index,
            market_id=market_id,
            order_id=order_id,
            client_id=client_id,
            timestamp_ns=ts,
        )
        return await self.rpc_post(
            "cancelOrder", body, signature=sig, timestamp=ts
        )

    async def cancel_all_orders(
        self,
        *,
        address: str,
        account_index: int = 0,
        market_id: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("cancel_all_orders 需要 ArcusAuth")
        body: Dict[str, Any] = {
            "address": address,
            "accountIndex": int(account_index),
        }
        if market_id is not None:
            body["marketId"] = int(market_id)
        signed = self.auth.sign_legacy_action(action="cancelAllOrders", body=body)
        return await self.rpc_post(
            "cancelAllOrders",
            body,
            signature=signed["signature"],
            timestamp=signed["timestamp"],
        )

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
            self.connected = False
            self._connect_time = None
        for task in (self._ping_task, self._recv_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._ping_task = None
        self._recv_task = None
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()


# 别名：对齐 popdex / ondo 命名
ArcusMarketStream = ArcusPerpStream
ArcusAccountStream = ArcusPerpStream
