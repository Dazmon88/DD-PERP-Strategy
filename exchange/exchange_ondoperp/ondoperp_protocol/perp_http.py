"""
Ondo Perps HTTP API Client

文档: https://docs.ondoperps.xyz/llms.txt
生产: https://api.ondoperps.xyz
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

from .orders import (
    build_place_order_body,
    format_batch_cancel_ids,
    format_order_id_ref,
)
from .perps_auth import OndoPerpAuth

Network = str  # "mainnet" | "sandbox"

REST_URLS = {
    "mainnet": "https://api.ondoperps.xyz",
    # sandbox 域名以官方 Builder 指南为准；可用 base_url 覆盖
    "sandbox": "https://api.ondoperps-sandbox.xyz",
}


class OndoPerpHTTP:
    """Ondo Perps REST 客户端"""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        auth: Optional[OndoPerpAuth] = None,
        timeout: float = 15.0,
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
        self._session = requests.Session()

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
        auth_required: bool = False,
        unwrap: bool = True,
    ) -> Any:
        request_path = OndoPerpAuth.build_request_path(path, params)
        body_str = self._dump_body(json_body)

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth_required:
            if not self.auth or not (self.auth.has_api_key or self.auth.has_jwt):
                raise ValueError("该接口需要 API Key 或 JWT")
            headers = self.auth.rest_headers(
                method=method,
                request_path=request_path,
                body=body_str,
            )

        resp = self._session.request(
            method=method.upper(),
            url=self._url(request_path),
            data=body_str.encode("utf-8") if body_str else None,
            headers=headers,
            timeout=self.timeout,
        )
        if not resp.ok:
            raise ValueError(f"HTTP {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except Exception:
            return resp.text

        if not unwrap or not isinstance(data, dict):
            return data

        # GenericResponse: {success, result, error, error_code}
        if "success" in data:
            if data.get("success") is False:
                raise ValueError(
                    f"Ondo API error error_code={data.get('error_code')} "
                    f"error={data.get('error')}"
                )
            if "result" in data:
                return data["result"]
            return data
        return data

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth_required: bool = False,
    ) -> Any:
        return self._request(
            "GET", path, params=params, auth_required=auth_required
        )

    def _post(
        self,
        path: str,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth_required: bool = True,
    ) -> Any:
        return self._request(
            "POST",
            path,
            params=params,
            json_body=json_body,
            auth_required=auth_required,
        )

    def _put(
        self,
        path: str,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        auth_required: bool = True,
    ) -> Any:
        return self._request(
            "PUT",
            path,
            params=params,
            json_body=json_body,
            auth_required=auth_required,
        )

    def _delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        *,
        auth_required: bool = True,
    ) -> Any:
        return self._request(
            "DELETE",
            path,
            params=params,
            json_body=json_body,
            auth_required=auth_required,
        )

    # ------------------------------------------------------------------
    # 公共 / 工具
    # ------------------------------------------------------------------

    def hello(self) -> Any:
        return self._get("/hello", auth_required=False)

    def get_status(self) -> Any:
        return self._get("/status", auth_required=False)

    def get_markets(self, **params: Any) -> Any:
        return self._get("/v1/markets", params=params or None, auth_required=False)

    # ------------------------------------------------------------------
    # 行情
    # ------------------------------------------------------------------

    def get_contracts(self, **params: Any) -> Any:
        return self._get("/v1/perps/contracts", params=params or None)

    def get_orderbook(self, market: str, **params: Any) -> Any:
        p = {"market": market, **params}
        return self._get("/v1/perps/depth", params=p)

    def get_mark_prices(self, **params: Any) -> Any:
        return self._get("/v1/perps/mark_prices", params=params or None)

    def get_trades(self, market: str, **params: Any) -> Any:
        return self._get("/v1/perps/trades", params={"market": market, **params})

    def get_candles(self, market: str, **params: Any) -> Any:
        # Ondo 网关对 /v1/perps/candles 要求鉴权
        return self._get(
            "/v1/perps/candles",
            params={"market": market, **params},
            auth_required=True,
        )

    def get_price_history(self, symbol: str, **params: Any) -> Any:
        """
        TradingView UDF 历史 K 线（公开，无需鉴权）。

        参数: symbol / resolution / from / to（Unix 秒）
        返回: {s, t, o, h, l, c, v}
        注意: symbol 用 displayName 风格，如 BTCUSD.P（不是 BTC-USD.P）
        """
        return self._get(
            "/v1/perps/history",
            params={"symbol": symbol, **params},
            auth_required=False,
        )

    def get_funding_rates(self, **params: Any) -> Any:
        return self._get("/v1/perps/funding_rates", params=params or None)

    def get_funding_rate_history(self, market: str, **params: Any) -> Any:
        return self._get(
            "/v1/perps/funding_rate_history",
            params={"market": market, **params},
        )

    def get_open_interest(self, **params: Any) -> Any:
        return self._get("/v1/perps/open_interest", params=params or None)

    def get_volume(self, **params: Any) -> Any:
        return self._get("/v1/perps/volume", params=params or None)

    # ------------------------------------------------------------------
    # 账户 / 保证金 / 仓位
    # ------------------------------------------------------------------

    def get_account(self) -> Any:
        return self._get("/v1/account", auth_required=True)

    def get_balance(self) -> Any:
        return self._get("/v1/perps/balance", auth_required=True)

    def get_positions(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/positions", params=params or None, auth_required=True
        )

    def get_leverage(self, market: Optional[str] = None) -> Any:
        params = {"market": market} if market else None
        return self._get("/v1/perps/leverage", params=params, auth_required=True)

    def set_leverage(self, market: str, leverage: Union[str, int]) -> Any:
        return self._post(
            "/v1/perps/leverage",
            json_body={"market": market, "leverage": str(leverage)},
        )

    def get_max_order_size(self, market: str, **params: Any) -> Any:
        return self._get(
            "/v1/perps/max_order_size",
            params={"market": market, **params},
            auth_required=True,
        )

    def get_orders_summaries(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/orders_summaries",
            params=params or None,
            auth_required=True,
        )

    def get_open_order_counts(self, **params: Any) -> Any:
        return self._get(
            "/v1/counts/orders", params=params or None, auth_required=True
        )

    def get_portfolio_summary(self, **params: Any) -> Any:
        return self._get(
            "/v1/portfolio/summary", params=params or None, auth_required=True
        )

    def get_funding_fee_payments(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/funding_fees",
            params=params or None,
            auth_required=True,
        )

    def get_liquidation_history(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/liquidation_history",
            params=params or None,
            auth_required=True,
        )

    # ------------------------------------------------------------------
    # 订单
    # ------------------------------------------------------------------

    def place_order(
        self,
        *,
        market: str,
        side: str,
        size: Union[str, float, int],
        order_type: str = "limit",
        price: Optional[Union[str, float, int]] = None,
        client_order_id: Optional[str] = None,
        time_in_force: Optional[str] = None,
        post_only: Optional[bool] = None,
        reduce_only: Optional[bool] = None,
        quote_size: Optional[Union[str, float, int]] = None,
        take_profit: Optional[Dict[str, Any]] = None,
        stop_loss: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> Any:
        body = build_place_order_body(
            market=market,
            side=side,
            size=size,
            order_type=order_type,
            price=price,
            quote_size=quote_size,
            client_order_id=client_order_id,
            time_in_force=time_in_force,
            post_only=post_only,
            reduce_only=reduce_only,
            take_profit=take_profit,
            stop_loss=stop_loss,
            extra=extra or None,
        )
        return self._post("/v1/perps/orders", json_body=body)

    def place_orders_batch(self, orders: Sequence[Dict[str, Any]]) -> Any:
        """批量下单；orders 为 AddOrderReq 列表（1–20）。"""
        return self._post(
            "/v1/perps/orders/batch",
            json_body={"orders": list(orders)},
        )

    def get_orders(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/orders", params=params or None, auth_required=True
        )

    def get_order(
        self,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Any:
        ref = format_order_id_ref(order_id=order_id, client_order_id=client_order_id)
        return self._get(f"/v1/perps/orders/{ref}", auth_required=True)

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Any:
        ref = format_order_id_ref(order_id=order_id, client_order_id=client_order_id)
        return self._delete(f"/v1/perps/orders/{ref}")

    def cancel_orders_batch(
        self,
        order_ids: Optional[Sequence[Union[str, int]]] = None,
        client_order_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        ids = format_batch_cancel_ids(order_ids, client_order_ids)
        return self._delete("/v1/perps/orders/batch", params={"orderIDs": ids})

    def cancel_all_orders(self, market: Optional[str] = None) -> Any:
        params = {"market": market} if market else None
        return self._delete("/v1/perps/orders", params=params)

    def get_fills(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/fills", params=params or None, auth_required=True
        )

    def get_fills_by_order(self, order_id: str) -> Any:
        ref = format_order_id_ref(order_id=order_id)
        return self._get(f"/v1/perps/orders/{ref}/fills", auth_required=True)

    # ------------------------------------------------------------------
    # 止损 / TWAP（薄封装）
    # ------------------------------------------------------------------

    def get_stop_orders(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/stop_order", params=params or None, auth_required=True
        )

    def set_stop_order(self, body: Dict[str, Any]) -> Any:
        return self._post("/v1/perps/stop_order", json_body=body)

    def remove_stop_order(self, **params: Any) -> Any:
        return self._delete("/v1/perps/stop_order", params=params or None)

    def create_twap_order(self, body: Dict[str, Any]) -> Any:
        return self._post("/v1/perps/twap/order", json_body=body)

    def get_twap_order(self, order_id: str) -> Any:
        return self._get(f"/v1/perps/twap/order/{order_id}", auth_required=True)

    def cancel_twap_order(self, order_id: str) -> Any:
        return self._delete(f"/v1/perps/twap/order/{order_id}")

    def get_running_twap_orders(self, **params: Any) -> Any:
        return self._get(
            "/v1/perps/twap/orders/running",
            params=params or None,
            auth_required=True,
        )

    # ------------------------------------------------------------------
    # Auth helpers（SIWE）
    # ------------------------------------------------------------------

    def get_siwe_login_challenge(self, body: Dict[str, Any]) -> Any:
        return self._post(
            "/v1/auth/erc-4361/login/get_challenge",
            json_body=body,
            auth_required=False,
        )

    def complete_siwe_login(self, body: Dict[str, Any]) -> Any:
        return self._post(
            "/v1/auth/erc-4361/login/complete_challenge",
            json_body=body,
            auth_required=False,
        )

    def invalidate_jwt(self) -> Any:
        return self._get("/v1/auth/invalidate_jwt", auth_required=True)
