"""
Ondo Perps Exchange Adapter

Implements BasePerpAdapter for Ondo Perps.
REST + API Key HMAC（或 JWT）；行情/私有推送走 WebSocket。
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.base_adapter import BasePerpAdapter, Balance, Order, Position
from exchange.exchange_ondoperp.ondoperp_protocol.orders import (
    make_client_order_id,
    normalize_market,
)
from exchange.exchange_ondoperp.ondoperp_protocol.perp_http import OndoPerpHTTP
from exchange.exchange_ondoperp.ondoperp_protocol.perps_auth import OndoPerpAuth
from exchange.exchange_ondoperp.ondoperp_protocol.perps_wss import OndoPerpStream

_STATUS_MAP = {
    "open": "open",
    "pending": "pending",
    "untriggered": "pending",
    "fullyfilled": "filled",
    "filled": "filled",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "rejected": "rejected",
}

_CHANNEL_ALIAS = {
    "depth_book": "depthBooksPerps",
    "depth": "depthBooksPerps",
    "orderbook": "depthBooksPerps",
    "book": "topOfBooksPerps",
    "ticker": "topOfBooksPerps",
    "trade": "tradesPerps",
    "trades": "tradesPerps",
    "mark": "markPricesPerps",
    "order": "ordersPerps",
    "orders": "ordersPerps",
    "position": "positionsPerps",
    "positions": "positionsPerps",
    "balance": "balancePerps",
    "fill": "fillsPerps",
    "fills": "fillsPerps",
}


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


def _map_position_side(direction: str) -> str:
    s = (direction or "").lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return s or "long"


def _map_order_status(status: str) -> str:
    key = (status or "").replace(" ", "").lower()
    return _STATUS_MAP.get(key, "pending")


def _parse_iso_ms(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _as_list(payload: Any) -> List[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("result", "data", "orders", "positions", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def normalize_ondo_symbol(symbol: str) -> str:
    """
    规范化市场名称为 Ondo 风格，如 AAPL-USD.P。

    兼容: AAPL-USD.P / AAPL-USD / AAPL_USD_Perp / AAPL
    """
    s = (symbol or "").strip()
    if not s:
        return s
    if s.upper().endswith(".P"):
        return normalize_market(s)
    if "_Perp" in s or s.endswith("_P"):
        s = s.replace("_Perp", "").replace("_P", "")
        s = s.replace("_", "-")
    if "-" not in s:
        # 裸 ticker → AAPL-USD.P
        return normalize_market(f"{s}-USD.P")
    if not s.upper().endswith(".P"):
        s = f"{s}.P"
    return normalize_market(s)


class OndoAdapter(BasePerpAdapter):
    """Ondo Perps 交易所适配器"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config:
                - exchange_name: "ondo" / "ondoperp" / "ondoperps"
                - key_id / api_key_id: ondoKeyId_...
                - api_secret / secret: ondoApiSecret_...
                - jwt: 可选 Bearer（无 API Key 时）
                - network: mainnet | sandbox
                - base_url / ws_url: 可选覆盖
                - timeout: HTTP 超时秒数
        """
        super().__init__(config)

        self.network = (config.get("network") or "mainnet").strip().lower()
        if self.network not in ("mainnet", "sandbox"):
            raise ValueError("network 必须是 mainnet 或 sandbox")

        key_id = (
            config.get("key_id")
            or config.get("api_key_id")
            or config.get("api_key")
            or ""
        ).strip()
        api_secret = (
            config.get("api_secret")
            or config.get("secret")
            or config.get("signing_key")
            or ""
        ).strip()
        jwt = (config.get("jwt") or config.get("token") or "").strip() or None

        self.auth = OndoPerpAuth(
            key_id=key_id or None,
            api_secret=api_secret or None,
            jwt=jwt,
            network=self.network,  # type: ignore[arg-type]
        )
        timeout = float(config.get("timeout", 15.0))
        self.http_client = OndoPerpHTTP(
            base_url=config.get("base_url"),
            network=self.network,
            auth=self.auth,
            timeout=timeout,
        )
        self.ws_url = config.get("ws_url")
        self.market_stream: Optional[OndoPerpStream] = None
        self._connected = False

    def _require_auth(self) -> None:
        if not self.auth.has_api_key and not self.auth.has_jwt:
            raise Exception("需要配置 key_id+api_secret 或 jwt")

    def connect(self) -> bool:
        try:
            self.http_client.hello()
            if self.auth.has_api_key or self.auth.has_jwt:
                # 鉴权连通性
                self.http_client.get_account()
            self._connected = True
            return True
        except Exception as e:
            raise Exception(f"Ondo 连接失败: {e}") from e

    async def connect_market_stream(self) -> OndoPerpStream:
        if not self.market_stream:
            self.market_stream = OndoPerpStream(
                base_url=self.ws_url,
                network=self.network,
                auth=self.auth,
            )
        if not self.market_stream.connected:
            await self.market_stream.connect()
        return self.market_stream

    async def subscribe_market(
        self,
        channel: str,
        symbol: Optional[str] = None,
        callback: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        stream = await self.connect_market_stream()
        ch = _CHANNEL_ALIAS.get((channel or "").lower(), channel)
        markets = None
        if symbol:
            markets = [normalize_ondo_symbol(symbol)]
        elif kwargs.get("markets"):
            markets = [normalize_ondo_symbol(m) for m in kwargs.pop("markets")]
        await stream.subscribe_market(ch, markets=markets, callback=callback, **kwargs)

    async def subscribe_private(
        self,
        channel: str,
        symbol: Optional[str] = None,
        callback: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        self._require_auth()
        stream = await self.connect_market_stream()
        ch = _CHANNEL_ALIAS.get((channel or "").lower(), channel)
        markets = None
        if symbol:
            markets = [normalize_ondo_symbol(symbol)]
        elif kwargs.get("markets"):
            markets = [normalize_ondo_symbol(m) for m in kwargs.pop("markets")]
        await stream.subscribe_private(
            ch, markets=markets, callback=callback, **kwargs
        )

    def get_balance(self) -> Balance:
        self._require_auth()
        try:
            raw = self.http_client.get_balance()
            if not isinstance(raw, dict):
                raise ValueError(f"unexpected balance payload: {raw!r}")
            equity = _to_decimal(raw.get("marginBalance"))
            available = _to_decimal(raw.get("availableMargin"))
            used = _to_decimal(raw.get("usedMargin"))
            upnl = _to_decimal(raw.get("unrealizedPnl"))
            wallet = _to_decimal(raw.get("walletBalance"))
            return Balance(
                total_balance=wallet if wallet else equity,
                available_balance=available,
                equity=equity,
                unrealized_pnl=upnl,
                margin_used=used if used else None,
                margin_available=available if available else None,
            )
        except Exception as e:
            raise Exception(f"查询余额失败: {e}") from e

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        self._require_auth()
        try:
            params: Dict[str, Any] = {}
            want = normalize_ondo_symbol(symbol) if symbol else None
            if want:
                params["market"] = want
            raw = self.http_client.get_positions(**params)
            items = _as_list(raw)
            positions: List[Position] = []
            for pos in items:
                if not isinstance(pos, dict):
                    continue
                market = str(pos.get("market") or "")
                if want and normalize_ondo_symbol(market) != want:
                    continue
                direction = str(pos.get("direction") or "")
                if direction.lower() == "neutral":
                    continue
                size = _to_decimal(pos.get("netQuantity"))
                if size == 0:
                    continue
                leverage_raw = pos.get("leverage")
                leverage = (
                    int(float(leverage_raw))
                    if leverage_raw not in (None, "")
                    else None
                )
                positions.append(
                    Position(
                        symbol=market,
                        size=abs(size),
                        side=_map_position_side(direction),
                        entry_price=_to_decimal(pos.get("averageEntryPrice")),
                        mark_price=_to_decimal(pos.get("markPrice")),
                        unrealized_pnl=_to_decimal(pos.get("unrealizedPnl")),
                        leverage=leverage,
                        margin_mode=None,
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
        self._require_auth()
        market = normalize_ondo_symbol(symbol)
        side_str = _map_side(side)
        typ = (order_type or "limit").lower()
        if typ == "limit" and price is None:
            raise ValueError("限价单必须指定价格")

        tif = (time_in_force or "gtc").lower().replace("-", "_")
        post_only = kwargs.get("post_only")
        if post_only is None:
            post_only = kwargs.get("postOnly")
        # alo / postonly → GTC + postOnly
        if tif in ("alo", "postonly", "post_only"):
            tif = "gtc"
            if post_only is None:
                post_only = True
        tif_api = tif.upper() if tif in ("gtc", "ioc") else "GTC"

        cloid = client_order_id or kwargs.get("clientOrderId")
        if not cloid and kwargs.get("auto_client_id", True):
            cloid = make_client_order_id("dd")

        try:
            result = self.http_client.place_order(
                market=market,
                side=side_str,
                size=format(quantity, "f") if isinstance(quantity, Decimal) else str(quantity),
                order_type=typ,
                price=(
                    format(price, "f")
                    if isinstance(price, Decimal)
                    else (str(price) if price is not None else None)
                ),
                client_order_id=cloid,
                time_in_force=tif_api if typ == "limit" else None,
                post_only=bool(post_only) if post_only is not None else None,
                reduce_only=reduce_only,
                quote_size=kwargs.get("quote_size") or kwargs.get("quoteSize"),
                take_profit=kwargs.get("take_profit") or kwargs.get("takeProfit"),
                stop_loss=kwargs.get("stop_loss") or kwargs.get("stopLoss"),
            )
            if isinstance(result, dict):
                return self._parse_order(result)
            return Order(
                order_id=str(result or ""),
                symbol=market,
                side=side_str,
                order_type=typ,
                quantity=quantity,
                price=price,
                status="pending",
                time_in_force=tif_api.lower(),
                reduce_only=reduce_only,
                client_order_id=cloid,
            )
        except Exception as e:
            raise Exception(f"下单失败: {e}") from e

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        self._require_auth()
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            self.http_client.cancel_order(
                order_id=order_id, client_order_id=client_order_id
            )
            return True
        except Exception as e:
            raise Exception(f"撤单失败: {e}") from e

    def cancel_orders_by_ids(
        self,
        order_id_list: Optional[Sequence[Union[int, str]]] = None,
        cl_ord_id_list: Optional[Sequence[str]] = None,
    ) -> bool:
        """批量撤单（兼容 grid_mm / StandX 调用风格）。"""
        self._require_auth()
        ids = list(order_id_list or [])
        cloids = list(cl_ord_id_list or [])
        if not ids and not cloids:
            raise ValueError("必须提供 order_id_list 或 cl_ord_id_list")
        try:
            self.http_client.cancel_orders_batch(
                order_ids=ids or None,
                client_order_ids=cloids or None,
            )
            return True
        except Exception as e:
            raise Exception(f"批量撤单失败: {e}") from e

    def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        self._require_auth()
        try:
            market = normalize_ondo_symbol(symbol) if symbol else None
            self.http_client.cancel_all_orders(market=market)
            return True
        except Exception as e:
            raise Exception(f"全部撤单失败: {e}") from e

    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        self._require_auth()
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            raw = self.http_client.get_order(
                order_id=order_id, client_order_id=client_order_id
            )
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
        self._require_auth()
        try:
            params: Dict[str, Any] = {"status": "open", "limit": 1000}
            if symbol:
                params["market"] = normalize_ondo_symbol(symbol)
            raw = self.http_client.get_orders(**params)
            orders: List[Order] = []
            for item in _as_list(raw):
                if not isinstance(item, dict):
                    continue
                order = self._parse_order(item)
                if order.status not in ("open", "pending", "partially_filled"):
                    continue
                orders.append(order)
            return orders
        except Exception as e:
            raise Exception(f"查询未成交订单失败: {e}") from e

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        market = normalize_ondo_symbol(symbol)
        try:
            bid = ask = last = mark = index = funding = None
            # contracts 含 bid/ask/last
            contracts = _as_list(self.http_client.get_contracts())
            for c in contracts:
                if not isinstance(c, dict):
                    continue
                if normalize_ondo_symbol(str(c.get("market") or "")) != market:
                    continue
                bid = float(c["bid"]) if c.get("bid") not in (None, "") else None
                ask = float(c["ask"]) if c.get("ask") not in (None, "") else None
                last = (
                    float(c["lastPrice"])
                    if c.get("lastPrice") not in (None, "")
                    else None
                )
                index = (
                    float(c["indexPrice"])
                    if c.get("indexPrice") not in (None, "")
                    else None
                )
                funding = (
                    float(c["fundingRate"])
                    if c.get("fundingRate") not in (None, "")
                    else None
                )
                break

            try:
                marks = self.http_client.get_mark_prices()
                if isinstance(marks, dict):
                    entry = marks.get(market) or marks.get(symbol)
                    if isinstance(entry, dict):
                        mp = entry.get("markPrice") or entry.get("price")
                        if mp not in (None, ""):
                            mark = float(mp)
            except Exception:
                pass

            mid = None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2.0

            return {
                "symbol": market,
                "bid_price": bid,
                "ask_price": ask,
                "last_price": last,
                "mid_price": mid,
                "mark_price": mark if mark is not None else last,
                "index_price": index,
                "funding_rate": funding,
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取价格失败: {e}") from e

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        market = normalize_ondo_symbol(symbol)
        try:
            raw = self.http_client.get_orderbook(market)
            if not isinstance(raw, dict):
                raw = {}
            bids = raw.get("bids") or []
            asks = raw.get("asks") or []

            def _levels(rows: Any) -> List[List[float]]:
                out: List[List[float]] = []
                for row in rows[:depth]:
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        out.append([float(row[0]), float(row[1])])
                    elif isinstance(row, dict):
                        p = row.get("price") or row.get("px")
                        q = row.get("size") or row.get("qty") or row.get("quantity")
                        if p is not None and q is not None:
                            out.append([float(p), float(q)])
                return out

            return {
                "symbol": market,
                "bids": _levels(bids),
                "asks": _levels(asks),
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取订单簿失败: {e}") from e

    def close_position(
        self,
        symbol: str,
        order_type: str = "market",
        **kwargs: Any,
    ) -> Optional[Order]:
        """市价/限价减仓平仓。"""
        positions = self.get_positions(symbol=symbol)
        if not positions:
            return None
        pos = positions[0]
        if pos.size == 0:
            return None
        close_side = "sell" if pos.side == "long" else "buy"
        return self.place_order(
            symbol=symbol,
            side=close_side,
            order_type=order_type,
            quantity=pos.size,
            price=kwargs.get("price"),
            time_in_force=str(kwargs.get("time_in_force") or "ioc"),
            reduce_only=True,
            client_order_id=kwargs.get("client_order_id"),
            auto_client_id=True,
            post_only=False,
        )

    def _parse_order(self, data: Dict[str, Any]) -> Order:
        side = _map_side(str(data.get("side") or ""))
        tif = data.get("timeInForce") or data.get("time_in_force") or "gtc"
        if isinstance(tif, str):
            tif = tif.lower()
        status = _map_order_status(str(data.get("status") or ""))
        # 部分成交：open 且 filledSize>0
        filled = _to_decimal(data.get("filledSize"))
        qty = _to_decimal(data.get("size") or data.get("qty"))
        if status == "open" and filled > 0 and qty > 0 and filled < qty:
            status = "partially_filled"

        return Order(
            order_id=str(data.get("orderId") or data.get("id") or ""),
            symbol=str(data.get("market") or data.get("symbol") or ""),
            side=side,
            order_type=str(data.get("type") or data.get("order_type") or "limit").lower(),
            quantity=qty,
            price=_to_decimal(data.get("price"))
            if data.get("price") not in (None, "")
            else None,
            filled_quantity=filled,
            status=status,
            time_in_force=tif,
            reduce_only=bool(data.get("reduceOnly", False)),
            client_order_id=data.get("clientOrderId") or data.get("clientOid"),
            created_at=_parse_iso_ms(data.get("createdAt")),
            updated_at=_parse_iso_ms(data.get("updatedAt") or data.get("filledAt")),
        )
