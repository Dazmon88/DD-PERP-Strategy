"""
Ondo Perps Authentication Module

REST：API Key HMAC（ONDO-KEY-ID / ONDO-TIMESTAMP / ONDO-SIGN）
WSS：API Key login 或 JWT login
可选：Bearer JWT（SIWE 登录后）
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlencode

Network = Literal["mainnet", "sandbox"]

WS_LOGIN_PREFIX = "ondo_perps_ws_login"


class OndoPerpAuth:
    """
    Ondo Perps 鉴权客户端。

    机器人场景优先使用 API Key；Builder / 人机场景可设置 jwt。
    """

    def __init__(
        self,
        *,
        key_id: Optional[str] = None,
        api_secret: Optional[str] = None,
        jwt: Optional[str] = None,
        network: Network = "mainnet",
    ):
        self.key_id = (key_id or "").strip() or None
        self.api_secret = (api_secret or "").strip() or None
        self.jwt = (jwt or "").strip() or None
        self.network: Network = network

    @property
    def has_api_key(self) -> bool:
        return bool(self.key_id and self.api_secret)

    @property
    def has_jwt(self) -> bool:
        return bool(self.jwt)

    def set_jwt(self, jwt: str) -> None:
        self.jwt = (jwt or "").strip() or None

    def clear_jwt(self) -> None:
        self.jwt = None

    @staticmethod
    def timestamp_ms() -> str:
        return str(int(time.time() * 1000))

    def sign_rest(
        self,
        *,
        method: str,
        request_path: str,
        body: str = "",
        timestamp: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        生成 REST 鉴权头。

        request_path: 含 query 的完整 path（不含 host），如
          /v1/perps/orders?market=AAPL-USD.P&limit=100
        body: 原始请求体字符串；GET 通常为空字符串。
        """
        if not self.has_api_key:
            raise ValueError("REST HMAC 签名需要 key_id 与 api_secret")

        ts = timestamp or self.timestamp_ms()
        method_u = method.upper()
        payload = f"{ts}{method_u}{request_path}{body}"
        sig = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "ONDO-KEY-ID": self.key_id or "",
            "ONDO-TIMESTAMP": ts,
            "ONDO-SIGN": sig,
        }

    def rest_headers(
        self,
        *,
        method: str,
        request_path: str,
        body: str = "",
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        组装 REST 请求头。

        优先 API Key HMAC；若无 Key 但有 JWT，则使用 Bearer。
        """
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.has_api_key:
            headers.update(
                self.sign_rest(method=method, request_path=request_path, body=body)
            )
        elif self.has_jwt:
            headers["Authorization"] = f"Bearer {self.jwt}"
        if extra:
            headers.update(extra)
        return headers

    def ws_login_args_api_key(self, timestamp: Optional[str] = None) -> Dict[str, str]:
        """
        WSS login args（API Key）。

        官方 OpenAPI：HMAC-SHA256(secret, \"ondo_perps_ws_login\" + time)
        """
        if not self.has_api_key:
            raise ValueError("WSS API Key login 需要 key_id 与 api_secret")
        ts = timestamp or self.timestamp_ms()
        msg = f"{WS_LOGIN_PREFIX}{ts}"
        sig = hmac.new(
            self.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "key": self.key_id or "",
            "time": ts,
            "sign": sig,
        }

    def ws_login_message(
        self,
        *,
        use_jwt: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """构造 WSS login 报文。"""
        prefer_jwt = self.has_jwt if use_jwt is None else use_jwt
        if prefer_jwt and self.has_jwt:
            return {"op": "login", "args": {"token": self.jwt}}
        if self.has_api_key:
            return {"op": "login", "args": self.ws_login_args_api_key()}
        raise ValueError("WSS login 需要 jwt 或 api key")

    @staticmethod
    def build_request_path(path: str, params: Optional[Dict[str, Any]] = None) -> str:
        """path + 稳定 query string（按 key 排序，便于签名可复现）。"""
        if not path.startswith("/"):
            path = "/" + path
        if not params:
            return path
        clean = {k: v for k, v in params.items() if v is not None}
        if not clean:
            return path
        # 与常见网关一致：按 key 排序；值为 list 时展开
        items = []
        for k in sorted(clean.keys()):
            v = clean[k]
            if isinstance(v, (list, tuple)):
                for item in v:
                    items.append((k, item))
            else:
                items.append((k, v))
        qs = urlencode(items, doseq=True)
        return f"{path}?{qs}" if qs else path
