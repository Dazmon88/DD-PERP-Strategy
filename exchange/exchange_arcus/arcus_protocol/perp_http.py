"""
Arcus Perps HTTP API Client

文档: https://docs.arcus.xyz/llms.txt
主网: https://api.arcus.xyz
测试网: https://api.testnet.arcus.xyz
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

from .orders import (
    build_cancel_order_body,
    build_cancel_typed_payload,
    build_place_order_body,
    build_place_typed_payload,
    default_good_til_time_us,
)
from .perps_auth import ArcusAuth, timestamp_ns

REST_URLS = {
    "mainnet": "https://api.arcus.xyz",
    "testnet": "https://api.testnet.arcus.xyz",
    "staging": "https://api.staging.arcus.xyz",
}


def _retry_after_seconds(resp: requests.Response, attempt: int) -> float:
    """解析 429 的等待秒数：优先 Retry-After / body.retry_after，否则指数退避。"""
    hdr = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    if hdr:
        try:
            return max(1.0, float(hdr))
        except ValueError:
            pass
    try:
        body = resp.json()
        if isinstance(body, dict):
            ra = body.get("retry_after") or body.get("retryAfter")
            if ra is not None:
                return max(1.0, float(ra))
    except Exception:
        pass
    return float(min(120.0, (2**attempt) * 2.0))


class ArcusPerpHTTP:
    """Arcus REST 客户端"""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        auth: Optional[ArcusAuth] = None,
        timeout: float = 15.0,
        max_retries: int = 5,
    ):
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            if network not in REST_URLS:
                raise ValueError(f"未知 network: {network}，可选: {list(REST_URLS)}")
            self.base_url = REST_URLS[network]
        self.network = network
        self.auth = auth
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self._session = requests.Session()
        self._markets_cache: Optional[Dict[Any, Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _dump_body(self, json_body: Any) -> str:
        if json_body is None:
            return ""
        return json.dumps(json_body, separators=(",", ":"), ensure_ascii=False)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        allow_statuses: Optional[Sequence[int]] = None,
    ) -> Any:
        clean_params = None
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}

        body_str = self._dump_body(json_body)
        hdrs = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            hdrs.update(headers)

        ok_statuses = set(allow_statuses or ()) | {200, 201, 202}
        attempts = self.max_retries + 1
        last_err: Optional[Exception] = None

        for attempt in range(attempts):
            resp = self._session.request(
                method=method.upper(),
                url=self._url(path),
                params=clean_params,
                data=body_str.encode("utf-8") if body_str else None,
                headers=hdrs,
                timeout=self.timeout,
            )
            if resp.status_code == 429:
                wait = _retry_after_seconds(resp, attempt)
                last_err = ValueError(f"HTTP {resp.status_code}: {resp.text}")
                if attempt >= attempts - 1:
                    raise last_err
                print(
                    f"[arcus 429] {method.upper()} {path} "
                    f"第 {attempt + 1}/{self.max_retries} 次重试，休眠 {wait:.0f}s"
                )
                time.sleep(wait)
                continue

            if resp.status_code not in ok_statuses and not resp.ok:
                raise ValueError(f"HTTP {resp.status_code}: {resp.text}")

            if not resp.content:
                return {"status": resp.status_code}
            try:
                return resp.json()
            except Exception:
                return resp.text

        assert last_err is not None
        raise last_err

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        api_key: bool = False,
    ) -> Any:
        headers = None
        if api_key:
            if not self.auth:
                raise ValueError("该接口需要 ArcusAuth（X-API-Key）")
            headers = self.auth.api_key_headers()
        return self._request("GET", path, params=params, headers=headers)

    def _post_signed_order(
        self,
        path: str,
        *,
        body: Dict[str, Any],
        typed_payload: str,
        timestamp: Union[int, str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("写操作需要 ArcusAuth")
        sig = self.auth.sign_typed_payload(typed_payload)
        headers = self.auth.signed_headers(signature=sig, timestamp=timestamp)
        return self._request(
            "POST",
            path,
            params=params,
            json_body=body,
            headers=headers,
            allow_statuses=(200, 202),
        )

    def _post_legacy(
        self,
        path: str,
        *,
        action: str,
        body: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("写操作需要 ArcusAuth")
        signed = self.auth.sign_legacy_action(action=action, body=body)
        headers = self.auth.signed_headers(
            signature=signed["signature"],
            timestamp=signed["timestamp"],
        )
        return self._request(
            "POST",
            path,
            params=params,
            json_body=body,
            headers=headers,
            allow_statuses=(200, 202),
        )

    def _require_address(self, address: Optional[str] = None) -> str:
        addr = address or (self.auth.address if self.auth else None)
        if not addr:
            raise ValueError("需要 address（参数或 auth.address）")
        if not addr.startswith("0x"):
            addr = "0x" + addr
        return addr

    # ------------------------------------------------------------------
    # 市场缓存
    # ------------------------------------------------------------------

    def refresh_markets(self) -> Dict[Any, Dict[str, Any]]:
        data = self.get_markets()
        markets = data.get("markets", data) if isinstance(data, dict) else data
        cache: Dict[Any, Dict[str, Any]] = {}
        if isinstance(markets, list):
            for m in markets:
                if not isinstance(m, dict):
                    continue
                mid = m.get("marketId", m.get("id"))
                if mid is not None:
                    cache[int(mid)] = m
                    cache[str(mid)] = m
                names = [
                    m.get("marketDisplayName"),
                    m.get("market"),
                    m.get("name"),
                    m.get("symbol"),
                    m.get("fullAssetName"),
                ]
                base = m.get("baseAsset")
                quote = m.get("quoteAsset")
                if base and quote:
                    names.append(f"{base}-{quote}")
                    names.append(f"{base}{quote}")
                    names.append(str(base))
                for name in names:
                    if not name:
                        continue
                    cache[str(name)] = m
                    cache[str(name).upper()] = m
        self._markets_cache = cache
        return cache

    def resolve_market(
        self,
        market: Optional[Union[str, int]] = None,
        market_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if self._markets_cache is None:
            self.refresh_markets()
        assert self._markets_cache is not None
        if market_id is not None:
            m = self._markets_cache.get(int(market_id)) or self._markets_cache.get(
                str(market_id)
            )
            if not m:
                self.refresh_markets()
                m = self._markets_cache.get(int(market_id))
            if not m:
                raise ValueError(f"未知 marketId: {market_id}")
            return m
        if market is None:
            raise ValueError("需要 market 或 market_id")
        key = str(market).upper() if not str(market).isdigit() else str(market)
        m = self._markets_cache.get(key) or self._markets_cache.get(market)
        if not m and str(market).isdigit():
            m = self._markets_cache.get(int(market))
        if not m:
            self.refresh_markets()
            m = self._markets_cache.get(key)
        if not m:
            raise ValueError(f"未知 market: {market}")
        return m

    def market_meta(
        self,
        market: Optional[Union[str, int]] = None,
        market_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        m = self.resolve_market(market=market, market_id=market_id)
        mid = int(m.get("marketId", m.get("id")))
        return {
            "marketId": mid,
            "tickSize": m.get("tickSize"),
            "stepSize": m.get("stepSize"),
            "raw": m,
        }

    # ------------------------------------------------------------------
    # 公共 / 工具
    # ------------------------------------------------------------------

    def health(self) -> Any:
        return self._get("/health")

    def get_service_info(self) -> Any:
        return self._get("/v1/info")

    def get_server_time(self) -> Any:
        return self._get("/v1/time")

    def get_markets(self, market: Optional[str] = None) -> Any:
        params = {"market": market} if market else None
        return self._get("/v1/markets", params=params)

    def get_bbo(self, market: Optional[str] = None, market_id: Optional[int] = None) -> Any:
        """GET /v1/bbo/{market} — market 为 display name，如 BTC-USD。"""
        name = market
        if name is None and market_id is not None:
            name = self.market_meta(market_id=market_id)["raw"].get("marketDisplayName")
        if not name:
            raise ValueError("get_bbo 需要 market 或 market_id")
        return self._get(f"/v1/bbo/{name}")

    def get_all_mid_prices(self) -> Any:
        """GET /v1/mids"""
        return self._get("/v1/mids")

    def get_live_prices(self) -> Any:
        """GET /v1/prices — 全市场 oracle/mark。"""
        return self._get("/v1/prices")

    def get_l2_orderbook(
        self,
        market: Optional[str] = None,
        market_id: Optional[int] = None,
        levels: Optional[int] = None,
    ) -> Any:
        """GET /v1/l2OrderBook/{market}?nLevels=..."""
        name = market
        if name is None and market_id is not None:
            name = self.market_meta(market_id=market_id)["raw"].get("marketDisplayName")
        if not name:
            raise ValueError("get_l2_orderbook 需要 market 或 market_id")
        params = {"nLevels": levels} if levels is not None else None
        return self._get(f"/v1/l2OrderBook/{name}", params=params)

    def get_candles(self, **params: Any) -> Any:
        return self._get("/v1/candles", params=params or None)

    def get_recent_trades(self, **params: Any) -> Any:
        return self._get("/v1/trades", params=params or None)

    def get_trade(self, trade_id: str, **params: Any) -> Any:
        return self._get(f"/v1/trades/{trade_id}", params=params or None)

    def get_funding_rates(self, **params: Any) -> Any:
        return self._get("/v1/fundingRates", params=params or None)

    def get_fee_tier_table(self) -> Any:
        return self._get("/v1/feeTiers")

    def get_rate_limit_usage(self, **params: Any) -> Any:
        return self._get("/v1/rateLimitUsage", params=params or None, api_key=True)

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    def create_api_key(self, body: Dict[str, Any]) -> Any:
        """POST /v1/createApiKey（需主钱包 EIP-712 签名，无 Ed25519）。"""
        return self._request("POST", "/v1/createApiKey", json_body=body)

    def get_api_keys(self, address: str) -> Any:
        return self._get("/v1/apiKeys", params={"address": address})

    def revoke_api_key(self, body: Dict[str, Any]) -> Any:
        if not self.auth:
            raise ValueError("revokeApiKey 需要 ArcusAuth")
        # 多数撤销接口也走签名；若官方仅需 api key 则可简化
        return self._post_legacy("/v1/revokeApiKey", action="revokeApiKey", body=body)

    # ------------------------------------------------------------------
    # 账户读（address query；可选 X-API-Key）
    # ------------------------------------------------------------------

    def get_account(
        self,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
        *,
        api_key: bool = True,
    ) -> Any:
        addr = self._require_address(address)
        params: Dict[str, Any] = {"address": addr}
        if account_index is not None:
            params["accountIndex"] = account_index
        elif self.auth is not None:
            params["accountIndex"] = self.auth.account_index
        return self._get("/v1/account", params=params, api_key=api_key)

    def get_positions(
        self,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
        *,
        api_key: bool = True,
        **params: Any,
    ) -> Any:
        addr = self._require_address(address)
        p: Dict[str, Any] = {"address": addr, **params}
        if account_index is not None:
            p["accountIndex"] = account_index
        elif self.auth is not None:
            p["accountIndex"] = self.auth.account_index
        return self._get("/v1/positions", params=p, api_key=api_key)

    def get_open_orders(
        self,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
        *,
        api_key: bool = True,
        **params: Any,
    ) -> Any:
        addr = self._require_address(address)
        p: Dict[str, Any] = {"address": addr, **params}
        if account_index is not None:
            p["accountIndex"] = account_index
        elif self.auth is not None:
            p["accountIndex"] = self.auth.account_index
        return self._get("/v1/openOrders", params=p, api_key=api_key)

    def get_order_history(self, address: Optional[str] = None, **params: Any) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/orderHistory",
            params={"address": addr, **params},
            api_key=True,
        )

    def get_order_status(
        self,
        order_id: str,
        address: Optional[str] = None,
        **params: Any,
    ) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/orderStatus",
            params={"address": addr, "orderId": order_id, **params},
            api_key=True,
        )

    def get_fills(self, address: Optional[str] = None, **params: Any) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/fills",
            params={"address": addr, **params},
            api_key=True,
        )

    def get_funding_payments(self, address: Optional[str] = None, **params: Any) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/fundingPayments",
            params={"address": addr, **params},
            api_key=True,
        )

    def get_leverage(self, address: Optional[str] = None, **params: Any) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/leverage",
            params={"address": addr, **params},
            api_key=True,
        )

    def get_account_transfer_updates(
        self, address: Optional[str] = None, **params: Any
    ) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/accountTransferUpdates",
            params={"address": addr, **params},
            api_key=True,
        )

    def get_portfolio_history(self, address: Optional[str] = None, **params: Any) -> Any:
        addr = self._require_address(address)
        return self._get(
            "/v1/portfolioHistory",
            params={"address": addr, **params},
            api_key=True,
        )

    # ------------------------------------------------------------------
    # 交易写
    # ------------------------------------------------------------------

    def place_order(
        self,
        *,
        market: Optional[Union[str, int]] = None,
        market_id: Optional[int] = None,
        side: str,
        quantity: Union[str, int, float],
        price: Union[str, int, float],
        order_type: str = "LIMIT",
        time_in_force: Optional[str] = None,
        reduce_only: bool = False,
        client_id: Optional[str] = None,
        good_til_time_us: Optional[int] = None,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
        tick_size: Optional[Union[str, float]] = None,
        step_size: Optional[Union[str, float]] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("place_order 需要 ArcusAuth")
        addr = self._require_address(address)
        ai = int(
            account_index
            if account_index is not None
            else self.auth.account_index
        )
        meta = self.market_meta(market=market, market_id=market_id)
        mid = int(meta["marketId"])
        tick = tick_size or meta["tickSize"]
        step = step_size or meta["stepSize"]
        if tick is None or step is None:
            raise ValueError("缺少 tickSize/stepSize")

        gtt = int(good_til_time_us or default_good_til_time_us())
        ts = timestamp_ns()
        typed = build_place_typed_payload(
            address=addr,
            account_index=ai,
            market_id=mid,
            side=side,
            price=price,
            quantity=quantity,
            tick_size=tick,
            step_size=step,
            time_in_force=time_in_force or "GTT",
            reduce_only=reduce_only,
            good_til_time_us=gtt,
            client_id=client_id,
            timestamp_ns=ts,
        )
        body = build_place_order_body(
            address=addr,
            account_index=ai,
            market_id=mid,
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
        return self._post_signed_order(
            "/v1/placeOrder",
            body=body,
            typed_payload=typed,
            timestamp=ts,
            params={"address": addr},
        )

    def cancel_order(
        self,
        *,
        market: Optional[Union[str, int]] = None,
        market_id: Optional[int] = None,
        order_id: Optional[str] = None,
        client_id: Optional[str] = None,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("cancel_order 需要 ArcusAuth")
        addr = self._require_address(address)
        ai = int(
            account_index
            if account_index is not None
            else self.auth.account_index
        )
        mid = int(self.market_meta(market=market, market_id=market_id)["marketId"])
        ts = timestamp_ns()
        typed = build_cancel_typed_payload(
            address=addr,
            account_index=ai,
            market_id=mid,
            order_id=order_id,
            client_id=client_id,
            timestamp_ns=ts,
        )
        body = build_cancel_order_body(
            address=addr,
            account_index=ai,
            market_id=mid,
            order_id=order_id,
            client_id=client_id,
            timestamp_ns=ts,
        )
        return self._post_signed_order(
            "/v1/cancelOrder",
            body=body,
            typed_payload=typed,
            timestamp=ts,
            params={"address": addr},
        )

    def batch_place_orders(
        self,
        orders: Sequence[Dict[str, Any]],
        *,
        address: Optional[str] = None,
        shared_timestamp_ns: Optional[int] = None,
    ) -> Any:
        """
        批量下单。每个元素需含 place 字段；可传已拼好的 body 字段，
        或传 market/side/price/quantity 等由本方法补齐签名。
        """
        if not self.auth:
            raise ValueError("batch_place_orders 需要 ArcusAuth")
        if not orders:
            raise ValueError("orders 不能为空")
        if len(orders) > 100:
            raise ValueError("单次最多 100 笔")

        addr = self._require_address(address)
        ts = int(shared_timestamp_ns or timestamp_ns())
        signed_orders: List[Dict[str, Any]] = []
        first_sig: Optional[str] = None

        for raw in orders:
            item = dict(raw)
            mid = int(
                item.get("marketId")
                or self.market_meta(
                    market=item.get("market"), market_id=item.get("market_id")
                )["marketId"]
            )
            meta = self.market_meta(market_id=mid)
            ai = int(item.get("accountIndex", self.auth.account_index))
            side = item.get("orderSide") or item["side"]
            price = item.get("price")
            qty = item.get("quantity") or item.get("size")
            gtt = int(item.get("goodTilTime") or default_good_til_time_us())
            if isinstance(item.get("goodTilTime"), str):
                gtt = int(item["goodTilTime"])
            client_id = item.get("clientId") or item.get("client_id")
            reduce_only = bool(item.get("reduceOnly", item.get("reduce_only", False)))
            tif = item.get("timeInForce") or item.get("time_in_force") or "GTT"
            ot = item.get("orderType") or item.get("order_type") or "LIMIT"

            typed = build_place_typed_payload(
                address=addr,
                account_index=ai,
                market_id=mid,
                side=side,
                price=price,
                quantity=qty,
                tick_size=meta["tickSize"],
                step_size=meta["stepSize"],
                time_in_force=tif,
                reduce_only=reduce_only,
                good_til_time_us=gtt,
                client_id=client_id,
                timestamp_ns=ts,
            )
            sig = self.auth.sign_typed_payload(typed)
            if first_sig is None:
                first_sig = sig
            body = build_place_order_body(
                address=addr,
                account_index=ai,
                market_id=mid,
                side=side,
                quantity=qty,
                price=price,
                order_type=ot,
                time_in_force=tif,
                reduce_only=reduce_only,
                good_til_time_us=gtt,
                client_id=client_id,
                timestamp_ns=ts,
                signature=sig,
            )
            signed_orders.append(body)

        headers = self.auth.signed_headers(signature=first_sig or "", timestamp=ts)
        return self._request(
            "POST",
            "/v1/batchPlaceOrders",
            params={"address": addr},
            json_body={"orders": signed_orders},
            headers=headers,
            allow_statuses=(200, 202),
        )

    def batch_cancel_orders(
        self,
        cancels: Sequence[Dict[str, Any]],
        *,
        address: Optional[str] = None,
        shared_timestamp_ns: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("batch_cancel_orders 需要 ArcusAuth")
        if not cancels:
            raise ValueError("cancels 不能为空")
        if len(cancels) > 100:
            raise ValueError("单次最多 100 笔")

        addr = self._require_address(address)
        ts = int(shared_timestamp_ns or timestamp_ns())
        signed: List[Dict[str, Any]] = []
        first_sig: Optional[str] = None

        for raw in cancels:
            item = dict(raw)
            mid = int(
                item.get("marketId")
                or self.market_meta(
                    market=item.get("market"), market_id=item.get("market_id")
                )["marketId"]
            )
            ai = int(item.get("accountIndex", self.auth.account_index))
            order_id = item.get("orderId") or item.get("order_id")
            client_id = item.get("clientId") or item.get("client_id")
            typed = build_cancel_typed_payload(
                address=addr,
                account_index=ai,
                market_id=mid,
                order_id=order_id,
                client_id=client_id,
                timestamp_ns=ts,
            )
            sig = self.auth.sign_typed_payload(typed)
            if first_sig is None:
                first_sig = sig
            body = build_cancel_order_body(
                address=addr,
                account_index=ai,
                market_id=mid,
                order_id=order_id,
                client_id=client_id,
                timestamp_ns=ts,
                signature=sig,
            )
            signed.append(body)

        headers = self.auth.signed_headers(signature=first_sig or "", timestamp=ts)
        return self._request(
            "POST",
            "/v1/batchCancelOrders",
            params={"address": addr},
            json_body={"cancels": signed},
            headers=headers,
            allow_statuses=(200, 202),
        )

    def cancel_all_orders(
        self,
        *,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
        market_id: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("cancel_all_orders 需要 ArcusAuth")
        addr = self._require_address(address)
        body: Dict[str, Any] = {
            "address": addr,
            "accountIndex": int(
                account_index
                if account_index is not None
                else self.auth.account_index
            ),
        }
        if market_id is not None:
            body["marketId"] = int(market_id)
        return self._post_legacy(
            "/v1/cancelAllOrders",
            action="cancelAllOrders",
            body=body,
            params={"address": addr},
        )

    def set_leverage(
        self,
        *,
        market_id: int,
        leverage: Union[str, int, float],
        address: Optional[str] = None,
        account_index: Optional[int] = None,
    ) -> Any:
        if not self.auth:
            raise ValueError("set_leverage 需要 ArcusAuth")
        addr = self._require_address(address)
        body = {
            "address": addr,
            "accountIndex": int(
                account_index
                if account_index is not None
                else self.auth.account_index
            ),
            "marketId": int(market_id),
            "leverage": str(leverage),
        }
        return self._post_legacy(
            "/v1/setLeverage",
            action="setLeverage",
            body=body,
            params={"address": addr},
        )
