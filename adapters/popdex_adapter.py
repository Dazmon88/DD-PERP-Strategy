"""
PopDEX Exchange Adapter Implementation

Implements BasePerpAdapter for PopDEX (Morph Tachyon).
读接口走 REST；行情/账户推送走公共 WebSocket。
写接口（下单/撤单）走 Agent Key + Order 预编译链上交易。
"""
from __future__ import annotations

import os
import sys
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.base_adapter import BasePerpAdapter, Balance, Order, Position
from exchange.exchange_popdex.popdex_protocol.orders import client_oid_text
from exchange.exchange_popdex.popdex_protocol.perp_http import PopDEXPerpHTTP
from exchange.exchange_popdex.popdex_protocol.perps_auth import PopDEXAuth
from exchange.exchange_popdex.popdex_protocol.perps_wss import PopDEXMarketStream

# PopDEX orderbook levels 枚举
_ORDERBOOK_LEVELS = (1, 5, 25, 50, 100, 200)

_STATUS_MAP = {
    "new": "open",
    "open": "open",
    "pending": "pending",
    "resting": "open",
    "partiallyfilled": "partially_filled",
    "partially_filled": "partially_filled",
    "filled": "filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "rejected": "rejected",
}

# 套利等策略可能沿用 StandX 频道名，这里做一层映射
_CHANNEL_ALIAS = {
    "depth_book": "books1",
    "depth": "books1",
    "orderbook": "books1",
    "book": "books1",
}

_TIF_ALIAS = {
    "alo": "postonly",
    "post_only": "postonly",
    "post-only": "postonly",
}


def _unwrap_data(payload: Any) -> Any:
    """HTTP 客户端可能返回裸 data，或带 cursor/updatedTime 的包装。"""
    if isinstance(payload, dict) and "data" in payload and (
        "cursor" in payload
        or "updatedTime" in payload
        or "code" in payload
        or "total" in payload
    ):
        return payload["data"]
    return payload


def _nearest_levels(depth: int) -> int:
    for level in _ORDERBOOK_LEVELS:
        if depth <= level:
            return level
    return _ORDERBOOK_LEVELS[-1]


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _map_side(side: str) -> str:
    s = (side or "").lower()
    if s in ("buy", "long"):
        return "buy"
    if s in ("sell", "short"):
        return "sell"
    return s


def _map_position_side(position_side: str) -> str:
    s = (position_side or "").lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return s or "long"


def _map_order_status(status: str) -> str:
    key = (status or "").replace(" ", "").lower()
    return _STATUS_MAP.get(key, "pending")


def _map_order_type(order_type: str) -> str:
    t = (order_type or "").lower()
    if t in ("limit", "market"):
        return t
    return t


def _map_tif(time_in_force: str) -> str:
    t = (time_in_force or "gtc").lower().replace("-", "_")
    return _TIF_ALIAS.get(t, t)


def normalize_popdex_symbol(symbol: str) -> str:
    """BTC-USDT / BTC_USDT_Perp / BTC → BTCUSDT。"""
    s = (symbol or "").strip()
    if not s:
        return s
    if "_" in s and "_Perp" in s:
        s = s.replace("_Perp", "").replace("_", "")
    elif "-" in s:
        s = s.replace("-", "")
    return s.upper()


class PopDEXAdapter(BasePerpAdapter):
    """PopDEX 交易所适配器"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config:
                - exchange_name: "popdex"
                - wallet_id: 主账户/子账户钱包地址（私有读接口必填）
                - agent_key: Agent 私钥（可选；写操作需要，读可不填）
                - network: "mainnet" | "testnet"（默认 mainnet）
                - category: 产品类型，默认 "Futures"
                - base_url / ws_url: 可选覆盖
                - timeout: HTTP 超时秒数
        """
        super().__init__(config)

        self.network = (config.get("network") or "mainnet").strip().lower()
        if self.network not in ("mainnet", "testnet"):
            raise ValueError("network 必须是 mainnet 或 testnet")

        self.category = config.get("category") or "Futures"
        self.wallet_id = (config.get("wallet_id") or config.get("wallet") or "").strip()
        self.agent_key = (
            config.get("agent_key")
            or config.get("signing_key")
            or config.get("private_key")
            or ""
        ).strip()

        base_url = config.get("base_url")
        timeout = float(config.get("timeout", 10.0))
        self.http_client = PopDEXPerpHTTP(
            base_url=base_url,
            network=self.network,
            timeout=timeout,
        )

        self.auth: Optional[PopDEXAuth] = None
        if self.agent_key:
            self.auth = PopDEXAuth(
                private_key=self.agent_key,
                network=self.network,  # type: ignore[arg-type]
                wallet_id=self.wallet_id or None,
            )

        self.ws_url = config.get("ws_url")
        self.market_stream: Optional[PopDEXMarketStream] = None
        self._connected = False
        self._symbol_id_cache: Dict[str, int] = {}

    def _require_wallet(self) -> str:
        if not self.wallet_id:
            raise Exception("未配置 wallet_id，无法调用私有接口")
        return self.wallet_id

    def _require_agent(self) -> str:
        if not self.agent_key or not self.auth:
            raise Exception("写操作需要配置 agent_key（已授权的 Trade Agent 私钥）")
        return self.agent_key

    def _resolve_symbol_id(self, symbol: str) -> tuple[int, str]:
        symbol_name = normalize_popdex_symbol(symbol)
        if str(symbol).isdigit():
            return int(symbol), symbol_name or str(symbol)
        if symbol_name in self._symbol_id_cache:
            return self._symbol_id_cache[symbol_name], symbol_name
        raw = self.http_client.get_symbol(category=self.category, symbol=symbol_name)
        data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
        if not isinstance(data, dict) or data.get("symbolId") is None:
            raise ValueError(f"无法解析 symbolId: {symbol}")
        symbol_id = int(data["symbolId"])
        self._symbol_id_cache[symbol_name] = symbol_id
        return symbol_id, symbol_name

    def connect(self) -> bool:
        """连接校验：公共时间接口；可选查询 Agent。"""
        try:
            self.http_client.get_server_time()
            if self.wallet_id and self.auth:
                try:
                    self.http_client.query_agent(self.auth.agent_address)
                except Exception:
                    pass
            self._connected = True
            return True
        except Exception as e:
            raise Exception(f"PopDEX 连接失败: {e}") from e

    async def connect_market_stream(self) -> PopDEXMarketStream:
        """连接公共 WebSocket（行情与账户推送共用）。"""
        if not self.market_stream:
            self.market_stream = PopDEXMarketStream(
                base_url=self.ws_url,
                network=self.network,
            )
        if not self.market_stream.connected:
            await self.market_stream.connect()
        return self.market_stream

    async def subscribe_market(
        self,
        channel: str,
        symbol: str,
        callback: Optional[Callable] = None,
        category: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        stream = await self.connect_market_stream()
        topic = _CHANNEL_ALIAS.get((channel or "").lower(), channel)
        await stream.subscribe_market(
            topic=topic,
            symbol=normalize_popdex_symbol(symbol),
            category=category or self.category,
            callback=callback,
            **kwargs,
        )

    async def subscribe_account(
        self,
        topic: str,
        callback: Optional[Callable] = None,
        wallet_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        stream = await self.connect_market_stream()
        wid = wallet_id or self._require_wallet()
        await stream.subscribe_account(
            wallet_id=wid,
            topic=topic,
            callback=callback,
            **kwargs,
        )

    def get_balance(self) -> Balance:
        wallet_id = self._require_wallet()
        try:
            overview = _unwrap_data(self.http_client.query_overview(wallet_id))
            if not isinstance(overview, dict):
                raise ValueError(f"unexpected overview payload: {overview!r}")

            equity = _to_decimal(overview.get("accountEquity"))
            available = _to_decimal(overview.get("availableMargin"))
            initial_margin = _to_decimal(overview.get("initialMargin"))

            upnl = Decimal("0")
            balances = overview.get("balances") or []
            if isinstance(balances, list):
                for item in balances:
                    if isinstance(item, dict):
                        upnl += _to_decimal(item.get("upl"))

            return Balance(
                total_balance=equity,
                available_balance=available,
                equity=equity,
                unrealized_pnl=upnl,
                margin_used=initial_margin if initial_margin else None,
                margin_available=available if available else None,
            )
        except Exception as e:
            raise Exception(f"查询余额失败: {e}") from e

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        wallet_id = self._require_wallet()
        try:
            raw = _unwrap_data(self.http_client.query_positions(wallet_id))
            if isinstance(raw, dict):
                items = raw.get("data") or raw.get("positions") or []
            else:
                items = raw or []

            want = normalize_popdex_symbol(symbol) if symbol else None
            positions: List[Position] = []
            for pos in items:
                if not isinstance(pos, dict):
                    continue
                pos_symbol = str(pos.get("symbol") or "")
                if want and normalize_popdex_symbol(pos_symbol) != want:
                    continue

                size = _to_decimal(pos.get("holdQty"))
                if size == 0:
                    continue

                leverage_raw = pos.get("symbolLeverage") or pos.get("leverage")
                leverage = (
                    int(float(leverage_raw)) if leverage_raw not in (None, "") else None
                )
                margin_mode = pos.get("marginMode")
                if isinstance(margin_mode, str):
                    margin_mode = margin_mode.lower()

                positions.append(
                    Position(
                        symbol=pos_symbol,
                        size=abs(size),
                        side=_map_position_side(str(pos.get("positionSide", ""))),
                        entry_price=_to_decimal(pos.get("avgOpenPrice")),
                        mark_price=_to_decimal(pos.get("markPrice")),
                        unrealized_pnl=_to_decimal(pos.get("unPnl")),
                        leverage=leverage,
                        margin_mode=margin_mode,
                    )
                )
            return positions
        except Exception as e:
            raise Exception(f"查询持仓失败: {e}") from e

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "gtc",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Order:
        """
        链上下单（Order 预编译 placeOrder）。

        返回的 order_id 优先为索引侧真实 orderId；若尚未可查则回退 tx_hash，
        并带上 client_order_id 供后续按 clientOid 撤单。
        """
        wallet_id = self._require_wallet()
        agent_key = self._require_agent()
        if order_type.lower() == "limit" and price is None:
            raise ValueError("限价单必须指定价格")

        side_str = _map_side(side)
        tif = _map_tif(time_in_force)
        if kwargs.get("post_only") or kwargs.get("postOnly"):
            tif = "postonly"
        try:
            symbol_id, symbol_name = self._resolve_symbol_id(symbol)
            result = self.http_client.place_order_onchain(
                wallet_id=wallet_id,
                agent_private_key=agent_key,
                symbol_id=symbol_id,
                price=price if price is not None else 0,
                qty=quantity,
                side=side_str,
                order_type=order_type,
                time_in_force=tif,
                category=self.category,
                reduce_only=reduce_only,
                position_side=str(kwargs.get("position_side") or "none"),
                slippage=kwargs.get("slippage", 0),
                client_order_id=client_order_id,
                network=self.network,
            )
            encoded = result.get("encoded") or {}
            cl_oid_hex = encoded.get("client_order_id")
            cl_oid = client_oid_text(cl_oid_hex) if cl_oid_hex else None

            rpc = result.get("rpc") or {}
            tx_hash = ""
            if isinstance(rpc, dict):
                tx_hash = str(rpc.get("result") or result["signed"].get("hash") or "")

            order_id = self._resolve_order_id_after_place(
                symbol_name=symbol_name,
                client_oid=cl_oid,
                fallback=tx_hash,
                wait_sec=float(kwargs.get("confirm_wait", 2.0)),
            )

            return Order(
                order_id=order_id,
                symbol=symbol_name,
                side=side_str,
                order_type=order_type.lower(),
                quantity=quantity,
                price=price,
                status="pending",
                time_in_force=tif,
                reduce_only=reduce_only,
                client_order_id=cl_oid or cl_oid_hex,
            )
        except Exception as e:
            raise Exception(f"下单失败: {e}") from e

    def _resolve_order_id_after_place(
        self,
        *,
        symbol_name: str,
        client_oid: Optional[str],
        fallback: str,
        wait_sec: float = 2.0,
    ) -> str:
        if wait_sec <= 0 or not client_oid:
            return fallback
        deadline = time.time() + wait_sec
        want = client_oid.lower()
        while time.time() < deadline:
            try:
                for order in self.get_open_orders(symbol=symbol_name):
                    oid = (order.client_order_id or "").strip()
                    if oid.lower() == want and order.order_id:
                        return str(order.order_id)
            except Exception:
                pass
            time.sleep(0.15)
        return fallback

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        wallet_id = self._require_wallet()
        agent_key = self._require_agent()
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            self.http_client.cancel_order_onchain(
                wallet_id=wallet_id,
                agent_private_key=agent_key,
                order_id=order_id,
                client_order_id=client_order_id,
                network=self.network,
            )
            return True
        except Exception as e:
            raise Exception(f"撤单失败: {e}") from e

    def cancel_orders_by_ids(
        self,
        order_id_list: Optional[Sequence[Union[int, str]]] = None,
        cl_ord_id_list: Optional[Sequence[str]] = None,
    ) -> bool:
        """批量撤单：逐笔链上 cancelOrder（兼容 grid_mm / StandX 调用风格）。"""
        ids = list(order_id_list or [])
        cloids = list(cl_ord_id_list or [])
        if not ids and not cloids:
            raise ValueError("必须提供 order_id_list 或 cl_ord_id_list")

        errors: List[str] = []
        for oid in ids:
            try:
                self.cancel_order(order_id=str(oid))
            except Exception as e:
                errors.append(f"order_id={oid}: {e}")
        for cloid in cloids:
            try:
                self.cancel_order(client_order_id=str(cloid))
            except Exception as e:
                errors.append(f"client_order_id={cloid}: {e}")
        if errors:
            raise Exception("批量撤单部分失败: " + "; ".join(errors[:5]))
        return True

    def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        """拉取当前委托后逐笔撤单。"""
        try:
            opens = self.get_open_orders(symbol=symbol)
            if not opens:
                return True
            order_ids = [o.order_id for o in opens if o.order_id]
            cloids = [
                o.client_order_id
                for o in opens
                if not o.order_id and o.client_order_id
            ]
            return self.cancel_orders_by_ids(
                order_id_list=order_ids or None,
                cl_ord_id_list=[c for c in cloids if c] or None,
            )
        except Exception as e:
            raise Exception(f"全部撤单失败: {e}") from e

    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        wallet_id = self._require_wallet()
        if not order_id:
            if client_order_id:
                for order in self.get_open_orders(symbol=symbol):
                    if (order.client_order_id or "").lower() == str(client_order_id).lower():
                        return order
                return None
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            raw = _unwrap_data(self.http_client.query_order(wallet_id, str(order_id)))
            if not raw:
                return None
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            if not isinstance(raw, dict):
                return None
            return self._parse_order(raw)
        except Exception as e:
            raise Exception(f"查询订单失败: {e}") from e

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        wallet_id = self._require_wallet()
        try:
            raw = _unwrap_data(self.http_client.query_open_orders(wallet_id))
            if isinstance(raw, dict):
                items = raw.get("data") or raw.get("orders") or raw.get("result") or []
            else:
                items = raw or []

            want = normalize_popdex_symbol(symbol) if symbol else None
            orders: List[Order] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                order = self._parse_order(item)
                if want and normalize_popdex_symbol(order.symbol) != want:
                    continue
                if order.status not in ("open", "pending", "partially_filled"):
                    continue
                orders.append(order)
            return orders
        except Exception as e:
            raise Exception(f"查询未成交订单失败: {e}") from e

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            symbol_name = normalize_popdex_symbol(symbol)
            raw = _unwrap_data(
                self.http_client.get_tickers(
                    category=self.category, symbol=symbol_name, limit=1
                )
            )
            if isinstance(raw, list):
                item = raw[0] if raw else {}
            elif isinstance(raw, dict):
                item = raw
            else:
                item = {}

            def _f(key: str) -> Optional[float]:
                val = item.get(key)
                if val is None or val == "":
                    return None
                return float(val)

            bid = _f("bid1Price")
            ask = _f("ask1Price")
            mid = None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2.0

            return {
                "symbol": item.get("symbol", symbol_name),
                "bid_price": bid,
                "ask_price": ask,
                "last_price": _f("lastPrice"),
                "mid_price": mid,
                "mark_price": _f("markPrice"),
                "index_price": _f("indexPrice"),
                "funding_rate": _f("fundingRate"),
                "timestamp": int(item.get("updatedTime") or time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取价格失败: {e}") from e

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        try:
            symbol_name = normalize_popdex_symbol(symbol)
            levels = _nearest_levels(depth)
            raw = _unwrap_data(
                self.http_client.get_orderbook(
                    category=self.category,
                    symbol=symbol_name,
                    levels=levels,
                )
            )
            if not isinstance(raw, dict):
                raw = {}

            bids = raw.get("bids") or []
            asks = raw.get("asks") or []
            return {
                "symbol": symbol_name,
                "bids": [[float(p), float(q)] for p, q in bids[:depth]],
                "asks": [[float(p), float(q)] for p, q in asks[:depth]],
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取订单簿失败: {e}") from e

    def _parse_order(self, data: Dict[str, Any]) -> Order:
        side_raw = data.get("side") or data.get("positionSide") or ""
        side = _map_side(str(side_raw))
        if str(side_raw).lower() in ("buy", "sell"):
            side = str(side_raw).lower()

        created_at = None
        updated_at = None
        if data.get("createdAt"):
            try:
                created_at = int(data["createdAt"])
            except (TypeError, ValueError):
                pass
        if data.get("updatedAt"):
            try:
                updated_at = int(data["updatedAt"])
            except (TypeError, ValueError):
                pass

        tif = data.get("timeInForce") or data.get("time_in_force") or "gtc"
        if isinstance(tif, str):
            tif = tif.lower()

        return Order(
            order_id=str(data.get("orderId") or data.get("id") or ""),
            symbol=str(data.get("symbol") or ""),
            side=side,
            order_type=_map_order_type(
                str(data.get("type") or data.get("order_type") or "")
            ),
            quantity=_to_decimal(data.get("qty")),
            price=_to_decimal(data.get("price"))
            if data.get("price") not in (None, "")
            else None,
            filled_quantity=_to_decimal(data.get("filledQty")),
            status=_map_order_status(str(data.get("status") or "")),
            time_in_force=tif,
            reduce_only=bool(data.get("reduceOnly", False)),
            client_order_id=data.get("clientOid") or data.get("cl_ord_id"),
            created_at=created_at,
            updated_at=updated_at,
        )
