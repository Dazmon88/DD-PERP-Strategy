"""
PopDEX WebSocket 客户端

官方：所有频道（含账户/订单/仓位）均通过同一个公共端点：
  主网  wss://ws.popdex.xyz/v1/ws/public
  测试网 wss://testnet-ws.popdex.xyz/v1/ws/public

心跳：每 30s 发送字符串 "ping"，服务端回 "pong"；超过 2 分钟未 ping 会被断开。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Union

import websockets
from websockets.exceptions import ConnectionClosed

WS_URLS = {
    "mainnet": "wss://ws.popdex.xyz/v1/ws/public",
    "testnet": "wss://testnet-ws.popdex.xyz/v1/ws/public",
}


def _callback_key(arg: Dict[str, Any]) -> str:
    """由订阅参数生成回调索引（大小写不敏感）。"""
    topic = str(arg.get("topic", "")).lower()
    if "walletId" in arg or "wallet_id" in arg:
        wallet = arg.get("walletId") or arg.get("wallet_id") or ""
        return f"wallet:{str(wallet).lower()}:{topic}"
    parts = [
        str(arg.get("category", "")).lower(),
        topic,
        str(arg.get("symbol", "")).lower(),
        str(arg.get("interval", "")).lower(),
    ]
    return "market:" + "|".join(parts)


class PopDEXMarketStream:
    """
    PopDEX 公共 WebSocket（行情 + 账户推送共用）。

    订阅行情：
        await stream.subscribe_market("books1", "BTCUSDT", category="Futures", callback=...)
    订阅账户：
        await stream.subscribe_account(wallet_id, "order", callback=...)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        ping_interval_sec: float = 30.0,
    ):
        if base_url:
            self.base_url = base_url
        else:
            if network not in WS_URLS:
                raise ValueError(f"未知 network: {network}")
            self.base_url = WS_URLS[network]
        self.network = network
        self.ws: Optional[Any] = None
        self.callbacks: Dict[str, Callable] = {}
        self.connected = False
        self._connect_time: Optional[float] = None
        self.ping_interval_sec = ping_interval_sec
        self._ping_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """建立 WebSocket 连接并启动收消息 / 心跳任务。"""
        try:
            self.ws = await websockets.connect(
                self.base_url,
                proxy=None,
                ping_interval=None,
                ping_timeout=None,
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
                    if message == "pong":
                        continue
                    if isinstance(message, (bytes, bytearray)):
                        message = message.decode("utf-8")
                    if message == "pong":
                        continue
                    data = json.loads(message)
                    asyncio.create_task(self._handle_message(data))
                except json.JSONDecodeError:
                    # 非 JSON（如纯文本 pong）已处理
                    continue
                except Exception as e:
                    print(f"处理消息错误: {e}")
        except ConnectionClosed:
            self.connected = False

    async def _ping_loop(self) -> None:
        """官方要求发送字符串 \"ping\"，不是 WebSocket protocol ping。"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval_sec)
                if self.ws and self.connected:
                    await self.ws.send("ping")
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
        """
        推送消息通常含 arg / topic；订阅确认含 event=subscribe。
        按 arg 匹配回调；同时支持按 topic 兜底。
        """
        # 订阅/退订确认也可回调（key = event）
        event = data.get("event")
        if event and event in self.callbacks:
            await self._invoke_callback(self.callbacks[event], data)

        arg = data.get("arg") or data.get("args")
        if isinstance(arg, dict):
            key = _callback_key(arg)
            if key in self.callbacks:
                await self._invoke_callback(self.callbacks[key], data)
                return
            topic = arg.get("topic")
            if topic and str(topic).lower() in self.callbacks:
                await self._invoke_callback(self.callbacks[str(topic).lower()], data)
                return

        topic = data.get("topic")
        if topic and str(topic).lower() in self.callbacks:
            await self._invoke_callback(self.callbacks[str(topic).lower()], data)

    async def subscribe(self, args: List[Dict[str, Any]], callback: Optional[Callable] = None) -> None:
        """
        底层订阅：发送 {"op":"subscribe","args":[...]}。

        若提供 callback，会为每个 arg 注册回调键。
        """
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        if not args:
            raise ValueError("args 不能为空")

        msg = {"op": "subscribe", "args": args}
        payload = json.dumps(msg, separators=(",", ":"))
        if len(payload.encode("utf-8")) > 4096:
            raise ValueError("订阅消息超过 4096 字节限制")

        if callback:
            for arg in args:
                self.callbacks[_callback_key(arg)] = callback
                topic = arg.get("topic")
                if topic:
                    self.callbacks[str(topic).lower()] = callback

        await self.ws.send(payload)

    async def unsubscribe(self, args: List[Dict[str, Any]]) -> None:
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        await self.ws.send(json.dumps({"op": "unsubscribe", "args": args}))
        for arg in args:
            self.callbacks.pop(_callback_key(arg), None)

    async def subscribe_market(
        self,
        topic: str,
        symbol: str,
        category: str = "Futures",
        interval: Optional[str] = None,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """
        订阅行情频道。

        topic 示例: ticker / kline / books / books1 / books5 / books50 / trade
        """
        arg: Dict[str, Any] = {
            "category": category,
            "topic": topic,
            "symbol": symbol,
            **extra,
        }
        if interval is not None:
            arg["interval"] = interval
        await self.subscribe([arg], callback=callback)

    async def subscribe_account(
        self,
        wallet_id: str,
        topic: str,
        callback: Optional[Callable] = None,
        **extra: Any,
    ) -> None:
        """
        订阅账户频道。

        topic 示例: account / order / position / fill
        """
        arg: Dict[str, Any] = {
            "walletId": wallet_id,
            "topic": topic,
            **extra,
        }
        await self.subscribe([arg], callback=callback)

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


# 别名：账户流与行情共用同一端点，便于对照 StandX 的 OrderStream 命名
PopDEXAccountStream = PopDEXMarketStream
