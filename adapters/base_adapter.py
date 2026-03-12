"""
Base Adapter for Perpetual Exchange Integration

This module provides a base adapter interface for integrating different
perpetual futures exchanges. All exchange-specific adapters should inherit
from BasePerpAdapter and implement the required methods.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from decimal import Decimal
from enum import Enum


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """订单类型"""
    LIMIT = "limit"
    MARKET = "market"


class TimeInForce(Enum):
    """订单有效期"""
    GTC = "gtc"  # Good Till Cancel
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Position:
    """持仓信息"""
    def __init__(
        self,
        symbol: str,
        size: Decimal,
        side: str,  # "long" or "short"
        entry_price: Decimal,
        mark_price: Decimal,
        unrealized_pnl: Decimal,
        leverage: Optional[int] = None,
        margin_mode: Optional[str] = None,
    ):
        self.symbol = symbol
        self.size = size
        self.side = side
        self.entry_price = entry_price
        self.mark_price = mark_price
        self.unrealized_pnl = unrealized_pnl
        self.leverage = leverage
        self.margin_mode = margin_mode
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "size": str(self.size),
            "side": self.side,
            "entry_price": str(self.entry_price),
            "mark_price": str(self.mark_price),
            "unrealized_pnl": str(self.unrealized_pnl),
            "leverage": self.leverage,
            "margin_mode": self.margin_mode,
        }


class Balance:
    """账户余额信息"""
    def __init__(
        self,
        total_balance: Decimal,
        available_balance: Decimal,
        equity: Decimal,
        unrealized_pnl: Decimal,
        margin_used: Optional[Decimal] = None,
        margin_available: Optional[Decimal] = None,
        position_value: Optional[Decimal] = None,
    ):
        self.total_balance = total_balance
        self.available_balance = available_balance
        self.equity = equity
        self.unrealized_pnl = unrealized_pnl
        self.margin_used = margin_used
        self.margin_available = margin_available
        self.position_value = position_value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_balance": str(self.total_balance),
            "available_balance": str(self.available_balance),
            "equity": str(self.equity),
            "unrealized_pnl": str(self.unrealized_pnl),
            "margin_used": str(self.margin_used) if self.margin_used else None,
            "margin_available": str(self.margin_available) if self.margin_available else None,
            "position_value": str(self.position_value) if self.position_value is not None else None,
        }


class Order:
    """订单信息"""
    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        filled_quantity: Decimal = Decimal("0"),
        status: str = "pending",
        time_in_force: Optional[str] = None,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        created_at: Optional[int] = None,
        updated_at: Optional[int] = None,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.filled_quantity = filled_quantity
        self.status = status
        self.time_in_force = time_in_force
        self.reduce_only = reduce_only
        self.client_order_id = client_order_id
        self.created_at = created_at
        self.updated_at = updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "filled_quantity": str(self.filled_quantity),
            "status": self.status,
            "time_in_force": self.time_in_force,
            "reduce_only": self.reduce_only,
            "client_order_id": self.client_order_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class BasePerpAdapter(ABC):
    """
    永续合约交易所适配器基类
    
    所有交易所适配器都应该继承此类并实现所有抽象方法。
    这样可以确保不同交易所的接口统一，方便策略编写。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化适配器
        
        Args:
            config: 交易所配置字典，包含 API key、secret、base_url 等
        """
        self.config = config
        self.exchange_name = config.get("exchange_name", "unknown")
    
    @abstractmethod
    def connect(self) -> bool:
        """
        连接到交易所并完成认证
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Balance:
        """
        查询账户余额
        
        Returns:
            Balance: 账户余额信息
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        查询持仓信息
        
        Args:
            symbol: 交易对符号，如果为 None 则返回所有持仓
            
        Returns:
            List[Position]: 持仓信息列表
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    @abstractmethod
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
        **kwargs
    ) -> Order:
        """
        下单
        
        Args:
            symbol: 交易对符号，如 "BTC-USD"
            side: 订单方向，"buy"/"sell" 或 "long"/"short"
            order_type: 订单类型，"limit" 或 "market"
            quantity: 订单数量
            price: 订单价格（限价单必填）
            time_in_force: 订单有效期，"gtc"/"ioc"/"fok"
            reduce_only: 是否只减仓
            client_order_id: 客户端订单ID
            **kwargs: 其他交易所特定参数
            
        Returns:
            Order: 订单信息
            
        Raises:
            Exception: 下单失败时抛出异常
        """
        pass
    
    @abstractmethod
    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        """
        撤单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号（某些交易所需要）
            client_order_id: 客户端订单ID
            
        Returns:
            bool: 撤单是否成功
            
        Raises:
            Exception: 撤单失败时抛出异常
        """
        pass
    
    @abstractmethod
    def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
    ) -> bool:
        """
        撤销所有订单
        
        Args:
            symbol: 交易对符号，如果为 None 则撤销所有交易对的订单
            
        Returns:
            bool: 撤单是否成功
            
        Raises:
            Exception: 撤单失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        """
        查询订单状态
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号（某些交易所需要）
            client_order_id: 客户端订单ID
            
        Returns:
            Optional[Order]: 订单信息，如果订单不存在则返回 None
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_open_orders(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """
        查询所有未成交订单
        
        Args:
            symbol: 交易对符号，如果为 None 则返回所有交易对的订单
            
        Returns:
            List[Order]: 订单列表
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对的最新价格信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            Dict[str, Any]: 包含最新价、买一价、卖一价等信息
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    @abstractmethod
    def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """
        获取订单簿
        
        Args:
            symbol: 交易对符号
            depth: 深度，默认 20
            
        Returns:
            Dict[str, Any]: 包含 bids 和 asks 的订单簿数据
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        pass
    
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        time_in_force: str = "gtc",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs
    ) -> Order:
        """
        下限价单（便捷方法）
        
        Args:
            symbol: 交易对符号
            side: 订单方向
            quantity: 订单数量
            price: 订单价格
            time_in_force: 订单有效期
            reduce_only: 是否只减仓
            client_order_id: 客户端订单ID
            **kwargs: 其他参数
            
        Returns:
            Order: 订单信息
        """
        return self.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_order_id=client_order_id,
            **kwargs
        )
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs
    ) -> Order:
        """
        下市价单（便捷方法）
        
        Args:
            symbol: 交易对符号
            side: 订单方向
            quantity: 订单数量
            reduce_only: 是否只减仓
            client_order_id: 客户端订单ID
            **kwargs: 其他参数
            
        Returns:
            Order: 订单信息
        """
        return self.place_order(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=None,
            time_in_force="ioc",
            reduce_only=reduce_only,
            client_order_id=client_order_id,
            **kwargs
        )
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取单个交易对的持仓（便捷方法）
        
        Args:
            symbol: 交易对符号
            
        Returns:
            Optional[Position]: 持仓信息，如果没有持仓则返回 None
        """
        positions = self.get_positions(symbol=symbol)
        if positions:
            return positions[0]
        return None
    
    def close_position(
        self,
        symbol: str,
        order_type: str = "market",
        price: Optional[Decimal] = None,
    ) -> Optional[Order]:
        """
        平仓（便捷方法）
        
        Args:
            symbol: 交易对符号
            order_type: 订单类型，"limit" 或 "market"
            price: 限价单价格（限价单必填）
            
        Returns:
            Optional[Order]: 订单信息，如果没有持仓则返回 None
        """
        position = self.get_position(symbol)
        if not position or position.size == Decimal("0"):
            return None
        
        # 确定平仓方向（与持仓相反）
        if position.side in ["long", "buy"]:
            close_side = "sell"
        else:
            close_side = "buy"
        
        if order_type == "market":
            return self.place_market_order(
                symbol=symbol,
                side=close_side,
                quantity=abs(position.size),
                reduce_only=True,
            )
        else:
            if price is None:
                raise ValueError("限价单必须指定价格")
            return self.place_limit_order(
                symbol=symbol,
                side=close_side,
                quantity=abs(position.size),
                price=price,
                reduce_only=True,
            )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<{self.__class__.__name__}(exchange={self.exchange_name})>"
