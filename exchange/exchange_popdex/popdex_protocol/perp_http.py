"""
PopDEX Perps HTTP API Client
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import requests

Network = str  # "mainnet" | "testnet"

REST_URLS = {
    "mainnet": "https://api.popdex.xyz",
    "testnet": "https://testnet-api.popdex.xyz",
}


class PopDEXPerpHTTP:
    """PopDEX Perps HTTP API Client"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        network: str = "mainnet",
        timeout: float = 10.0,
    ):
        """
        Args:
            base_url: REST 基础 URL；默认按 network 选择官方域名
            network: mainnet / testnet
            timeout: 请求超时（秒）
        """
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            if network not in REST_URLS:
                raise ValueError(f"未知 network: {network}，可选: {list(REST_URLS)}")
            self.base_url = REST_URLS[network]
        self.network = network
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        unwrap: bool = True,
    ) -> Any:
        resp = self._session.request(
            method=method.upper(),
            url=self._url(path),
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout,
        )
        if not resp.ok:
            raise ValueError(f"HTTP {resp.status_code}: {resp.text}")

        # eth_sendRawTransaction 等可能返回纯 JSON-RPC
        try:
            data = resp.json()
        except Exception:
            return resp.text

        if unwrap and isinstance(data, dict) and "code" in data:
            code = str(data.get("code", ""))
            if code not in ("200", "0", ""):
                raise ValueError(
                    f"PopDEX API error code={code} msg={data.get('msg')}"
                )
            # 多数接口数据在 data 字段；保留 cursor/total 等分页字段
            if "data" in data:
                payload = data["data"]
                # 附带分页元数据
                if any(k in data for k in ("cursor", "total", "limit", "updatedTime", "updatedBlock")):
                    if isinstance(payload, dict):
                        meta = {
                            k: data[k]
                            for k in (
                                "cursor",
                                "total",
                                "limit",
                                "updatedTime",
                                "updatedBlock",
                                "code",
                                "msg",
                            )
                            if k in data
                        }
                        return {"data": payload, **meta} if meta else payload
                    return {
                        "data": payload,
                        **{
                            k: data[k]
                            for k in ("cursor", "total", "limit", "updatedTime", "updatedBlock")
                            if k in data
                        },
                    }
                return payload
            return data
        return data

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        unwrap: bool = True,
    ) -> Any:
        # 过滤 None
        clean = None
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=clean, unwrap=unwrap)

    def _post(
        self,
        path: str,
        json_body: Any,
        unwrap: bool = True,
    ) -> Any:
        return self._request("POST", path, json_body=json_body, unwrap=unwrap)

    # ------------------------------------------------------------------
    # 公共：平台 / 配置
    # ------------------------------------------------------------------

    def get_server_time(self) -> Dict[str, Any]:
        """GET /api/v1/public/time"""
        return self._get("/api/v1/public/time")

    def get_symbols(self) -> Any:
        """获取全部币对配置 GET /api/v1/config/symbols"""
        return self._get("/api/v1/config/symbols")

    def get_symbol(self, **params: Any) -> Any:
        """获取单个币对配置 GET /api/v1/config/symbol"""
        return self._get("/api/v1/config/symbol", params=params)

    def get_tokens(self) -> Any:
        """获取全部币种配置 GET /api/v1/config/tokens"""
        return self._get("/api/v1/config/tokens")

    def get_token(self, **params: Any) -> Any:
        """获取单个币种配置 GET /api/v1/config/token"""
        return self._get("/api/v1/config/token", params=params)

    def get_fee_rate(self, **params: Any) -> Any:
        """GET /api/v1/public/fee-rate"""
        return self._get("/api/v1/public/fee-rate", params=params)

    def get_futures_tier(self, **params: Any) -> Any:
        """GET /api/v1/public/futures-tier"""
        return self._get("/api/v1/public/futures-tier", params=params)

    def get_insurance_fund(self, **params: Any) -> Any:
        """GET /api/v1/public/insurance-fund"""
        return self._get("/api/v1/public/insurance-fund", params=params)

    # ------------------------------------------------------------------
    # 公共：行情
    # ------------------------------------------------------------------

    def get_tickers(
        self,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[Union[str, int]] = None,
    ) -> Any:
        """GET /api/v1/public/market/tickers"""
        return self._get(
            "/api/v1/public/market/tickers",
            params={
                "category": category,
                "symbol": symbol,
                "cursor": cursor,
                "limit": limit,
            },
        )

    def get_orderbook(
        self,
        category: str,
        symbol: str,
        levels: Optional[Union[str, int]] = None,
    ) -> Any:
        """GET /api/v1/public/market/orderbook"""
        return self._get(
            "/api/v1/public/market/orderbook",
            params={"category": category, "symbol": symbol, "levels": levels},
        )

    def get_merge_depth(
        self,
        category: str,
        symbol: str,
        **params: Any,
    ) -> Any:
        """GET /api/v1/public/market/merge-depth"""
        return self._get(
            "/api/v1/public/market/merge-depth",
            params={"category": category, "symbol": symbol, **params},
        )

    def get_recent_fills(
        self,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
        **params: Any,
    ) -> Any:
        """GET /api/v1/public/market/fills"""
        return self._get(
            "/api/v1/public/market/fills",
            params={"category": category, "symbol": symbol, **params},
        )

    def get_candles(
        self,
        category: str,
        symbol: str,
        interval: Optional[str] = None,
        **params: Any,
    ) -> Any:
        """GET /api/v1/public/market/candles"""
        return self._get(
            "/api/v1/public/market/candles",
            params={
                "category": category,
                "symbol": symbol,
                "interval": interval,
                **params,
            },
        )

    def get_history_candles(self, **params: Any) -> Any:
        """GET /api/v1/market/history/candles"""
        return self._get("/api/v1/market/history/candles", params=params)

    def get_funding_rate(self, **params: Any) -> Any:
        """GET /api/v1/market/funding-rate"""
        return self._get("/api/v1/market/funding-rate", params=params)

    def get_history_funding_rate(self, **params: Any) -> Any:
        """GET /api/v1/market/history/funding-rate"""
        return self._get("/api/v1/market/history/funding-rate", params=params)

    def get_open_interest(self, **params: Any) -> Any:
        """GET /api/v1/public/market/open-interest"""
        return self._get("/api/v1/public/market/open-interest", params=params)

    def get_oi_limit(self, **params: Any) -> Any:
        """GET /api/v1/public/market/oi-limit"""
        return self._get("/api/v1/public/market/oi-limit", params=params)

    def get_exchange_rates(self, **params: Any) -> Any:
        """GET /api/v1/public/market/exchange-rates"""
        return self._get("/api/v1/public/market/exchange-rates", params=params)

    # ------------------------------------------------------------------
    # 账户（路径含 walletId；私有读）
    # ------------------------------------------------------------------

    def query_overview(self, wallet_id: str) -> Any:
        """账户概览 GET /api/v1/account/{walletId}/overview"""
        return self._get(f"/api/v1/account/{wallet_id}/overview")

    def query_settings(self, wallet_id: str) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/settings")

    def query_token_balance(self, wallet_id: str, token: str) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/token/{token}/balance")

    def query_positions(
        self,
        wallet_id: str,
        position_side: Optional[str] = None,
    ) -> Any:
        """当前仓位 GET /api/v1/account/{walletId}/positions"""
        return self._get(
            f"/api/v1/account/{wallet_id}/positions",
            params={"positionSide": position_side},
        )

    def query_open_orders(self, wallet_id: str, **params: Any) -> Any:
        """当前委托 GET /api/v1/account/{walletId}/orders"""
        return self._get(f"/api/v1/account/{wallet_id}/orders", params=params)

    def query_order(self, wallet_id: str, order_id: str) -> Any:
        """单笔订单 GET /api/v1/account/{walletId}/order/{orderId}"""
        return self._get(f"/api/v1/account/{wallet_id}/order/{order_id}")

    def query_fills(self, wallet_id: str, **params: Any) -> Any:
        """成交明细 GET /api/v1/account/{walletId}/trade/fills"""
        return self._get(f"/api/v1/account/{wallet_id}/trade/fills", params=params)

    def query_history_orders(self, wallet_id: str, **params: Any) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/history/orders", params=params)

    def query_history_positions(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/history/positions", params=params
        )

    def query_history_funding(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/history/funding-rate", params=params
        )

    def query_history_liquidation(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/history/liquidation", params=params
        )

    def query_financial_records(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/financial-records", params=params
        )

    def query_max_open_available(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/max-open-available", params=params
        )

    def query_max_transferable(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/max-transferable", params=params
        )

    def query_position_mode(self, wallet_id: str) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/config/position-mode")

    def query_futures_leverage(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/config/futures-leverage", params=params
        )

    def query_token_leverage(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/config/token-leverage", params=params
        )

    def query_plan_orders(self, wallet_id: str, **params: Any) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/plan-orders", params=params)

    def query_plan_orders_history(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/plan-orders/history", params=params
        )

    def query_agents(self, wallet_id: str) -> Any:
        """查询账户下所有 Agent GET /api/v1/account/{walletId}/agents"""
        return self._get(f"/api/v1/account/{wallet_id}/agents")

    def query_agent(self, agent_wallet_id: str) -> Any:
        """查询单个 Agent GET /api/v1/agent/{walletId}"""
        return self._get(f"/api/v1/agent/{agent_wallet_id}")

    def query_subaccounts(self, wallet_id: str) -> Any:
        return self._get(f"/api/v1/account/{wallet_id}/subaccounts")

    def query_subaccount(self, wallet_id: str) -> Any:
        return self._get(f"/api/v1/subaccount/{wallet_id}")

    def query_adl_rank(self, **params: Any) -> Any:
        """GET /api/v1/position/adl-rank"""
        return self._get("/api/v1/position/adl-rank", params=params)

    def query_open_interest_limit(self, wallet_id: str, **params: Any) -> Any:
        return self._get(
            f"/api/v1/account/{wallet_id}/open-interest-limit", params=params
        )

    # ------------------------------------------------------------------
    # Web3 RPC（查询 + 广播交易）
    # ------------------------------------------------------------------

    def web3_rpc(
        self,
        method: str,
        params: Optional[List[Any]] = None,
        request_id: str = "1",
    ) -> Any:
        """
        POST /api/v1/web3/rpc

        标准 JSON-RPC 2.0。查询方法权重 1；eth_sendRawTransaction 权重 10。
        """
        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": request_id,
        }
        result = self._post("/api/v1/web3/rpc", json_body=body, unwrap=False)
        if isinstance(result, dict) and result.get("error"):
            raise ValueError(f"Web3 RPC error: {result['error']}")
        return result

    def eth_call(self, *args: Any, **kwargs: Any) -> Any:
        """便捷封装 eth_call"""
        params = kwargs.get("params")
        if params is None:
            params = list(args)
        return self.web3_rpc("eth_call", params=params)

    def eth_block_number(self) -> Any:
        return self.web3_rpc("eth_blockNumber", params=[])

    def send_raw_transaction(self, raw_tx_hex: str, request_id: str = "1") -> Any:
        """广播已签名交易 eth_sendRawTransaction"""
        if not raw_tx_hex.startswith("0x"):
            raw_tx_hex = "0x" + raw_tx_hex
        return self.web3_rpc(
            "eth_sendRawTransaction",
            params=[raw_tx_hex],
            request_id=request_id,
        )

    def get_transaction_receipt(self, tx_hash: str) -> Any:
        return self.web3_rpc("eth_getTransactionReceipt", params=[tx_hash])

    def get_transaction_failure(self, tx_hash: str) -> Any:
        """扩展方法 core_getTransactionFailure"""
        return self.web3_rpc("core_getTransactionFailure", params=[tx_hash])

    def place_order_onchain(
        self,
        *,
        wallet_id: str,
        agent_private_key: str,
        symbol_id: int,
        price: Any,
        qty: Any,
        side: str = "buy",
        order_type: str = "limit",
        time_in_force: str = "gtc",
        category: str = "Futures",
        reduce_only: bool = False,
        position_side: str = "none",
        slippage: Any = 0,
        client_order_id: Optional[str] = None,
        network: Optional[str] = None,
        gas: int = 1_000_000,
    ) -> Dict[str, Any]:
        """
        通过 Order 预编译合约 placeOrder 挂单，并 eth_sendRawTransaction 广播。

        Args:
            wallet_id: 主账户/子账户地址（order.account）
            agent_private_key: 已授权的 Trade Agent 私钥
            symbol_id: 交易对 ID（如 BTCUSDT=20000）
        """
        from .orders import build_agent_tx, encode_place_order_calldata

        encoded = encode_place_order_calldata(
            account=wallet_id,
            symbol_id=symbol_id,
            price=price,
            qty=qty,
            side=side,
            order_type=order_type,
            time_in_force=time_in_force,
            category=category,
            reduce_only=reduce_only,
            position_side=position_side,
            slippage=slippage,
            client_order_id=client_order_id,
        )
        signed = build_agent_tx(
            private_key=agent_private_key,
            to=encoded["to"],
            data=encoded["data"],
            network=(network or self.network),  # type: ignore[arg-type]
            gas=gas,
        )
        rpc_result = self.send_raw_transaction(signed["raw_transaction"])
        return {
            "encoded": encoded,
            "signed": {
                "from": signed["from"],
                "nonce": signed["nonce"],
                "hash": signed["hash"],
            },
            "rpc": rpc_result,
        }

    def cancel_order_onchain(
        self,
        *,
        wallet_id: str,
        agent_private_key: str,
        order_id: Optional[Union[str, int]] = None,
        client_order_id: Optional[str] = None,
        network: Optional[str] = None,
        gas: int = 1_000_000,
    ) -> Dict[str, Any]:
        """通过 Order 预编译 cancelOrder 撤单并广播。"""
        from .orders import build_agent_tx, encode_cancel_order_calldata

        encoded = encode_cancel_order_calldata(
            account=wallet_id,
            order_id=order_id,
            client_order_id=client_order_id,
        )
        signed = build_agent_tx(
            private_key=agent_private_key,
            to=encoded["to"],
            data=encoded["data"],
            network=(network or self.network),  # type: ignore[arg-type]
            gas=gas,
        )
        rpc_result = self.send_raw_transaction(signed["raw_transaction"])
        return {
            "encoded": encoded,
            "signed": {
                "from": signed["from"],
                "nonce": signed["nonce"],
                "hash": signed["hash"],
            },
            "rpc": rpc_result,
        }
