"""
Lighter Exchange Adapter Implementation

This module implements BasePerpAdapter for Lighter exchange.
"""
import sys
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal, ROUND_DOWN

# 添加项目路径
project_root = os.path.join(os.path.dirname(__file__), "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

lighter_sdk_path = os.path.join(project_root, "exchange", "exchange_lighter")
if lighter_sdk_path not in sys.path:
    sys.path.insert(0, lighter_sdk_path)

from adapters.base_adapter import BasePerpAdapter, Balance, Position, Order

import lighter
from lighter.ws_client import WsClient


class LighterAdapter(BasePerpAdapter):
    """Lighter 交易所适配器实现"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Lighter 适配器

        Args:
            config: 配置字典，必须包含：
                - exchange_name: "lighter"
                - account_index: 账户索引（账户级，非 API key）
                - base_url: API 基础 URL（可选，默认 https://mainnet.zklighter.elliot.ai）
                - api_key_index: 使用的 API key index（API key 级，非账户）
                - api_public_key: API 公钥（可选，当前仅记录）
                - api_private_key: API 私钥（可选，下单需要）
                - api_private_keys: API 私钥字典（可选，下单需要） e.g. {0: "0x..."}
                - market_type: "perp" 或 "spot"（可选，默认 "perp"）
                - auth_expiry_sec: auth token 过期时间（秒，可选，默认 600）
        """
        super().__init__(config)

        self.base_url = config.get("base_url", "https://mainnet.zklighter.elliot.ai")
        self.account_index = config.get("account_index")
        if self.account_index is None:
            raise ValueError("配置中必须包含 account_index")
        self.account_index = int(self.account_index)

        self.market_type = str(config.get("market_type", "perp")).lower()
        self.auth_expiry_sec = int(config.get("auth_expiry_sec", 600))
        self.market_slippage_pct = float(config.get("market_slippage_pct", 0.005))

        self.api_public_key = config.get("api_public_key")
        api_private_keys = self._normalize_api_private_keys(
            config.get("api_private_keys"),
            config.get("api_key_index"),
            config.get("api_private_key"),
        )

        self.api_client = lighter.ApiClient(configuration=lighter.Configuration(host=self.base_url))
        self.account_api = lighter.AccountApi(self.api_client)
        self.order_api = lighter.OrderApi(self.api_client)

        self.signer_client: Optional[lighter.SignerClient] = None
        if api_private_keys:
            self.signer_client = lighter.SignerClient(
                url=self.base_url,
                account_index=int(self.account_index),
                api_private_keys=api_private_keys,
            )

        self.api_key_index = self._resolve_api_key_index(api_private_keys, config.get("api_key_index"))
        self._auth_token: Optional[str] = None
        self._auth_token_expiry: Optional[int] = None

        self._market_cache: Dict[str, Dict[str, Any]] = {}
        self._market_by_id: Dict[int, Dict[str, Any]] = {}
        self.ws_host = self.base_url.replace("https://", "").replace("http://", "")
        self.ws_client: Optional[WsClient] = None

    def init_ws_client(
        self,
        order_book_ids: Optional[List[int]] = None,
        account_ids: Optional[List[int]] = None,
        account_orders_ids: Optional[List[int]] = None,
        user_stats_ids: Optional[List[int]] = None,
        order_book_symbols: Optional[List[str]] = None,
        on_order_book_update=None,
        on_account_update=None,
        on_account_orders_update=None,
        on_user_stats_update=None,
        auth_token: Optional[str] = None,
    ) -> WsClient:
        order_book_ids = order_book_ids or []
        account_ids = account_ids or []
        account_orders_ids = account_orders_ids or []
        user_stats_ids = user_stats_ids or []
        if order_book_symbols:
            market_map = {}
            for market in self._market_cache.values():
                market_map[self._normalize_symbol(market["symbol"])] = market["market_id"]
            for sym in order_book_symbols:
                key = self._normalize_symbol(sym)
                if key not in market_map:
                    raise ValueError(f"未找到交易对: {sym}（请先通过 connect_ws 预热市场或传 order_book_ids）")
                order_book_ids.append(int(market_map[key]))
        self.ws_client = WsClient(
            host=self.ws_host,
            order_book_ids=order_book_ids,
            account_ids=account_ids,
            account_orders_ids=account_orders_ids,
            user_stats_ids=user_stats_ids,
            on_order_book_update=on_order_book_update,
            on_account_update=on_account_update,
            on_account_orders_update=on_account_orders_update,
            on_user_stats_update=on_user_stats_update,
            auth_token=auth_token,
        )
        return self.ws_client

    def _normalize_api_private_keys(
        self,
        api_private_keys: Optional[Dict[Any, str]],
        api_key_index: Optional[int],
        api_private_key: Optional[str],
    ) -> Dict[int, str]:
        if api_private_keys:
            normalized: Dict[int, str] = {}
            for key, value in api_private_keys.items():
                normalized[int(key)] = value
            return normalized

        if api_private_key:
            index = int(api_key_index) if api_key_index is not None else 0
            return {index: api_private_key}

        return {}

    def _resolve_api_key_index(self, api_private_keys: Dict[int, str], api_key_index: Optional[int]) -> Optional[int]:
        if api_key_index is not None:
            return int(api_key_index)
        if len(api_private_keys) == 1:
            return list(api_private_keys.keys())[0]
        return None

    def _run_async(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

    def _resolve_auth_api_key_index(self) -> int:
        if self.api_key_index is not None:
            return int(self.api_key_index)
        if self.signer_client and len(self.signer_client.api_key_dict) == 1:
            return list(self.signer_client.api_key_dict.keys())[0]
        raise ValueError("未指定 api_key_index，且存在多个 API key，无法生成 auth token")

    def _get_auth_token(self) -> str:
        if not self.signer_client:
            raise Exception("未配置 API 私钥，无法生成 auth token")

        now = int(time.time())
        if self._auth_token and self._auth_token_expiry and now < self._auth_token_expiry - 5:
            return self._auth_token

        auth_api_key_index = self._resolve_auth_api_key_index()
        auth, error = self.signer_client.create_auth_token_with_expiry(
            deadline=self.auth_expiry_sec,
            api_key_index=auth_api_key_index,
        )
        if error:
            raise Exception(f"生成 auth token 失败: {error}")

        self._auth_token = auth
        self._auth_token_expiry = now + self.auth_expiry_sec
        return auth

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.replace("-", "").replace("_", "").upper()

    def _refresh_markets(self):
        details = self._run_async(self.order_api.order_books(filter=self.market_type))
        if not details or not details.order_books:
            return

        for market in details.order_books:
            norm_symbol = self._normalize_symbol(market.symbol)
            meta = {
                "symbol": market.symbol,
                "market_id": market.market_id,
                "supported_price_decimals": market.supported_price_decimals,
                "supported_size_decimals": market.supported_size_decimals,
            }
            self._market_cache[norm_symbol] = meta
            self._market_by_id[market.market_id] = meta

    async def _refresh_markets_async(self):
        details = await self.order_api.order_books(filter=self.market_type)
        if not details or not details.order_books:
            return

        for market in details.order_books:
            norm_symbol = self._normalize_symbol(market.symbol)
            meta = {
                "symbol": market.symbol,
                "market_id": market.market_id,
                "supported_price_decimals": market.supported_price_decimals,
                "supported_size_decimals": market.supported_size_decimals,
            }
            self._market_cache[norm_symbol] = meta
            self._market_by_id[market.market_id] = meta

    def _load_market_details(self, market_id: int):
        details = self._run_async(self.order_api.order_book_details(market_id=market_id, filter=self.market_type))
        if not details:
            return

        perps = details.order_book_details or []
        for item in perps:
            if item.market_id != market_id:
                continue
            meta = self._market_by_id.get(market_id, {})
            meta.update(
                {
                    "symbol": item.symbol,
                    "market_id": item.market_id,
                    "price_decimals": item.price_decimals,
                    "size_decimals": item.size_decimals,
                    "last_trade_price": item.last_trade_price,
                }
            )
            self._market_by_id[market_id] = meta
            self._market_cache[self._normalize_symbol(item.symbol)] = meta
            break

    async def _load_market_details_async(self, market_id: int):
        details = await self.order_api.order_book_details(market_id=market_id, filter=self.market_type)
        if not details:
            return

        perps = details.order_book_details or []
        for item in perps:
            if item.market_id != market_id:
                continue
            meta = self._market_by_id.get(market_id, {})
            meta.update(
                {
                    "symbol": item.symbol,
                    "market_id": item.market_id,
                    "price_decimals": item.price_decimals,
                    "size_decimals": item.size_decimals,
                    "last_trade_price": item.last_trade_price,
                }
            )
            self._market_by_id[market_id] = meta
            self._market_cache[self._normalize_symbol(item.symbol)] = meta
            break

    def _get_market_meta(self, symbol: str) -> Dict[str, Any]:
        norm_symbol = self._normalize_symbol(symbol)
        if norm_symbol not in self._market_cache:
            self._refresh_markets()

        if norm_symbol not in self._market_cache:
            raise ValueError(f"未找到交易对: {symbol}")

        meta = self._market_cache[norm_symbol]
        if "price_decimals" not in meta or "size_decimals" not in meta:
            try:
                self._load_market_details(meta["market_id"])
            except Exception:
                # order_book_details may return invalid payloads; keep fallback decimals
                pass
        return self._market_cache[norm_symbol]

    async def _get_market_meta_async(self, symbol: str) -> Dict[str, Any]:
        norm_symbol = self._normalize_symbol(symbol)
        if norm_symbol not in self._market_cache:
            await self._refresh_markets_async()

        if norm_symbol not in self._market_cache:
            raise ValueError(f"未找到交易对: {symbol}")

        meta = self._market_cache[norm_symbol]
        if "price_decimals" not in meta or "size_decimals" not in meta:
            try:
                await self._load_market_details_async(meta["market_id"])
            except Exception:
                # order_book_details may return invalid payloads; keep fallback decimals
                pass
        return self._market_cache[norm_symbol]

    def get_market_id(self, symbol: str) -> int:
        """获取交易对对应的 market_id（供 WSS 使用）"""
        return int(self._get_market_meta(symbol)["market_id"])

    def _parse_decimal(self, value: Optional[str]) -> Decimal:
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    def _apply_market_slippage(self, price: Decimal, is_ask: int) -> Decimal:
        slippage = Decimal(str(max(self.market_slippage_pct, 0.0)))
        if slippage == 0:
            return price
        factor = Decimal("1") - slippage if is_ask else Decimal("1") + slippage
        adjusted = price * factor
        return adjusted if adjusted > 0 else price

    def _to_scaled_int(self, value: Decimal, decimals: int) -> int:
        if decimals <= 0:
            return int(value.to_integral_value(rounding=ROUND_DOWN))
        scale = Decimal(10) ** decimals
        return int((value * scale).to_integral_value(rounding=ROUND_DOWN))

    def connect(self) -> bool:
        """连接到 Lighter 并完成认证"""
        if self.signer_client:
            err = self.signer_client.check_client()
            if err:
                raise Exception(f"Lighter 认证失败: {err}")
        return True

    async def connect_ws(
        self,
        order_book_ids: Optional[List[int]] = None,
        account_ids: Optional[List[int]] = None,
        account_orders_ids: Optional[List[int]] = None,
        user_stats_ids: Optional[List[int]] = None,
        order_book_symbols: Optional[List[str]] = None,
        on_order_book_update=None,
        on_account_update=None,
        on_account_orders_update=None,
        on_user_stats_update=None,
        auth_token: Optional[str] = None,
    ) -> WsClient:
        """
        创建并返回 WSS 客户端（不会自动 run）

        Args:
            order_book_ids: 订阅的 order book market_id 列表
            account_ids: 订阅的 account index 列表
            order_book_symbols: 订阅的交易对符号列表（会转换为 market_id）
            on_order_book_update: order book 回调 (market_id, order_book)
            on_account_update: account 回调 (account_id, payload)
        """
        order_book_ids = order_book_ids or []
        account_ids = account_ids or []
        account_orders_ids = account_orders_ids or []
        user_stats_ids = user_stats_ids or []
        if order_book_symbols:
            temp_client = lighter.ApiClient(configuration=lighter.Configuration(host=self.base_url))
            temp_order_api = lighter.OrderApi(temp_client)
            try:
                details = await temp_order_api.order_books(filter=self.market_type)
                market_map = {}
                for market in details.order_books or []:
                    norm_symbol = self._normalize_symbol(market.symbol)
                    market_map[norm_symbol] = market.market_id
                    meta = {
                        "symbol": market.symbol,
                        "market_id": market.market_id,
                        "supported_price_decimals": market.supported_price_decimals,
                        "supported_size_decimals": market.supported_size_decimals,
                    }
                    self._market_cache[norm_symbol] = meta
                    self._market_by_id[market.market_id] = meta
                for sym in order_book_symbols:
                    key = self._normalize_symbol(sym)
                    if key not in market_map:
                        raise ValueError(f"未找到交易对: {sym}")
                    order_book_ids.append(int(market_map[key]))
            finally:
                await temp_client.close()

        if account_orders_ids and not auth_token:
            if not self.signer_client:
                raise Exception("未配置 API 私钥，无法生成 auth token")
            auth_token = self._get_auth_token()

        return self.init_ws_client(
            order_book_ids=order_book_ids,
            account_ids=account_ids,
            account_orders_ids=account_orders_ids,
            user_stats_ids=user_stats_ids,
            on_order_book_update=on_order_book_update,
            on_account_update=on_account_update,
            on_account_orders_update=on_account_orders_update,
            on_user_stats_update=on_user_stats_update,
            auth_token=auth_token,
        )

    async def run_ws(self, ws_client: WsClient):
        """运行 WSS 客户端（阻塞直到连接关闭）"""
        await ws_client.run_async()



    def get_balance(self) -> Balance:
        """查询账户余额"""
        response = self._run_async(self.account_api.account(by="index", value=str(self.account_index)))
        if not response.accounts:
            raise Exception("未找到账户信息")

        account = response.accounts[0]
        total_asset_value = self._parse_decimal(account.total_asset_value)
        available_balance = self._parse_decimal(account.available_balance)

        unrealized_pnl = Decimal("0")
        for pos in account.positions or []:
            unrealized_pnl += self._parse_decimal(pos.unrealized_pnl)

        return Balance(
            total_balance=total_asset_value,
            available_balance=available_balance,
            equity=total_asset_value,
            unrealized_pnl=unrealized_pnl,
            margin_used=None,
            margin_available=None,
        )

    async def get_balance_async(self) -> Balance:
        """查询账户余额（异步版本，避免跨 event loop 调用）"""
        response = await self.account_api.account(by="index", value=str(self.account_index))
        if not response.accounts:
            raise Exception("未找到账户信息")

        account = response.accounts[0]
        total_asset_value = self._parse_decimal(account.total_asset_value)
        available_balance = self._parse_decimal(account.available_balance)

        unrealized_pnl = Decimal("0")
        for pos in account.positions or []:
            unrealized_pnl += self._parse_decimal(pos.unrealized_pnl)

        return Balance(
            total_balance=total_asset_value,
            available_balance=available_balance,
            equity=total_asset_value,
            unrealized_pnl=unrealized_pnl,
            margin_used=None,
            margin_available=None,
        )

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """查询持仓信息"""
        response = self._run_async(self.account_api.account(by="index", value=str(self.account_index)))
        if not response.accounts:
            return []

        account = response.accounts[0]
        positions: List[Position] = []
        for pos in account.positions or []:
            if symbol and self._normalize_symbol(pos.symbol) != self._normalize_symbol(symbol):
                continue

            size = self._parse_decimal(pos.position)
            if size == Decimal("0"):
                continue

            side = "long" if int(pos.sign) > 0 else "short"
            meta = self._get_market_meta(pos.symbol)
            mark_price = Decimal(str(meta.get("last_trade_price", 0)))

            margin_mode = "cross" if int(pos.margin_mode) == 0 else "isolated"

            positions.append(
                Position(
                    symbol=pos.symbol,
                    size=abs(size),
                    side=side,
                    entry_price=self._parse_decimal(pos.avg_entry_price),
                    mark_price=mark_price,
                    unrealized_pnl=self._parse_decimal(pos.unrealized_pnl),
                    leverage=None,
                    margin_mode=margin_mode,
                )
            )

        return positions

    async def get_positions_async(self, symbol: Optional[str] = None) -> List[Position]:
        """查询持仓信息（异步版本，避免跨 event loop 调用）"""
        response = await self.account_api.account(by="index", value=str(self.account_index))
        if not response.accounts:
            return []

        account = response.accounts[0]
        positions: List[Position] = []
        for pos in account.positions or []:
            if symbol and self._normalize_symbol(pos.symbol) != self._normalize_symbol(symbol):
                continue

            size = self._parse_decimal(pos.position)
            if size == Decimal("0"):
                continue

            side = "long" if int(pos.sign) > 0 else "short"
            meta = await self._get_market_meta_async(pos.symbol)
            mark_price = Decimal(str(meta.get("last_trade_price", 0)))

            margin_mode = "cross" if int(pos.margin_mode) == 0 else "isolated"

            positions.append(
                Position(
                    symbol=pos.symbol,
                    size=abs(size),
                    side=side,
                    entry_price=self._parse_decimal(pos.avg_entry_price),
                    mark_price=mark_price,
                    unrealized_pnl=self._parse_decimal(pos.unrealized_pnl),
                    leverage=None,
                    margin_mode=margin_mode,
                )
            )

        return positions

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
        **kwargs,
    ) -> Order:
        """下单"""
        if not self.signer_client:
            raise Exception("未配置 API 私钥，无法下单")

        meta = self._get_market_meta(symbol)
        market_id = meta["market_id"]
        size_decimals = meta.get("size_decimals", meta.get("supported_size_decimals", 0))
        price_decimals = meta.get("price_decimals", meta.get("supported_price_decimals", 0))

        is_ask = 1 if side.lower() in ["sell", "short"] else 0
        base_amount = self._to_scaled_int(quantity, int(size_decimals))

        tif_map = {
            "gtc": self.signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            "ioc": self.signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            "fok": self.signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        }
        tif = tif_map.get(time_in_force.lower(), self.signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)

        try:
            client_order_index = int(client_order_id) if client_order_id and str(client_order_id).isdigit() else 0
        except (ValueError, TypeError):
            client_order_index = 0

        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("限价单必须指定价格")
            price_scaled = self._to_scaled_int(price, int(price_decimals))
            created_order, response, error = self._run_async(
                self.signer_client.create_order(
                    market_index=market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    price=price_scaled,
                    is_ask=is_ask,
                    order_type=self.signer_client.ORDER_TYPE_LIMIT,
                    time_in_force=tif,
                    reduce_only=reduce_only,
                    api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
                )
            )
        elif order_type.lower() == "market":
            if price is None:
                order_book = self._run_async(self.order_api.order_book_orders(market_id, 1))
                if is_ask:
                    best_price = order_book.bids[0].price
                else:
                    best_price = order_book.asks[0].price
                price = Decimal(str(best_price))
            price = self._apply_market_slippage(price, is_ask)
            price_scaled = self._to_scaled_int(price, int(price_decimals))
            created_order, response, error = self._run_async(
                self.signer_client.create_market_order(
                    market_index=market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    avg_execution_price=price_scaled,
                    is_ask=is_ask,
                    reduce_only=reduce_only,
                    api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
                )
            )
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")

        if error:
            raise Exception(f"下单失败: {error}")
        if not response or getattr(response, "code", None) != 200:
            raise Exception(f"下单失败: {getattr(response, 'message', '未知错误')}")

        order_id = getattr(response, "tx_hash", "")
        return Order(
            order_id=str(order_id),
            symbol=symbol,
            side="sell" if is_ask else "buy",
            order_type=order_type.lower(),
            quantity=quantity,
            price=price,
            status="pending",
            time_in_force=time_in_force.lower(),
            reduce_only=reduce_only,
            client_order_id=client_order_id,
        )

    async def place_order_async(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "gtc",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs,
    ) -> Order:
        """下单（异步版本，避免跨 event loop 调用）"""
        if not self.signer_client:
            raise Exception("未配置 API 私钥，无法下单")

        meta = await self._get_market_meta_async(symbol)
        market_id = meta["market_id"]
        size_decimals = meta.get("size_decimals", meta.get("supported_size_decimals", 0))
        price_decimals = meta.get("price_decimals", meta.get("supported_price_decimals", 0))

        is_ask = 1 if side.lower() in ["sell", "short"] else 0
        base_amount = self._to_scaled_int(quantity, int(size_decimals))

        tif_map = {
            "gtc": self.signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            "ioc": self.signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            "fok": self.signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        }
        tif = tif_map.get(time_in_force.lower(), self.signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)

        try:
            client_order_index = int(client_order_id) if client_order_id and str(client_order_id).isdigit() else 0
        except (ValueError, TypeError):
            client_order_index = 0

        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("限价单必须指定价格")
            price_scaled = self._to_scaled_int(price, int(price_decimals))
            created_order, response, error = await self.signer_client.create_order(
                market_index=market_id,
                client_order_index=client_order_index,
                base_amount=base_amount,
                price=price_scaled,
                is_ask=is_ask,
                order_type=self.signer_client.ORDER_TYPE_LIMIT,
                time_in_force=tif,
                reduce_only=reduce_only,
                api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
            )
        elif order_type.lower() == "market":
            if price is None:
                order_book = await self.order_api.order_book_orders(market_id, 1)
                if is_ask:
                    best_price = order_book.bids[0].price
                else:
                    best_price = order_book.asks[0].price
                price = Decimal(str(best_price))
            price = self._apply_market_slippage(price, is_ask)
            price_scaled = self._to_scaled_int(price, int(price_decimals))
            created_order, response, error = await self.signer_client.create_market_order(
                market_index=market_id,
                client_order_index=client_order_index,
                base_amount=base_amount,
                avg_execution_price=price_scaled,
                is_ask=is_ask,
                reduce_only=reduce_only,
                api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
            )
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")

        if error:
            raise Exception(f"下单失败: {error}")
        if not response or getattr(response, "code", None) != 200:
            raise Exception(f"下单失败: {getattr(response, 'message', '未知错误')}")

        order_id = getattr(response, "tx_hash", "")
        return Order(
            order_id=str(order_id),
            symbol=symbol,
            side="sell" if is_ask else "buy",
            order_type=order_type.lower(),
            quantity=quantity,
            price=price,
            status="pending",
            time_in_force=time_in_force.lower(),
            reduce_only=reduce_only,
            client_order_id=client_order_id,
        )

    def _find_order_record(
        self,
        order_id: Optional[str],
        client_order_id: Optional[str],
        symbol: Optional[str],
    ) -> Optional[Tuple[int, lighter.models.order.Order]]:
        auth = self._get_auth_token()
        market_ids: List[int] = []

        if symbol:
            meta = self._get_market_meta(symbol)
            market_ids = [meta["market_id"]]
        else:
            if not self._market_by_id:
                self._refresh_markets()
            market_ids = list(self._market_by_id.keys())

        for market_id in market_ids:
            orders = self._run_async(
                self.order_api.account_active_orders(
                    account_index=int(self.account_index),
                    market_id=market_id,
                    auth=auth,
                )
            )
            for order in orders.orders or []:
                if order_id and str(order.order_id) == str(order_id):
                    return market_id, order
                if client_order_id and str(order.client_order_id) == str(client_order_id):
                    return market_id, order

        return None

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        """撤单"""
        if not self.signer_client:
            raise Exception("未配置 API 私钥，无法撤单")
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")

        result = self._find_order_record(order_id, client_order_id, symbol)
        if not result:
            return False

        market_id, order = result
        _, response, error = self._run_async(
            self.signer_client.cancel_order(
                market_index=market_id,
                order_index=order.order_index,
                api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
            )
        )
        if error:
            raise Exception(f"撤单失败: {error}")
        if not response or getattr(response, "code", None) != 200:
            raise Exception(f"撤单失败: {getattr(response, 'message', '未知错误')}")
        return True

    def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
    ) -> bool:
        """撤销所有订单"""
        if not self.signer_client:
            raise Exception("未配置 API 私钥，无法撤单")

        if symbol:
            open_orders = self.get_open_orders(symbol=symbol)
            success = True
            for order in open_orders:
                if not self.cancel_order(order_id=order.order_id, symbol=symbol, client_order_id=order.client_order_id):
                    success = False
            return success

        _, response, error = self._run_async(
            self.signer_client.cancel_all_orders(
                time_in_force=self.signer_client.CANCEL_ALL_TIF_IMMEDIATE,
                timestamp_ms=int(time.time() * 1000),
                api_key_index=self.api_key_index if self.api_key_index is not None else self.signer_client.DEFAULT_API_KEY_INDEX,
            )
        )
        if error:
            raise Exception(f"批量撤单失败: {error}")
        if not response or getattr(response, "code", None) != 200:
            raise Exception(f"批量撤单失败: {getattr(response, 'message', '未知错误')}")
        return True

    def _lighter_order_to_order(self, lighter_order: lighter.models.order.Order) -> Order:
        status_map = {
            "open": "open",
            "pending": "pending",
            "in-progress": "pending",
            "filled": "filled",
        }
        status_raw = str(lighter_order.status)
        if status_raw.startswith("canceled"):
            status = "cancelled"
        else:
            status = status_map.get(status_raw, "pending")

        symbol = ""
        if lighter_order.market_index in self._market_by_id:
            symbol = self._market_by_id[lighter_order.market_index]["symbol"]

        return Order(
            order_id=str(lighter_order.order_id),
            symbol=symbol,
            side=str(lighter_order.side),
            order_type=str(lighter_order.type),
            quantity=self._parse_decimal(lighter_order.initial_base_amount),
            price=self._parse_decimal(lighter_order.price) if lighter_order.price else None,
            filled_quantity=self._parse_decimal(lighter_order.filled_base_amount),
            status=status,
            time_in_force=str(lighter_order.time_in_force),
            reduce_only=bool(lighter_order.reduce_only),
            client_order_id=str(lighter_order.client_order_id),
            created_at=int(lighter_order.created_at) if lighter_order.created_at else None,
            updated_at=int(lighter_order.updated_at) if lighter_order.updated_at else None,
        )

    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        """查询订单状态"""
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")

        auth = self._get_auth_token()
        market_ids: List[int] = []
        if symbol:
            meta = self._get_market_meta(symbol)
            market_ids = [meta["market_id"]]
        else:
            if not self._market_by_id:
                self._refresh_markets()
            market_ids = list(self._market_by_id.keys())

        for market_id in market_ids:
            active_orders = self._run_async(
                self.order_api.account_active_orders(
                    account_index=int(self.account_index),
                    market_id=market_id,
                    auth=auth,
                )
            )
            for order in active_orders.orders or []:
                if order_id and str(order.order_id) == str(order_id):
                    return self._lighter_order_to_order(order)
                if client_order_id and str(order.client_order_id) == str(client_order_id):
                    return self._lighter_order_to_order(order)

            inactive_orders = self._run_async(
                self.order_api.account_inactive_orders(
                    account_index=int(self.account_index),
                    limit=100,
                    market_id=market_id,
                    auth=auth,
                )
            )
            for order in inactive_orders.orders or []:
                if order_id and str(order.order_id) == str(order_id):
                    return self._lighter_order_to_order(order)
                if client_order_id and str(order.client_order_id) == str(client_order_id):
                    return self._lighter_order_to_order(order)

        return None

    def get_open_orders(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """查询所有未成交订单"""
        auth = self._get_auth_token()
        market_ids: List[int] = []

        if symbol:
            meta = self._get_market_meta(symbol)
            market_ids = [meta["market_id"]]
        else:
            if not self._market_by_id:
                self._refresh_markets()
            market_ids = list(self._market_by_id.keys())

        orders: List[Order] = []
        for market_id in market_ids:
            response = self._run_async(
                self.order_api.account_active_orders(
                    account_index=int(self.account_index),
                    market_id=market_id,
                    auth=auth,
                )
            )
            for order in response.orders or []:
                orders.append(self._lighter_order_to_order(order))

        return orders

    async def get_open_orders_async(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """查询所有未成交订单（异步版本，避免跨 event loop 调用）"""
        auth = self._get_auth_token()
        market_ids: List[int] = []

        if symbol:
            meta = await self._get_market_meta_async(symbol)
            market_ids = [meta["market_id"]]
        else:
            if not self._market_by_id:
                await self._refresh_markets_async()
            market_ids = list(self._market_by_id.keys())

        orders: List[Order] = []
        for market_id in market_ids:
            response = await self.order_api.account_active_orders(
                account_index=int(self.account_index),
                market_id=market_id,
                auth=auth,
            )
            for order in response.orders or []:
                orders.append(self._lighter_order_to_order(order))

        return orders

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取交易对的最新价格信息"""
        meta = self._get_market_meta(symbol)
        market_id = meta["market_id"]

        order_book = self._run_async(self.order_api.order_book_orders(market_id, 1))
        best_bid = float(order_book.bids[0].price) if order_book.bids else None
        best_ask = float(order_book.asks[0].price) if order_book.asks else None

        if "last_trade_price" not in meta:
            self._load_market_details(market_id)
            meta = self._market_by_id.get(market_id, meta)

        last_price = meta.get("last_trade_price")
        last_price_value = float(last_price) if last_price is not None else None

        return {
            "symbol": meta.get("symbol", symbol),
            "bid_price": best_bid,
            "ask_price": best_ask,
            "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else None,
            "last_price": last_price_value,
            "mark_price": last_price_value,
            "index_price": None,
            "timestamp": int(time.time() * 1000),
        }

    def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """获取订单簿"""
        meta = self._get_market_meta(symbol)
        market_id = meta["market_id"]
        limit = max(1, min(int(depth), 250))

        order_book = self._run_async(self.order_api.order_book_orders(market_id, limit))
        bids = [[float(o.price), float(o.remaining_base_amount)] for o in order_book.bids]
        asks = [[float(o.price), float(o.remaining_base_amount)] for o in order_book.asks]

        return {
            "symbol": meta.get("symbol", symbol),
            "bids": bids,
            "asks": asks,
            "timestamp": int(time.time() * 1000),
        }
