"""Lighter 部署端点配置（API / WS / L2 签名 chain_id）。

官方 Python SDK 新版本同名模块。Robinhood 实例与 zkLighter 共用 API 形状，
但 L2 签名 domain（chain_id）不同，不能靠 URL 里是否含 mainnet 推断。

文档: https://apidocs.rh.lighter.xyz/
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse


def normalize_base_url(url: str) -> str:
    return (url or "").rstrip("/")


@dataclass(frozen=True)
class EndpointProfile:
    name: str
    api_url: str
    ws_url: str
    chain_id: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_url", normalize_base_url(self.api_url))
        object.__setattr__(self, "ws_url", normalize_base_url(self.ws_url))


MAINNET = EndpointProfile(
    name="mainnet",
    api_url="https://mainnet.zklighter.elliot.ai",
    ws_url="wss://mainnet.zklighter.elliot.ai/stream",
    chain_id=304,
)

TESTNET = EndpointProfile(
    name="testnet",
    api_url="https://testnet.zklighter.elliot.ai",
    ws_url="wss://testnet.zklighter.elliot.ai/stream",
    chain_id=300,
)

ROBINHOOD = EndpointProfile(
    name="robinhood",
    api_url="https://api.rh.lighter.xyz",
    ws_url="wss://api.rh.lighter.xyz/stream",
    chain_id=466324,
)

ROBINHOOD_TESTNET = EndpointProfile(
    name="robinhood_testnet",
    api_url="https://api.rh-testnet.lighter.xyz",
    ws_url="wss://api.rh-testnet.lighter.xyz/stream",
    chain_id=300,
)

DEFAULT_ENDPOINT_PROFILE = MAINNET

ENDPOINT_PROFILES: Dict[str, EndpointProfile] = {
    MAINNET.name: MAINNET,
    TESTNET.name: TESTNET,
    ROBINHOOD.name: ROBINHOOD,
    ROBINHOOD_TESTNET.name: ROBINHOOD_TESTNET,
    # 常用别名
    "rh": ROBINHOOD,
    "rh_lighter": ROBINHOOD,
    "rhlighter": ROBINHOOD,
    "lighter_rh": ROBINHOOD,
    "robinhood_lighter": ROBINHOOD,
    "rh-testnet": ROBINHOOD_TESTNET,
    "rh_testnet": ROBINHOOD_TESTNET,
}


def get_endpoint_profile(name: str) -> EndpointProfile:
    key = (name or "").strip().lower()
    try:
        return ENDPOINT_PROFILES[key]
    except KeyError as exc:
        raise ValueError(
            f"未知 Lighter network: {name!r}，可选: {sorted(ENDPOINT_PROFILES)}"
        ) from exc


def resolve_profile_from_url(url: str) -> Optional[EndpointProfile]:
    """根据 host 匹配已知 profile；无法识别则返回 None。"""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        raw = (url or "").lower()
        if "rh-testnet.lighter.xyz" in raw or "api.rh-testnet" in raw:
            return ROBINHOOD_TESTNET
        if "rh.lighter.xyz" in raw or "api.rh.lighter" in raw:
            return ROBINHOOD
        if "testnet.zklighter" in raw:
            return TESTNET
        if "mainnet.zklighter" in raw or "zklighter.elliot" in raw:
            return MAINNET
        return None

    if "rh-testnet" in host:
        return ROBINHOOD_TESTNET
    if host.endswith("rh.lighter.xyz") or host == "api.rh.lighter.xyz":
        return ROBINHOOD
    if "testnet.zklighter" in host:
        return TESTNET
    if "mainnet.zklighter" in host or "zklighter.elliot" in host:
        return MAINNET
    return None


def resolve_chain_id(*, url: str, chain_id: Optional[int] = None) -> int:
    """解析 L2 签名 chain_id。显式传入优先，其次按 URL host，最后兼容旧启发式。"""
    if chain_id is not None:
        return int(chain_id)
    profile = resolve_profile_from_url(url)
    if profile is not None:
        return profile.chain_id
    # 旧 SDK 启发式：URL 含 mainnet → 304，否则 300（对 RH 会误判，故仅作兜底）
    return 304 if "mainnet" in (url or "").lower() else 300
