"""
Ondo Perps 账户辅助（SIWE / JWT 会话）

机器人通常用 API Key，无需本模块。
Builder / 人机集成可走 SIWE → JWT。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .perp_http import OndoPerpHTTP
from .perps_auth import OndoPerpAuth


def siwe_login(
    http: OndoPerpHTTP,
    *,
    challenge_request: Dict[str, Any],
    signed_challenge: Dict[str, Any],
    auth: Optional[OndoPerpAuth] = None,
) -> Dict[str, Any]:
    """
    完成 SIWE 登录并可选写入 auth.jwt。

    具体 challenge_request / signed_challenge 字段以官方
    get-siwe-login-challenge / complete-siwe-login 为准。
    """
    # 若调用方尚未拿到 challenge，可先请求
    if "challenge" not in signed_challenge and challenge_request:
        challenge = http.get_siwe_login_challenge(challenge_request)
        # 调用方仍需对 challenge 签名；此处仅透传
        return {"challenge": challenge}

    result = http.complete_siwe_login(signed_challenge)
    token = None
    if isinstance(result, dict):
        token = result.get("token") or result.get("jwt") or result.get("accessToken")
        if not token and isinstance(result.get("result"), dict):
            inner = result["result"]
            token = inner.get("token") or inner.get("jwt")
    if token and auth is not None:
        auth.set_jwt(str(token))
    return result if isinstance(result, dict) else {"result": result}
