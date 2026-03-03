"""
Hyperliquid (Hype) Exchange Adapter Implementation

本模块基于 `exchange/exchange_hype` 提供的官方 SDK，
实现统一的 `BasePerpAdapter` 接口，方便在策略层无缝切换交易所。
"""

import os
import sys
from decimal import Decimal
from typing import Any, Dict, List, Optional

# 将本项目根目录加入路径，确保可以导入 hyperliquid 包
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

HYPE_ROOT = os.path.join(PROJECT_ROOT, "exchange", "exchange_hype")
if HYPE_ROOT not in sys.path:
    sys.path.insert(0, HYPE_ROOT)

from eth_account import Account  # type: ignore
from eth_account.signers.local import LocalAccount  # type: ignore

from adapters.base_adapter import BasePerpAdapter, Balance, Order, Position

from hyperliquid.exchange import Exchange  # type: ignore
from hyperliquid.info import Info  # type: ignore
from hyperliquid.utils.constants import MAINNET_API_URL  # type: ignore
from hyperliquid.utils.types import Cloid  # type: ignore


class HypeAdapter(BasePerpAdapter):
    """
    Hyperliquid / Hype 交易所适配器实现

    配置字段约定（与现有适配器风格保持一致）：
        - exchange_name: "hype"
        - api_key: API Wallet 私钥（推荐，0x 开头或裸 32 字节 hex）
        - account_address: 主交易账户地址（使用 api_key 时建议显式填写）
        - private_key / secret_key: 兼容旧字段（不推荐）
        - base_url: API 基础 URL（可选，默认 MAINNET_API_URL）
        - perp_dexs: perp dex 名称列表（可选，默认 [""]）
        - timeout: HTTP 超时时间（秒，可选）
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        base_url = config.get("base_url") or MAINNET_API_URL
        self.base_url: str = base_url

        api_key = (config.get("api_key") or "").strip()
        private_key = (config.get("private_key") or config.get("secret_key") or "").strip()
        signer_key = api_key or private_key
        if not signer_key:
            raise ValueError("Hype 配置中必须包含 api_key（推荐）或 private_key/secret_key（兼容）")

        # 兼容 0x 前缀和裸 hex
        if signer_key.startswith("0x") or signer_key.startswith("0X"):
            self._wallet: LocalAccount = Account.from_key(signer_key)
        else:
            self._wallet = Account.from_key("0x" + signer_key)

        self.address: str = (config.get("account_address") or self._wallet.address).strip()
        if api_key and not config.get("account_address"):
            raise ValueError("使用 api_key 时请配置 account_address（主账户地址，而非 API Wallet 地址）")
        self.perp_dexs: Optional[List[str]] = config.get("perp_dexs")
        self.timeout: Optional[float] = None
        if "timeout" in config:
            try:
                self.timeout = float(config["timeout"])
            except (TypeError, ValueError):
                self.timeout = None

        # Info 用于行情 / 账户查询；Exchange 用于带签名的写操作
        self.info = Info(
            base_url=self.base_url,
            skip_ws=True,
            perp_dexs=self.perp_dexs,
            timeout=self.timeout,
        )
        self.exchange = Exchange(
            wallet=self._wallet,
            base_url=self.base_url,
            account_address=self.address,
            perp_dexs=self.perp_dexs,
            timeout=self.timeout,
        )

    def _default_dex(self) -> str:
        """返回默认 dex（优先取配置中的第一个有效 perp_dex）。"""
        if not self.perp_dexs:
            return ""
        for dex in self.perp_dexs:
            dex_name = str(dex or "").strip()
            if dex_name:
                return dex_name
        return ""

    def _resolve_dex(self, symbol: Optional[str] = None) -> str:
        """
        根据 symbol 推断 dex。
        - builder 市场 symbol 形如 `xyz:SILVER` -> dex=xyz
        - 否则回退到配置默认 dex
        """
        if symbol:
            symbol_str = str(symbol)
            if ":" in symbol_str:
                return symbol_str.split(":", 1)[0]
        return self._default_dex()

    # ------------------------------------------------------------------ #
    # 基础接口实现
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        """
        连接到 Hype 交易所。

        Hyperliquid 的 HTTP 接口不需要单独登录，只要本地有私钥即可签名。
        这里不强制做 user_state 检查，以避免因账户无权益导致错误。
        """
        return True

    def get_balance(self) -> Balance:
        """
        查询账户余额（以期货账户为主）。
        """
        try:
            user_state = self.info.user_state(self.address, dex=self._default_dex())
        except Exception as e:  # pragma: no cover - 直接抛给上层
            raise Exception(f"Hype 查询余额失败: {e}")

        margin_summary = user_state.get("marginSummary", {}) or {}
        # accountValue 代表账户总权益
        total_str = margin_summary.get("accountValue", "0")
        withdrawable_str = user_state.get("withdrawable", "0")

        try:
            total_val = Decimal(str(total_str))
        except Exception:
            total_val = Decimal("0")
        try:
            withdrawable_val = Decimal(str(withdrawable_str))
        except Exception:
            withdrawable_val = total_val

        # Hype 的 user_state 中未直接暴露总未实现 pnl，这里简单置 0，
        # 如后续需要可从各 position["unrealizedPnl"] 聚合。
        return Balance(
            total_balance=total_val,
            available_balance=withdrawable_val,
            equity=total_val,
            unrealized_pnl=Decimal("0"),
            margin_used=None,
            margin_available=None,
        )

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        查询永续持仓信息。

        Hype 返回的 user_state 中：
            user_state["assetPositions"] -> 每个元素包含 position 字段。
        """
        dex = self._resolve_dex(symbol)
        try:
            user_state = self.info.user_state(self.address, dex=dex)
        except Exception as e:
            raise Exception(f"Hype 查询持仓失败: {e}")

        asset_positions = user_state.get("assetPositions", []) or []
        positions: List[Position] = []

        for item in asset_positions:
            pos_data = item.get("position") or {}
            coin = pos_data.get("coin")
            if not coin:
                continue

            if symbol is not None and str(coin) != str(symbol):
                continue

            szi_str = pos_data.get("szi", "0")
            try:
                szi = Decimal(str(szi_str))
            except Exception:
                continue

            if szi == 0:
                continue

            side = "long" if szi > 0 else "short"
            entry_px_str = pos_data.get("entryPx") or "0"
            unrealized_pnl_str = pos_data.get("unrealizedPnl") or "0"

            try:
                entry_px = Decimal(str(entry_px_str))
            except Exception:
                entry_px = Decimal("0")

            try:
                unrealized_pnl = Decimal(str(unrealized_pnl_str))
            except Exception:
                unrealized_pnl = Decimal("0")

            # mark_price 可以从 activeAssetCtx 获取，这里用 entryPx 作占位，避免引入额外查询
            mark_price = entry_px

            positions.append(
                Position(
                    symbol=str(coin),
                    size=abs(szi),
                    side=side,
                    entry_price=entry_px,
                    mark_price=mark_price,
                    unrealized_pnl=unrealized_pnl,
                    leverage=None,
                    margin_mode=None,
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
        **kwargs: Any,
    ) -> Order:
        """
        下单实现：
            - 限价单：直接使用传入价格；
            - 市价单：内部转换为带滑点的 IOC 限价单。
        """
        name = symbol
        side_lower = side.lower()
        is_buy = side_lower in ["buy", "long"]

        tif_map = {
            "gtc": "Gtc",
            "ioc": "Ioc",
            "fok": "Ioc",  # Hype 没有单独的 FOK，这里用 IOC 近似
            "alo": "Alo",
        }
        tif = tif_map.get(time_in_force.lower(), "Gtc")

        # 统一使用 Exchange.order 接口，order_type 为 wire dict
        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("限价单必须指定价格")
            limit_px = float(price)
        elif order_type.lower() == "market":
            # 使用内部 _slippage_price 计算激进价格，再下 IOC 限价单模拟市价
            # 默认滑点 5%，如需调整可在 config 中扩展。
            limit_px = self.exchange._slippage_price(name, is_buy, self.exchange.DEFAULT_SLIPPAGE)  # type: ignore[attr-defined]
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")

        order_type_wire = {"limit": {"tif": tif}}

        cloid: Optional[Cloid] = None
        if client_order_id:
            # client_order_id 需要是 16 字节 hex（以 0x 开头）
            try:
                cloid = Cloid.from_str(client_order_id)
            except Exception:
                cloid = None

        try:
            result = self.exchange.order(
                name=name,
                is_buy=is_buy,
                sz=float(quantity),
                limit_px=limit_px,
                order_type=order_type_wire,
                reduce_only=reduce_only,
                cloid=cloid,
            )
        except Exception as e:
            raise Exception(f"Hype 下单失败: {e}")

        status = str(result.get("status", "")).lower()
        if status != "ok":
            raise Exception(f"Hype 下单失败: {result}")

        # 解析返回的 oid（如果有），否则使用 cloid 或空字符串
        order_id = ""
        try:
            resp = result.get("response", {})
            data = (resp or {}).get("data", {})
            statuses = data.get("statuses") or []
            if statuses:
                st0 = statuses[0]
                resting = st0.get("resting") or {}
                if "oid" in resting:
                    order_id = str(resting["oid"])
        except Exception:
            order_id = ""

        if not order_id and client_order_id:
            order_id = client_order_id

        return Order(
            order_id=order_id,
            symbol=name,
            side="buy" if is_buy else "sell",
            order_type="limit" if order_type.lower() == "limit" else "market",
            quantity=quantity,
            price=Decimal(str(limit_px)),
            filled_quantity=Decimal("0"),
            status="pending",
            time_in_force=time_in_force.lower(),
            reduce_only=reduce_only,
            client_order_id=client_order_id,
        )

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        """
        撤单：
            - 优先使用 client_order_id（cloid）；
            - 否则使用 oid。
        """
        if not symbol:
            raise ValueError("Hype 撤单必须指定 symbol")

        name = symbol

        try:
            if client_order_id:
                cloid = Cloid.from_str(client_order_id)
                self.exchange.cancel_by_cloid(name, cloid)
                return True

            if order_id is None:
                raise ValueError("必须提供 order_id 或 client_order_id")

            oid = int(order_id)
            self.exchange.cancel(name, oid)
            return True
        except Exception as e:
            raise Exception(f"Hype 撤单失败: {e}")

    def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
    ) -> bool:
        """
        撤销所有未成交订单（可选按单一 symbol 限定）。
        """
        dex = self._resolve_dex(symbol)
        try:
            open_orders = self.info.open_orders(self.address, dex=dex)
        except Exception as e:
            raise Exception(f"Hype 查询未成交订单失败: {e}")

        ok = True
        for od in open_orders or []:
            coin = od.get("coin")
            if symbol is not None and str(coin) != str(symbol):
                continue
            oid = od.get("oid")
            if oid is None:
                continue
            try:
                self.exchange.cancel(str(coin), int(oid))
            except Exception:
                ok = False
        return ok

    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        """
        查询单个订单状态。

        Hype 官方接口以 oid 或 cloid（作为 oid 传入）查询，这里做一个简单封装。
        """
        if order_id is None and client_order_id is None:
            raise ValueError("必须提供 order_id 或 client_order_id")

        # 这里简化为直接通过 oid 查询；更精细的实现可以结合 cloid。
        if order_id is None:
            # 对 cloid 做一个弱转换：尝试当成 int 解析失败则返回 None
            try:
                oid_int = int(client_order_id)  # type: ignore[arg-type]
            except Exception:
                return None
        else:
            try:
                oid_int = int(order_id)
            except Exception:
                return None

        try:
            status = self.info.query_order_by_oid(self.address, oid_int)
        except Exception:
            return None

        # query_order_by_oid 的返回格式较复杂，这里只做非常简化的解析
        try:
            coin = status.get("coin", symbol or "")
            limit_px = status.get("limitPx") or status.get("px") or "0"
            sz_str = status.get("sz") or "0"
            side_raw = status.get("side") or "A"

            price = Decimal(str(limit_px))
            qty = Decimal(str(sz_str))

            side = "buy" if str(side_raw) in ["B", "buy"] else "sell"

            return Order(
                order_id=str(oid_int),
                symbol=str(coin),
                side=side,
                order_type="limit",
                quantity=qty,
                price=price,
                filled_quantity=Decimal("0"),
                status="open",
                time_in_force=None,
                reduce_only=False,
                client_order_id=client_order_id,
            )
        except Exception:
            return None

    def get_open_orders(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """
        查询所有未成交订单。
        """
        dex = self._resolve_dex(symbol)
        try:
            open_orders = self.info.open_orders(self.address, dex=dex)
        except Exception as e:
            raise Exception(f"Hype 查询未成交订单失败: {e}")

        results: List[Order] = []
        for od in open_orders or []:
            coin = od.get("coin")
            if symbol is not None and str(coin) != str(symbol):
                continue

            limit_px = od.get("limitPx") or "0"
            sz_str = od.get("sz") or "0"
            side_raw = od.get("side") or "A"

            try:
                price = Decimal(str(limit_px))
            except Exception:
                price = Decimal("0")
            try:
                qty = Decimal(str(sz_str))
            except Exception:
                qty = Decimal("0")

            side = "buy" if str(side_raw) in ["B", "buy"] else "sell"

            results.append(
                Order(
                    order_id=str(od.get("oid", "")),
                    symbol=str(coin),
                    side=side,
                    order_type="limit",
                    quantity=qty,
                    price=price,
                    filled_quantity=Decimal("0"),
                    status="open",
                    time_in_force=None,
                    reduce_only=bool(od.get("reduceOnly", False)),
                    client_order_id=None,
                )
            )

        return results

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取最新价格（通过 L2 快照估算）。
        """
        try:
            snapshot = self.info.l2_snapshot(symbol)
        except Exception as e:
            raise Exception(f"Hype 获取行情失败: {e}")

        levels = snapshot.get("levels") or []
        bids = levels[0] if len(levels) > 0 else []
        asks = levels[1] if len(levels) > 1 else []

        def _best_price(side_levels: List[Dict[str, Any]], reverse: bool) -> Optional[float]:
            if not side_levels:
                return None
            try:
                prices = [float(lvl["px"]) for lvl in side_levels]
                return (max if reverse else min)(prices)
            except Exception:
                return None

        best_bid = _best_price(bids, reverse=True)
        best_ask = _best_price(asks, reverse=False)

        mid = None
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2.0

        return {
            "symbol": symbol,
            "bid_price": best_bid,
            "ask_price": best_ask,
            "mid_price": mid,
            "last_price": None,
            "mark_price": None,
            "index_price": None,
            "timestamp": int(snapshot.get("time", 0)),
        }

    def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """
        获取订单簿（从 L2 快照直接构造）。
        """
        try:
            snapshot = self.info.l2_snapshot(symbol)
        except Exception as e:
            raise Exception(f"Hype 获取订单簿失败: {e}")

        levels = snapshot.get("levels") or []
        bids_raw = levels[0] if len(levels) > 0 else []
        asks_raw = levels[1] if len(levels) > 1 else []

        def _convert(side_levels: List[Dict[str, Any]]) -> List[List[float]]:
            result: List[List[float]] = []
            for lvl in side_levels[: depth if depth > 0 else None]:
                try:
                    px = float(lvl["px"])
                    sz = float(lvl["sz"])
                    result.append([px, sz])
                except Exception:
                    continue
            return result

        bids = _convert(bids_raw)
        asks = _convert(asks_raw)

        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "timestamp": int(snapshot.get("time", 0)),
        }

