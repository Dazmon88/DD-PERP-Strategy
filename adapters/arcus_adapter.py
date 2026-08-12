"""
Arcus Exchange Adapter

Implements BasePerpAdapter for Arcus perpetuals.
REST（Ed25519 签名）为主；行情/订单生命周期可走 WebSocket。
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
from exchange.exchange_arcus.arcus_protocol.orders import (
    make_client_id,
    snap_price,
    snap_qty,
)
from exchange.exchange_arcus.arcus_protocol.perp_http import ArcusPerpHTTP
from exchange.exchange_arcus.arcus_protocol.perps_auth import ArcusAuth
from exchange.exchange_arcus.arcus_protocol.perps_wss import ArcusPerpStream

_STATUS_MAP = {
    "ack": "pending",
    "open": "open",
    "pending": "pending",
    "resting": "open",
    "partially_filled": "partially_filled",
    "partiallyfilled": "partially_filled",
    "filled": "filled",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "rejected": "rejected",
}

_CHANNEL_ALIAS = {
    "depth_book": "l2Orderbook",
    "depth": "l2Orderbook",
    "orderbook": "l2Orderbook",
    "book": "bbo",
    "ticker": "bbo",
    "trade": "trades",
    "trades": "trades",
    "order": "orders",
    "orders": "orders",
    "position": "positions",
    "positions": "positions",
    "fill": "userFills",
    "fills": "userFills",
    "account": "account",
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


def _map_position_side(side: str) -> str:
    s = (side or "").lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return s or "long"


def _map_order_status(status: str) -> str:
    key = (status or "").replace(" ", "").lower()
    return _STATUS_MAP.get(key, "pending")


def _map_tif(time_in_force: str) -> str:
    """策略侧 tif → Arcus: GTT / FOK / IOC / ALO。"""
    raw = (time_in_force or "gtt").strip().lower().replace("-", "_")
    aliases = {
        "gtc": "GTT",
        "gtt": "GTT",
        "ioc": "IOC",
        "fok": "FOK",
        "alo": "ALO",
        "postonly": "ALO",
        "post_only": "ALO",
    }
    return aliases.get(raw, "GTT")


def normalize_arcus_symbol(symbol: str) -> str:
    """
    规范化为 Arcus marketDisplayName，如 BTC-USD。

    兼容: BTC-USD / BTC-USDT / BTCUSDT / BTC / BTC_USDT_Perp
    """
    s = (symbol or "").strip()
    if not s:
        return s
    s = s.replace("_Perp", "").replace("_P", "").replace("_", "-")
    upper = s.upper()
    if "-" not in upper:
        for quote in ("USDT", "USDC", "USD"):
            if upper.endswith(quote) and len(upper) > len(quote):
                return f"{upper[:-len(quote)]}-USD"
        return f"{upper}-USD"
    base, quote = upper.split("-", 1)
    if quote in ("USDT", "USDC"):
        quote = "USD"
    return f"{base}-{quote}"


def _as_list(payload: Any, *keys: str) -> List[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys or ("result", "data", "orders", "positions", "items"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                # Arcus positions 可能是 {marketId: position}
                return list(val.values())
    return []


class ArcusAdapter(BasePerpAdapter):
    """Arcus 永续交易所适配器"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config:
                - exchange_name: arcus
                - api_secret / api_private_key / private_key: Ed25519 API 签名私钥
                - api_key / public_key: 可选，Ed25519 公钥（X-API-Key）；不填则由私钥推导
                - address / wallet_id: 主钱包地址
                - account_index: 子账户索引，默认 0
                - network: mainnet | testnet | staging
                - base_url / ws_url / timeout: 可选

            日常交易只需 API Key 对 + address，无需主钱包私钥交互。
            首次注册 API Key 才需要钱包 EIP-712（见 arcus_protocol.account.create_api_key）。
        """
        super().__init__(config)

        self.network = (config.get("network") or "mainnet").strip().lower()
        if self.network not in ("mainnet", "testnet", "staging"):
            raise ValueError("network 必须是 mainnet / testnet / staging")

        private_key = (
            config.get("api_secret")
            or config.get("api_private_key")
            or config.get("private_key")
            or ""
        ).strip()
        api_key_cfg = (
            config.get("api_key")
            or config.get("apiKey")
            or config.get("public_key")
            or ""
        ).strip()
        address = (
            config.get("address")
            or config.get("wallet_id")
            or config.get("wallet")
            or ""
        ).strip()
        account_index = int(config.get("account_index", config.get("accountIndex", 0)))

        if not private_key:
            raise ValueError(
                "需要配置 api_secret（Ed25519 API 签名私钥）。"
                "填写 .generated/arcus.json，字段: api_key / api_secret / address"
            )
        if not address:
            raise ValueError("需要配置 address（主钱包地址）")

        self.auth = ArcusAuth.from_private_key(
            private_key,
            address=address,
            account_index=account_index,
            network=self.network,  # type: ignore[arg-type]
        )
        if api_key_cfg and api_key_cfg.lower().lstrip("0x") != self.auth.api_key.lower():
            raise ValueError(
                "api_key 与 api_secret 不匹配（api_key 应为 Ed25519 公钥，"
                "可由 api_secret 推导）"
            )
        timeout = float(config.get("timeout", 15.0))
        self.http_client = ArcusPerpHTTP(
            base_url=config.get("base_url"),
            network=self.network,
            auth=self.auth,
            timeout=timeout,
        )
        self.ws_url = config.get("ws_url")
        self.market_stream: Optional[ArcusPerpStream] = None
        self._connected = False
        self.address = self.auth.address or address.lower()
        self.account_index = account_index

    def connect(self) -> bool:
        try:
            self.http_client.health()
            self.http_client.refresh_markets()
            # 账户可能尚未入金（404），不阻断连接
            try:
                self.http_client.get_account(address=self.address)
            except Exception as e:
                msg = str(e).lower()
                if "no activity" not in msg and "404" not in msg:
                    raise
            self._connected = True
            return True
        except Exception as e:
            raise Exception(f"Arcus 连接失败: {e}") from e

    async def connect_market_stream(self) -> ArcusPerpStream:
        if not self.market_stream:
            self.market_stream = ArcusPerpStream(
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
        sub_id = kwargs.pop("id", None)
        if symbol and not sub_id:
            sub_id = normalize_arcus_symbol(symbol)
        # 部分频道在 id/payload 中带市场名
        extra = dict(kwargs)
        if symbol and "market" not in extra:
            extra["market"] = normalize_arcus_symbol(symbol)
        await stream.subscribe(ch, id=sub_id, callback=callback, **extra)

    def get_balance(self) -> Balance:
        try:
            raw = self.http_client.get_account(address=self.address)
            if not isinstance(raw, dict):
                raise ValueError(f"unexpected account payload: {raw!r}")
            equity = _to_decimal(
                raw.get("equity") or raw.get("totalEquity") or raw.get("marginBalance")
            )
            available = _to_decimal(
                raw.get("freeCollateral")
                or raw.get("availableBalance")
                or raw.get("availableMargin")
            )
            used = _to_decimal(
                raw.get("marginUsed") or raw.get("usedMargin") or raw.get("initialMargin")
            )
            upnl = _to_decimal(
                raw.get("unrealizedPnl") or raw.get("unrealizedPnL") or raw.get("upnl")
            )
            return Balance(
                total_balance=equity,
                available_balance=available,
                equity=equity,
                unrealized_pnl=upnl,
                margin_used=used if used else None,
                margin_available=available if available else None,
            )
        except Exception as e:
            raise Exception(f"查询余额失败: {e}") from e

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        try:
            want = normalize_arcus_symbol(symbol) if symbol else None
            raw = self.http_client.get_positions(address=self.address)
            items = _as_list(raw, "positions", "data", "result")
            positions: List[Position] = []
            for pos in items:
                if not isinstance(pos, dict):
                    continue
                market = str(
                    pos.get("marketDisplayName")
                    or pos.get("market")
                    or pos.get("symbol")
                    or ""
                )
                if want and normalize_arcus_symbol(market) != want:
                    continue

                # size: signed 或 size+side
                size_raw = pos.get("size")
                if size_raw is None:
                    size_raw = pos.get("quantity") or pos.get("netSize") or 0
                size = _to_decimal(size_raw)
                side = str(pos.get("side") or pos.get("positionSide") or "")
                if size < 0:
                    side = "short"
                    size = abs(size)
                elif size > 0 and not side:
                    side = "long"
                if size == 0 or (side or "").lower() in ("", "flat", "none", "neutral"):
                    continue

                leverage_raw = pos.get("leverage")
                leverage = (
                    int(float(leverage_raw))
                    if leverage_raw not in (None, "")
                    else None
                )
                positions.append(
                    Position(
                        symbol=normalize_arcus_symbol(market) if market else market,
                        size=abs(size),
                        side=_map_position_side(side),
                        entry_price=_to_decimal(
                            pos.get("entryPrice")
                            or pos.get("averageEntryPrice")
                            or pos.get("avgEntryPrice")
                        ),
                        mark_price=_to_decimal(pos.get("markPrice")),
                        unrealized_pnl=_to_decimal(
                            pos.get("unrealizedPnl") or pos.get("unrealizedPnL")
                        ),
                        leverage=leverage,
                        margin_mode=pos.get("marginMode"),
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
        time_in_force: str = "alo",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Order:
        market = normalize_arcus_symbol(symbol)
        side_str = _map_side(side)
        typ = (order_type or "limit").lower()
        if typ == "limit" and price is None:
            raise ValueError("限价单必须指定价格")

        meta = self.http_client.market_meta(market=market)
        tick = meta["tickSize"]
        step = meta["stepSize"]
        qty = snap_qty(quantity, step)
        if _to_decimal(qty) <= 0:
            raise ValueError(f"数量 {quantity} 低于 stepSize {step}")
        px = snap_price(price, tick) if price is not None else None
        if typ == "market" and px is None:
            # MARKET 仍需保护价：用 mark * 1.05 / 0.95
            mark = _to_decimal(meta["raw"].get("markPrice") or meta["raw"].get("oraclePrice"))
            if mark <= 0:
                raise ValueError("市价单缺少保护价且无法读取 markPrice")
            px = snap_price(
                mark * (Decimal("1.05") if side_str == "buy" else Decimal("0.95")),
                tick,
            )

        tif = _map_tif(time_in_force)
        if typ == "market":
            tif = "IOC"

        cloid = client_order_id or kwargs.get("clientOrderId") or kwargs.get("clientId")
        if not cloid and kwargs.get("auto_client_id", True):
            cloid = make_client_id("dd")

        try:
            result = self.http_client.place_order(
                market=market,
                market_id=int(meta["marketId"]),
                side=side_str.upper(),
                quantity=qty,
                price=px,
                order_type=typ.upper(),
                time_in_force=tif,
                reduce_only=reduce_only,
                client_id=cloid,
                address=self.address,
                account_index=self.account_index,
                tick_size=tick,
                step_size=step,
            )
            if isinstance(result, dict):
                # 202 body 可能直接是 OrderResponse，或包在 result 里
                payload = result.get("result") if isinstance(result.get("result"), dict) else result
                if isinstance(payload, dict) and (
                    payload.get("orderId") or payload.get("clientId")
                ):
                    order = self._parse_order(payload, default_symbol=market)
                    if not order.client_order_id and cloid:
                        order.client_order_id = cloid
                    if order.status == "pending" and not order.order_id:
                        order.status = "pending"
                    return order
            return Order(
                order_id=str(
                    (result or {}).get("orderId", "")
                    if isinstance(result, dict)
                    else result or ""
                ),
                symbol=market,
                side=side_str,
                order_type=typ,
                quantity=_to_decimal(qty),
                price=_to_decimal(px) if px is not None else None,
                status="pending",
                time_in_force=tif.lower(),
                reduce_only=reduce_only,
                client_order_id=cloid,
            )
        except Exception as e:
            raise Exception(f"下单失败: {e}") from e

    def _lookup_market_id_for_order(
        self,
        *,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        if symbol:
            return int(self.http_client.market_meta(market=normalize_arcus_symbol(symbol))["marketId"])
        opens = self.get_open_orders()
        want_oid = str(order_id).strip() if order_id else None
        want_cid = str(client_order_id).strip().lower() if client_order_id else None
        for o in opens:
            if want_oid and str(o.order_id) == want_oid:
                return int(
                    self.http_client.market_meta(market=normalize_arcus_symbol(o.symbol))[
                        "marketId"
                    ]
                )
            if want_cid and (o.client_order_id or "").lower() == want_cid:
                return int(
                    self.http_client.market_meta(market=normalize_arcus_symbol(o.symbol))[
                        "marketId"
                    ]
                )
        raise ValueError("无法解析 marketId：请传入 symbol，或确保订单仍在 openOrders 中")

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            market_id = self._lookup_market_id_for_order(
                order_id=order_id,
                client_order_id=client_order_id,
                symbol=symbol,
            )
            self.http_client.cancel_order(
                market_id=market_id,
                order_id=str(order_id) if order_id else None,
                client_id=str(client_order_id) if client_order_id else None,
                address=self.address,
                account_index=self.account_index,
            )
            return True
        except Exception as e:
            raise Exception(f"撤单失败: {e}") from e

    def cancel_orders_by_ids(
        self,
        order_id_list: Optional[Sequence[Union[int, str]]] = None,
        cl_ord_id_list: Optional[Sequence[str]] = None,
    ) -> bool:
        """批量撤单（兼容 grid_mm）：先查 openOrders 补齐 marketId，再 batchCancel。"""
        ids = [str(x) for x in (order_id_list or [])]
        cloids = [str(x) for x in (cl_ord_id_list or [])]
        if not ids and not cloids:
            raise ValueError("必须提供 order_id_list 或 cl_ord_id_list")

        opens = self.get_open_orders()
        by_oid = {str(o.order_id): o for o in opens if o.order_id}
        by_cid = {
            (o.client_order_id or "").lower(): o
            for o in opens
            if o.client_order_id
        }

        cancels: List[Dict[str, Any]] = []
        missing: List[str] = []

        for oid in ids:
            o = by_oid.get(str(oid))
            if not o:
                missing.append(f"order_id={oid}")
                continue
            mid = int(
                self.http_client.market_meta(market=normalize_arcus_symbol(o.symbol))[
                    "marketId"
                ]
            )
            cancels.append({"marketId": mid, "orderId": str(oid)})

        for cid in cloids:
            o = by_cid.get(str(cid).lower())
            if not o:
                missing.append(f"client_id={cid}")
                continue
            mid = int(
                self.http_client.market_meta(market=normalize_arcus_symbol(o.symbol))[
                    "marketId"
                ]
            )
            cancels.append({"marketId": mid, "clientId": str(cid)})

        if not cancels:
            if missing:
                raise Exception("批量撤单失败: 未找到订单 " + ", ".join(missing[:5]))
            return True

        try:
            # 分批 ≤100
            for i in range(0, len(cancels), 100):
                self.http_client.batch_cancel_orders(
                    cancels[i : i + 100],
                    address=self.address,
                )
            return True
        except Exception as e:
            raise Exception(f"批量撤单失败: {e}") from e

    def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        try:
            market_id = None
            if symbol:
                market_id = int(
                    self.http_client.market_meta(market=normalize_arcus_symbol(symbol))[
                        "marketId"
                    ]
                )
            self.http_client.cancel_all_orders(
                address=self.address,
                account_index=self.account_index,
                market_id=market_id,
            )
            return True
        except Exception as e:
            raise Exception(f"全部撤单失败: {e}") from e

    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        try:
            if order_id:
                raw = self.http_client.get_order_status(
                    order_id=str(order_id), address=self.address
                )
                if isinstance(raw, dict):
                    return self._parse_order(raw)
            # fallback：扫 open + history
            for o in self.get_open_orders(symbol=symbol):
                if order_id and str(o.order_id) == str(order_id):
                    return o
                if client_order_id and (o.client_order_id or "").lower() == str(
                    client_order_id
                ).lower():
                    return o
            return None
        except Exception as e:
            raise Exception(f"查询订单失败: {e}") from e

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        try:
            want = normalize_arcus_symbol(symbol) if symbol else None
            raw = self.http_client.get_open_orders(address=self.address)
            orders: List[Order] = []
            for item in _as_list(raw, "orders", "data", "result"):
                if not isinstance(item, dict):
                    continue
                order = self._parse_order(item)
                if want and normalize_arcus_symbol(order.symbol) != want:
                    continue
                if order.status not in ("open", "pending", "partially_filled"):
                    continue
                orders.append(order)
            return orders
        except Exception as e:
            raise Exception(f"查询未成交订单失败: {e}") from e

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """优先只打 BBO（weight 2）；避免每轮再打 mids/markets 加重 IP 限流。"""
        market = normalize_arcus_symbol(symbol)
        try:
            bid = ask = last = mark = index = funding = None
            try:
                bbo = self.http_client.get_bbo(market=market)
                if isinstance(bbo, dict):
                    bb = bbo.get("bestBid") or {}
                    ba = bbo.get("bestAsk") or {}
                    if isinstance(bb, dict) and bb.get("price") not in (None, ""):
                        bid = float(bb["price"])
                    if isinstance(ba, dict) and ba.get("price") not in (None, ""):
                        ask = float(ba["price"])
            except Exception:
                pass

            # 仅用本地 markets 缓存补 mark（连接时已 refresh，不再每轮 GET /markets）
            try:
                meta = self.http_client.market_meta(market=market)["raw"]
                if meta.get("markPrice") not in (None, ""):
                    mark = float(meta["markPrice"])
                if meta.get("oraclePrice") not in (None, ""):
                    index = float(meta["oraclePrice"])
                if meta.get("lastTradePrice") not in (None, ""):
                    last = float(meta["lastTradePrice"])
                if meta.get("fundingRate") not in (None, ""):
                    funding = float(meta["fundingRate"])
            except Exception:
                pass

            mid = None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2.0
                last = last if last is not None else mid
            elif last is not None:
                mid = last

            return {
                "symbol": market,
                "bid_price": bid,
                "ask_price": ask,
                "last_price": last if last is not None else mark,
                "mid_price": mid if mid is not None else mark,
                "mark_price": mark if mark is not None else last,
                "index_price": index,
                "funding_rate": funding,
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取价格失败: {e}") from e

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        market = normalize_arcus_symbol(symbol)
        try:
            raw = self.http_client.get_l2_orderbook(market=market, levels=depth)
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
        )

    def _parse_order(
        self, data: Dict[str, Any], *, default_symbol: str = ""
    ) -> Order:
        side_raw = data.get("orderSide") or data.get("side") or ""
        side = _map_side(str(side_raw))
        tif = data.get("timeInForce") or data.get("time_in_force") or "gtt"
        if isinstance(tif, str):
            tif = tif.lower()
        status = _map_order_status(str(data.get("status") or "ACK"))
        filled = _to_decimal(
            data.get("filledQuantity")
            or data.get("filledSize")
            or data.get("filledQty")
            or 0
        )
        qty = _to_decimal(
            data.get("quantity") or data.get("size") or data.get("qty") or 0
        )
        if status == "open" and filled > 0 and qty > 0 and filled < qty:
            status = "partially_filled"

        market = str(
            data.get("marketDisplayName")
            or data.get("market")
            or data.get("symbol")
            or default_symbol
            or ""
        )
        if data.get("marketId") and not market:
            try:
                market = self.http_client.market_meta(market_id=int(data["marketId"]))[
                    "raw"
                ].get("marketDisplayName", "")
            except Exception:
                market = str(data.get("marketId"))

        created = data.get("createdAt") or data.get("timestamp")
        if isinstance(created, str) and created.isdigit():
            created = int(created)
        if isinstance(created, int) and created > 10_000_000_000_000:
            # µs → ms
            created = created // 1000
        if isinstance(created, int) and created > 10_000_000_000:
            # ns? already handled µs; if still huge assume ns
            if created > 10_000_000_000_000_000:
                created = created // 1_000_000

        return Order(
            order_id=str(data.get("orderId") or data.get("id") or ""),
            symbol=normalize_arcus_symbol(market) if market else market,
            side=side,
            order_type=str(
                data.get("orderType") or data.get("type") or "limit"
            ).lower(),
            quantity=qty,
            price=_to_decimal(data.get("price"))
            if data.get("price") not in (None, "")
            else None,
            filled_quantity=filled,
            status=status,
            time_in_force=tif,
            reduce_only=bool(data.get("reduceOnly", False)),
            client_order_id=data.get("clientId")
            or data.get("clientOrderId")
            or data.get("clientOid"),
            created_at=int(created) if isinstance(created, int) else None,
            updated_at=None,
        )
