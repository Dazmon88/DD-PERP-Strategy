"""
Adapter Factory

This module provides a factory function to create exchange adapters based on configuration.
"""
from typing import Dict, Any, Type
from adapters.base_adapter import BasePerpAdapter
from adapters.standx_adapter import StandXAdapter
from adapters.grvt_adapter import GrvtAdapter
from adapters.lighter_adapter import LighterAdapter
from adapters.hype_adapter import HypeAdapter
from adapters.popdex_adapter import PopDEXAdapter
from adapters.ondo_adapter import OndoAdapter
from adapters.arcus_adapter import ArcusAdapter

# 注册所有可用的适配器
_ADAPTER_REGISTRY: Dict[str, Type[BasePerpAdapter]] = {
    "standx": StandXAdapter,
    "grvt": GrvtAdapter,
    "lighter": LighterAdapter,
    "hype": HypeAdapter,
    "popdex": PopDEXAdapter,
    "ondo": OndoAdapter,
    "ondoperp": OndoAdapter,
    "ondoperps": OndoAdapter,
    "arcus": ArcusAdapter,
}


def create_adapter(config: Dict[str, Any]) -> BasePerpAdapter:
    """
    根据配置创建适配器实例
    
    Args:
        config: 配置字典，必须包含 "exchange_name" 字段
        
    Returns:
        BasePerpAdapter: 适配器实例
        
    Raises:
        ValueError: 如果交易所名称不支持或配置无效
        
    Example:
        >>> config = {
        ...     "exchange_name": "standx",
        ...     "private_key": "0x...",
        ...     "chain": "bsc"
        ... }
        >>> adapter = create_adapter(config)
        >>> adapter.connect()
    """
    exchange_name = config.get("exchange_name")
    
    if not exchange_name:
        raise ValueError("配置中必须包含 'exchange_name' 字段")
    
    exchange_name = exchange_name.lower()
    
    if exchange_name not in _ADAPTER_REGISTRY:
        available = ", ".join(_ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"不支持的交易所: {exchange_name}. "
            f"支持的交易所: {available}"
        )
    
    adapter_class = _ADAPTER_REGISTRY[exchange_name]
    
    try:
        return adapter_class(config)
    except Exception as e:
        raise ValueError(f"创建适配器失败: {e}")


def register_adapter(exchange_name: str, adapter_class: Type[BasePerpAdapter]):
    """
    注册新的适配器类
    
    Args:
        exchange_name: 交易所名称（小写）
        adapter_class: 适配器类，必须继承自 BasePerpAdapter
        
    Example:
        >>> from adapters.base_adapter import BasePerpAdapter
        >>> class MyExchangeAdapter(BasePerpAdapter):
        ...     pass
        >>> register_adapter("myexchange", MyExchangeAdapter)
    """
    if not issubclass(adapter_class, BasePerpAdapter):
        raise ValueError(f"适配器类必须继承自 BasePerpAdapter")
    
    _ADAPTER_REGISTRY[exchange_name.lower()] = adapter_class


def get_available_exchanges() -> list:
    """
    获取所有可用的交易所列表
    
    Returns:
        list: 交易所名称列表
    """
    return list(_ADAPTER_REGISTRY.keys())
