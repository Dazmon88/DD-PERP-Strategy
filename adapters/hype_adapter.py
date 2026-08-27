"""
Hyperliquid (Hype) Exchange Adapter Implementation

本模块基于 `exchange/exchange_hype` 提供的官方 SDK，
实现统一的 `BasePerpAdapter` 接口，方便在策略层无缝切换交易所。
"""

import os
import sys
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

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
from adapters.hype_stream import HypeMarketStream

from hyperliquid.exchange import Exchange  # type: ignore
from hyperliquid.info import Info  # type: ignore
from hyperliquid.utils.constants import MAINNET_API_URL  # type: ignore
from hyperliquid.utils.types import Cloid  # type: ignore

# 永续价格最多 5 位有效数字，且小数位不超过 MAX_DECIMALS - szDecimals
_PERP_MAX_DECIMALS = 6
# 整数价永远合法，所以 10 万以上直接取整
_INT_PX_ABOVE = 100_000
_UNIFIED_MODES = {"unifiedAccount", "portfolioMargin"}
_STABLE_COINS = {"USDC", "USDH", "USDT0", "USDE", "USDT"}


def normalize_hype_symbol(symbol: str) -> str:
    """Hyperliquid 的 coin 就是原名，builder dex 带 `io:` 前缀，原样保留。"""
    return (symbol or "").strip()


def hype_dex_of(symbol: str) -> str:
    """`io:ANTH` → `io`；主 dex 返回空串。"""
    text = normalize_hype_symbol(symbol)
    return text.split(":", 1)[0] if ":" in text else ""


def resolve_hype_tif(time_in_force: str, post_only: bool = False) -> str:
    """gtc/ioc → Gtc/Ioc；post_only / alo 一律 Alo，否则 Maker 会吃单。"""
    tif = (time_in_force or "gtc").strip().lower().replace("-", "_")
    if post_only or tif in ("alo", "post_only", "postonly"):
        return "Alo"
    return {"gtc": "Gtc", "ioc": "Ioc", "fok": "Ioc"}.get(tif, "Gtc")


def round_hype_px(px: float, sz_decimals: int) -> float:
    """按官方 rounding.py 的规则收敛价格，否则挂单会被拒。"""
    value = float(px)
    if value > _INT_PX_ABOVE:
        return float(round(value))
    decimals = max(0, _PERP_MAX_DECIMALS - int(sz_decimals))
    return round(float(f"{value:.5g}"), decimals)


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        if value is None or value == "":
            return Decimal(default)
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def is_hype_unified(mode: Any) -> bool:
    text = str(mode or "").strip().strip('"').strip("'")
    return text in _UNIFIED_MODES


def spot_marks_from_ctxs(meta_and_ctxs: Any) -> Dict[str, Decimal]:
    """现货 coin → USD 标记价。报价是稳定币的才收。"""
    marks = {name: Decimal("1") for name in _STABLE_COINS}
    if not isinstance(meta_and_ctxs, (list, tuple)) or len(meta_and_ctxs) < 2:
        return marks
    meta, ctxs = meta_and_ctxs[0] or {}, meta_and_ctxs[1] or []
    tokens: Dict[int, Dict[str, Any]] = {}
    for i, tok in enumerate((meta or {}).get("tokens") or []):
        if not isinstance(tok, dict):
            continue
        try:
            tokens[int(tok.get("index", i))] = tok
        except (TypeError, ValueError):
            tokens[i] = tok
    for i, u in enumerate((meta or {}).get("universe") or []):
        if i >= len(ctxs or []):
            break
        ctx = ctxs[i] or {}
        px = ctx.get("markPx") or ctx.get("midPx")
        if px in (None, ""):
            continue
        pair = (u or {}).get("tokens") or []
        if len(pair) < 2:
            continue
        try:
            base = tokens.get(int(pair[0])) or {}
            quote = tokens.get(int(pair[1])) or {}
        except (TypeError, ValueError):
            continue
        qname = str(quote.get("name") or "")
        bname = str(base.get("name") or "")
        if qname in _STABLE_COINS and bname:
            marks[bname] = _dec(px)
    return marks


def spot_equity_from_state(
    state: Any, marks: Dict[str, Decimal]
) -> tuple[Decimal, Decimal]:
    """现货市值 USD、稳定币可用 USD。unified 下 USDC 优先用 maintenance 后可用。"""
    equity = Decimal("0")
    stables_free = Decimal("0")
    if not isinstance(state, dict):
        return equity, stables_free
    for item in state.get("balances") or []:
        if not isinstance(item, dict):
            continue
        coin = str(item.get("coin") or "")
        total = _dec(item.get("total"))
        hold = _dec(item.get("hold"))
        if total == 0 and hold == 0:
            continue
        px = marks.get(coin)
        if px is None:
            continue
        equity += total * px
        free = total - hold
        if free < 0:
            free = Decimal("0")
        if coin in _STABLE_COINS:
            stables_free += free * px
    available = stables_free
    t2a = state.get("tokenToAvailableAfterMaintenance")
    rows = t2a if isinstance(t2a, list) else []
    if isinstance(t2a, dict):
        rows = list(t2a.items())
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            if int(row[0]) == 0:
                available = _dec(row[1])
                break
        except (TypeError, ValueError):
            continue
    return equity, available


def px_tick_at(px: float, sz_decimals: int) -> Decimal:
    """当前价位下的最小报价步进：5 位有效数字与小数位上限取更粗的那个。"""
    value = abs(float(px))
    if value <= 0:
        return Decimal("0")
    if value > _INT_PX_ABOVE:
        return Decimal("1")
    decimals = max(0, _PERP_MAX_DECIMALS - int(sz_decimals))
    # 5 位有效数字允许的小数位：如 2005.1 -> 1 位，14.692 -> 3 位
    int_digits = len(str(int(value))) if value >= 1 else 0
    sig_decimals = max(0, 5 - int_digits)
    return Decimal(1).scaleb(-min(decimals, sig_decimals))


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
        self._wallet: Optional[LocalAccount] = None
        self.exchange: Optional[Exchange] = None
        self.address: str = str(config.get("account_address") or "").strip()
        if signer_key:
            # 兼容 0x 前缀和裸 hex
            if signer_key.startswith("0x") or signer_key.startswith("0X"):
                self._wallet = Account.from_key(signer_key)
            else:
                self._wallet = Account.from_key("0x" + signer_key)
            if not self.address:
                self.address = self._wallet.address
            if api_key and not str(config.get("account_address") or "").strip():
                raise ValueError("使用 api_key 时请配置 account_address（主账户地址，而非 API Wallet 地址）")
        self.perp_dexs: Optional[List[str]] = config.get("perp_dexs")
        self.timeout: Optional[float] = None
        if "timeout" in config:
            try:
                self.timeout = float(config["timeout"])
            except (TypeError, ValueError):
                self.timeout = None

        # Info 用于行情 / 账户查询；Exchange 用于带签名的写操作。
        # 永续不需要现货 meta；传空表跳过一次 HTTP，也避开 token index 稀疏导致的 SDK 崩。
        _empty_spot = {"universe": [], "tokens": []}
        self.info = Info(
            base_url=self.base_url,
            skip_ws=True,
            spot_meta=_empty_spot,
            perp_dexs=self.perp_dexs,
            timeout=self.timeout,
        )
        if self._wallet is not None:
            self.exchange = Exchange(
                wallet=self._wallet,
                base_url=self.base_url,
                account_address=self.address,
                spot_meta=_empty_spot,
                perp_dexs=self.perp_dexs,
                timeout=self.timeout,
            )

        self.network: str = str(config.get("network") or "mainnet")
        self.ws_url: Optional[str] = config.get("ws_url") or None
        self.market_stream: Optional[HypeMarketStream] = None
        # get_balance 和 get_positions 会连着各查一次 user_state，
        # 账户 REST 兜底每几秒跑一次，短 TTL 合并成一次请求省配额
        self._state_ttl: float = float(config.get("state_ttl_sec", 1.0))
        self._state_cache: Dict[str, Tuple[float, Any]] = {}
        self._sz_decimals: Dict[str, Dict[str, int]] = {}
        self._abs_cache: Optional[Tuple[float, str]] = None
        self._mark_cache: Optional[Tuple[float, Dict[str, Decimal]]] = None

    # ------------------------------------------------------------------ #
    # 元数据 / 精度
    # ------------------------------------------------------------------ #

    def _sz_decimals_map(self, dex: str) -> Dict[str, int]:
        """{coin: szDecimals}。builder dex 各有各的 universe，按 dex 缓存。"""
        cached = self._sz_decimals.get(dex)
        if cached is not None:
            return cached
        out: Dict[str, int] = {}
        try:
            meta = self.info.meta(dex=dex) if dex else self.info.meta()
            for item in (meta or {}).get("universe") or []:
                name = str((item or {}).get("name") or "")
                if name:
                    out[name] = int(item.get("szDecimals") or 0)
        except Exception:
            pass
        if out:
            self._sz_decimals[dex] = out
        return out

    def sz_decimals_of(self, symbol: str) -> int:
        coin = normalize_hype_symbol(symbol)
        table = self._sz_decimals_map(hype_dex_of(coin))
        return int(table.get(coin, 2))

    def get_market_filters(self, symbol: str) -> Dict[str, Decimal]:
        """数量步进来自 szDecimals；价格步进随当前价位变（5 位有效数字）。

        调用方通常只查一次就缓存，所以这里给的是「当前价位」的步进。
        价格若涨过一个数量级（如 9999 → 10001），步进会变粗，缓存下来的
        细步进就会挂单被拒；ANTH/SNDK 这类离边界很远的品种不受影响。
        """
        coin = normalize_hype_symbol(symbol)
        sz_dec = self.sz_decimals_of(coin)
        base_inc = Decimal(1).scaleb(-sz_dec)
        quote_inc = Decimal("0")
        try:
            bid, ask = self._book_bbo(coin)
            ref = None
            if bid and ask:
                ref = (float(bid) + float(ask)) / 2.0
            if ref:
                quote_inc = px_tick_at(ref, sz_dec)
        except Exception:
            pass
        return {
            "base_inc": base_inc,
            "quote_inc": quote_inc,
            # Hyperliquid 没有 minQty，但有 10 美元名义下限，交给上层名义校验
            "min_size": base_inc,
        }

    def _book_bbo(self, symbol: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        book = self.get_orderbook(symbol, depth=1) or {}
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        bid = Decimal(str(bids[0][0])) if bids else None
        ask = Decimal(str(asks[0][0])) if asks else None
        return bid, ask

    # ------------------------------------------------------------------ #
    # WebSocket
    # ------------------------------------------------------------------ #

    async def connect_market_stream(self) -> HypeMarketStream:
        if self.market_stream is None:
            self.market_stream = HypeMarketStream(
                base_url=self.ws_url or self.base_url,
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
        **kwargs: Any,
    ) -> None:
        stream = await self.connect_market_stream()
        await stream.subscribe_market(
            topic=channel,
            symbol=normalize_hype_symbol(symbol),
            callback=callback,
            **kwargs,
        )

    async def subscribe_account(
        self,
        topic: str,
        callback: Optional[Callable] = None,
        user: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        stream = await self.connect_market_stream()
        await stream.subscribe_account(
            topic=topic,
            user=(user or self.address),
            callback=callback,
            **kwargs,
        )

    def _user_state(self, dex: str) -> Dict[str, Any]:
        """带短 TTL 的 user_state，避免余额和持仓各打一次请求。"""
        now = time.time()
        hit = self._state_cache.get(dex)
        if hit is not None and now - hit[0] < self._state_ttl:
            return hit[1]
        state = self.info.user_state(self.address, dex=dex)
        self._state_cache[dex] = (now, state)
        return state

    def _default_dex(self) -> str:
        """返回默认 dex（优先取配置中的第一个有效 perp_dex）。"""
        if not self.perp_dexs:
            return ""
        for dex in self.perp_dexs:
            dex_name = str(dex or "").strip()
            if dex_name:
                return dex_name
        return ""

    def _dex_candidates(self) -> List[str]:
        """撤单兜底查持仓/挂单时，主 dex 和配置里的 builder dex 都扫一遍。"""
        seen = set()
        out: List[str] = []
        for dex in [self._default_dex(), ""] + list(self.perp_dexs or []):
            name = str(dex or "").strip()
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
        if "" not in seen:
            out.append("")
        return out

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

    def _abstraction_mode(self) -> str:
        now = time.time()
        hit = self._abs_cache
        if hit is not None and now - hit[0] < 60.0:
            return hit[1]
        mode = "disabled"
        try:
            raw = self.info.query_user_abstraction_state(self.address)
            if isinstance(raw, str) and raw.strip():
                mode = raw.strip().strip('"').strip("'")
        except Exception:
            pass
        self._abs_cache = (now, mode)
        return mode

    def _spot_marks(self) -> Dict[str, Decimal]:
        now = time.time()
        hit = self._mark_cache
        if hit is not None and now - hit[0] < 15.0:
            return hit[1]
        marks = {name: Decimal("1") for name in _STABLE_COINS}
        try:
            marks = spot_marks_from_ctxs(self.info.spot_meta_and_asset_ctxs())
        except Exception:
            pass
        self._mark_cache = (now, marks)
        return marks

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
        """净值：unified 看现货市值（永续 clearinghouse 恒为 0）；标准模式永续+现货。

        可用：unified 用 USDC maintenance 后可用（HIP-3 仍要 USDC 保证金）；
        标准模式用各 dex withdrawable。
        """
        if not self.address:
            raise Exception("Hype 查询余额失败: 未配置 account_address")
        try:
            unified = is_hype_unified(self._abstraction_mode())
            perp_eq = Decimal("0")
            perp_av = Decimal("0")
            position_value = Decimal("0")
            for dex in self._dex_candidates():
                state = self._user_state(dex)
                margin = (state or {}).get("marginSummary") or {}
                if not unified:
                    perp_eq += _dec(margin.get("accountValue"))
                    perp_av += _dec((state or {}).get("withdrawable"))
                for item in (state or {}).get("assetPositions") or []:
                    pos = (item or {}).get("position") or {}
                    position_value += _dec(pos.get("positionValue"))
            spot_eq = Decimal("0")
            spot_av = Decimal("0")
            try:
                spot_eq, spot_av = spot_equity_from_state(
                    self.info.spot_user_state(self.address),
                    self._spot_marks(),
                )
            except Exception:
                pass
            if unified:
                equity = spot_eq
                available = spot_av
            else:
                equity = perp_eq + spot_eq
                available = perp_av
            return Balance(
                total_balance=equity,
                available_balance=available,
                equity=equity,
                unrealized_pnl=Decimal("0"),
                margin_used=None,
                margin_available=None,
                position_value=position_value,
            )
        except Exception as e:
            raise Exception(f"Hype 查询余额失败: {e}")

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        查询永续持仓信息。

        Hype 返回的 user_state 中：
            user_state["assetPositions"] -> 每个元素包含 position 字段。
        """
        dexes = [self._resolve_dex(symbol)] if symbol else self._dex_candidates()
        try:
            asset_positions: list = []
            seen = set()
            for dex in dexes:
                user_state = self._user_state(dex)
                for item in user_state.get("assetPositions", []) or []:
                    pos_data = item.get("position") or {}
                    coin = pos_data.get("coin")
                    key = str(coin or "")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    asset_positions.append(item)
        except Exception as e:
            raise Exception(f"Hype 查询持仓失败: {e}")

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

    def get_positions_table_data(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取持仓表格数据（用于 TG 等展示），含币种、数量、清算价、标记价、保证金、仓位价值、资金费率。
        """
        dex = self._resolve_dex(symbol)
        try:
            user_state = self.info.user_state(self.address, dex=dex)
        except Exception as e:
            raise Exception(f"Hype 查询持仓失败: {e}")

        coin_to_ctx: Dict[str, Any] = {}
        try:
            meta_and_ctxs = self.info.meta_and_asset_ctxs()
            if isinstance(meta_and_ctxs, (list, tuple)) and len(meta_and_ctxs) >= 2:
                meta, asset_ctxs = meta_and_ctxs[0], meta_and_ctxs[1]
                universe = (meta or {}).get("universe") or []
                for i, asset_info in enumerate(universe):
                    if i < len(asset_ctxs):
                        name = (asset_info or {}).get("name") or ""
                        if name:
                            coin_to_ctx[name] = asset_ctxs[i] or {}
        except Exception:
            pass

        rows: List[Dict[str, Any]] = []
        for item in user_state.get("assetPositions", []) or []:
            pos = item.get("position") or {}
            coin = pos.get("coin")
            if not coin:
                continue
            if symbol is not None and str(coin) != str(symbol):
                continue
            szi_str = pos.get("szi", "0")
            try:
                szi = Decimal(str(szi_str))
            except Exception:
                continue
            if szi == 0:
                continue

            ctx = coin_to_ctx.get(str(coin), {})
            liquidation_px = pos.get("liquidationPx") or "-"
            margin_used = pos.get("marginUsed") or "0"
            position_value = pos.get("positionValue") or "0"
            mark_px = ctx.get("markPx") or "-"
            funding = ctx.get("funding") or "-"

            rows.append({
                "coin": str(coin),
                "size": abs(float(szi)),
                "side": "long" if szi > 0 else "short",
                "liquidation_px": liquidation_px,
                "mark_px": mark_px,
                "margin_used": margin_used,
                "position_value": position_value,
                "funding": funding,
            })
        return rows

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
        if self.exchange is None:
            raise Exception("Hype 未配置私钥，无法下单")

        name = normalize_hype_symbol(symbol)
        side_lower = side.lower()
        is_buy = side_lower in ["buy", "long"]
        post_only = bool(kwargs.get("post_only") or kwargs.get("postOnly"))
        tif = resolve_hype_tif(time_in_force, post_only=post_only)
        sz_dec = self.sz_decimals_of(name)
        sz = float(round(float(quantity), sz_dec))

        # 统一使用 Exchange.order 接口，order_type 为 wire dict
        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("限价单必须指定价格")
            limit_px = round_hype_px(float(price), sz_dec)
        elif order_type.lower() == "market":
            # 使用内部 _slippage_price 计算激进价格，再下 IOC 限价单模拟市价
            # 默认滑点 5%，如需调整可在 config 中扩展。
            limit_px = round_hype_px(
                float(self.exchange._slippage_price(name, is_buy, self.exchange.DEFAULT_SLIPPAGE)),  # type: ignore[attr-defined]
                sz_dec,
            )
            tif = "Ioc"
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
                sz=sz,
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
                if isinstance(st0, dict) and st0.get("error"):
                    raise Exception(f"Hype 下单失败: {st0.get('error')}")
                filled = st0.get("filled") or {}
                resting = st0.get("resting") or {}
                if "oid" in resting:
                    order_id = str(resting["oid"])
                elif "oid" in filled:
                    order_id = str(filled["oid"])
        except Exception as exc:
            if "Hype 下单失败" in str(exc):
                raise
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
            found = ""
            if order_id and self.exchange is not None:
                for dex in self._dex_candidates():
                    try:
                        for od in self.info.open_orders(self.address, dex=dex) or []:
                            if str((od or {}).get("oid")) == str(order_id):
                                found = str((od or {}).get("coin") or "")
                                break
                    except Exception:
                        continue
                    if found:
                        break
            if not found:
                raise ValueError("Hype 撤单必须指定 symbol")
            symbol = found

        name = normalize_hype_symbol(symbol)

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

