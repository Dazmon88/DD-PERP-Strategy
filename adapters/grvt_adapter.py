"""
GRVT Exchange Adapter Implementation

This module implements BasePerpAdapter for GRVT exchange.
"""
import sys
import os
import time
from typing import Dict, Any, Optional, List
from decimal import Decimal

# 添加项目路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from adapters.base_adapter import BasePerpAdapter, Balance, Position, Order

# 导入 GRVT 相关模块
# 注意：将 src 目录添加到 sys.path 后直接导入模块名
grvt_sdk_path = os.path.join(project_root, 'exchange', 'exchange_grvt', 'src')
if grvt_sdk_path not in sys.path:
    sys.path.insert(0, grvt_sdk_path)

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv


class GrvtAdapter(BasePerpAdapter):
    """GRVT 交易所适配器实现"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 GRVT 适配器
        
        Args:
            config: 配置字典，必须包含：
                - exchange_name: "grvt"
                - env: 环境名称，如 "prod", "testnet"（可选，默认 "prod"）
                - api_key: API Key（下单需要）
                - trading_account_id: 交易账户ID（下单需要）
                - private_key: 私钥（下单需要）
        """
        super().__init__(config)
        env_str = config.get("env", "prod").lower()
        env_map = {
            "prod": GrvtEnv.PROD,
            "testnet": GrvtEnv.TESTNET,
            "staging": GrvtEnv.STAGING,
            "dev": GrvtEnv.DEV,
        }
        self.env = env_map.get(env_str, GrvtEnv.PROD)
        
        # 准备认证参数
        parameters = {
            "api_key": config.get("api_key", ""),
            "trading_account_id": config.get("trading_account_id", ""),
            "private_key": config.get("private_key", ""),
        }
        
        # 初始化 GRVT 客户端
        self.grvt_client = GrvtCcxt(env=self.env, parameters=parameters)
    
    def connect(self) -> bool:
        """
        连接到 GRVT（获取价格不需要认证，直接返回成功）
        
        Returns:
            bool: 连接是否成功
        """
        return True
    
    def get_balance(self) -> Balance:
        """查询账户余额"""
        raise NotImplementedError("GRVT 余额查询功能待实现")
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """查询持仓信息"""
        try:
            symbols = [symbol] if symbol else []
            positions_data = self.grvt_client.fetch_positions(symbols=symbols)
            
            print(f"[GRVT] 查询持仓: symbol={symbol}, 返回数据条数={len(positions_data)}")
            if positions_data:
                print(f"[GRVT] 持仓数据示例: {positions_data[0]}")
            
            positions = []
            for idx, pos_data in enumerate(positions_data):
                
                # 获取持仓数量
                size_str = pos_data.get("size", "0")
                try:
                    qty = Decimal(str(size_str))
                except (ValueError, TypeError) as e:
                    continue
                
                # 如果数量为 0，跳过
                if qty == Decimal("0"):
                    print(f"[GRVT] 持仓数量为 0，跳过")
                    continue
                
                # 根据数量正负判断方向
                side = "long" if qty > 0 else "short"
                print(f"[GRVT] 持仓方向: {side}, 数量: {abs(qty)}")
                
                # 处理 leverage 字段（可能是字符串 "50.0"）
                leverage_value = None
                if pos_data.get("leverage"):
                    try:
                        leverage_value = int(float(str(pos_data.get("leverage"))))
                    except (ValueError, TypeError):
                        leverage_value = None
                
                position = Position(
                    symbol=pos_data.get("instrument", symbol or ""),
                    size=abs(qty),  # 使用绝对值
                    side=side,
                    entry_price=Decimal(str(pos_data.get("entry_price", "0"))),
                    mark_price=Decimal(str(pos_data.get("mark_price", "0"))),
                    unrealized_pnl=Decimal(str(pos_data.get("unrealized_pnl", "0"))),
                    leverage=leverage_value,
                    margin_mode=pos_data.get("margin_mode"),
                )
                positions.append(position)
                print(f"[GRVT] 成功创建 Position 对象: {position.symbol}, {position.size}, {position.side}")
            
            print(f"[GRVT] 最终返回持仓数量: {len(positions)}")
            return positions
        except Exception as e:
            print(f"[GRVT] 查询持仓异常: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"GRVT 查询持仓失败: {e}")
    
    def _grvt_order_to_order(self, grvt_order: dict, symbol: str) -> Order:
        """将 GRVT 订单格式转换为 Order 对象"""
        legs = grvt_order.get("legs", [])
        if not legs:
            raise ValueError("GRVT 订单格式错误：缺少 legs")
        
        leg = legs[0]
        metadata = grvt_order.get("metadata", {})
        
        return Order(
            order_id=str(metadata.get("client_order_id", "")),
            symbol=leg.get("instrument", symbol),
            side="buy" if leg.get("is_buying_asset") else "sell",
            order_type="market" if grvt_order.get("is_market") else "limit",
            quantity=Decimal(str(leg.get("size", 0))),
            price=Decimal(str(leg.get("limit_price", 0))) if leg.get("limit_price") else None,
            status="pending",  # GRVT 订单状态需要进一步查询
            created_at=int(time.time() * 1000),
        )
    
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
        """下单"""
        from pysdk.grvt_ccxt_types import GrvtOrderSide
        
        # 转换 side 格式
        grvt_side: GrvtOrderSide = "buy" if side.lower() in ["buy", "long"] else "sell"
        
        # 准备参数
        params = {"reduce_only": reduce_only}
        if client_order_id:
            params["client_order_id"] = client_order_id
        
        # 下单
        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("限价单必须提供价格")
            result = self.grvt_client.create_limit_order(symbol, grvt_side, str(quantity), str(price), params)
        elif order_type.lower() == "market":
            result = self.grvt_client.create_order(symbol, "market", grvt_side, str(quantity), None, params)
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")
        
        if not result:
            raise Exception("下单失败：返回结果为空")
        
        return self._grvt_order_to_order(result, symbol)
    
    def cancel_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> bool:
        """撤单
        
        注意：GRVT 的 order_id 实际上是 client_order_id，所以优先使用 client_order_id
        """
        params = {}
        # 优先使用 client_order_id，如果没有则使用 order_id（在 GRVT 中，order_id 就是 client_order_id）
        if client_order_id:
            params["client_order_id"] = client_order_id
        elif order_id:
            params["client_order_id"] = order_id
        
        return self.grvt_client.cancel_order(id=None, symbol=symbol, params=params)
    
    def cancel_orders_by_ids(
        self,
        order_id_list: List[int],
        symbol: Optional[str] = None,
    ) -> bool:
        """批量撤单
        
        Args:
            order_id_list: 订单ID列表（在 GRVT 中，这些是 client_order_id）
            symbol: 交易对符号（可选）
        """
        success_count = 0
        for order_id in order_id_list:
            try:
                if self.cancel_order(client_order_id=str(order_id), symbol=symbol):
                    success_count += 1
            except Exception:
                continue  # 跳过失败的订单
        
        return success_count > 0
    
    def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
    ) -> bool:
        """撤销所有订单"""
        params = {}
        if symbol:
            # 从 symbol 中提取 base 和 quote，例如 "BTC_USDT_Perp" -> base="BTC", quote="USDT"
            parts = symbol.replace("_Perp", "").split("_")
            if len(parts) >= 2:
                params["base"] = parts[0]
                params["quote"] = parts[1]
            params["kind"] = "PERPETUAL"
        
        return self.grvt_client.cancel_all_orders(params=params)
    
    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        """查询订单状态"""
        params = {}
        if client_order_id:
            params["client_order_id"] = client_order_id
        
        result = self.grvt_client.fetch_order(id=order_id, params=params)
        if not result or not result.get("result"):
            return None
        
        order_data = result.get("result", {})
        legs = order_data.get("legs", [])
        if not legs:
            return None
        
        leg = legs[0]
        metadata = order_data.get("metadata", {})
        
        return Order(
            order_id=str(metadata.get("client_order_id", order_id or "")),
            symbol=leg.get("instrument", symbol or ""),
            side="buy" if leg.get("is_buying_asset") else "sell",
            order_type="market" if order_data.get("is_market") else "limit",
            quantity=Decimal(str(leg.get("size", 0))),
            price=Decimal(str(leg.get("limit_price", 0))) if leg.get("limit_price") else None,
            status="pending",  # 可以根据订单状态进一步判断
            created_at=int(time.time() * 1000),
        )
    
    def get_open_orders(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """查询所有未成交订单"""
        params = {}
        if symbol:
            params["kind"] = "PERPETUAL"
        
        orders_data = self.grvt_client.fetch_open_orders(symbol=symbol, params=params)
        orders = []
        
        for order_data in orders_data:
            try:
                orders.append(self._grvt_order_to_order(order_data, symbol or ""))
            except Exception:
                continue  # 跳过格式错误的订单
        
        return orders
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对的最新价格信息
        
        Args:
            symbol: 交易对符号，如 "BTC_USDT_Perp"
            
        Returns:
            Dict[str, Any]: 包含最新价、买一价、卖一价等信息
        """
        try:
            ticker_data = self.grvt_client.fetch_ticker(symbol)
            
            # 处理返回的数据结构（可能是列表或字典）
            if isinstance(ticker_data, list) and len(ticker_data) > 0:
                ticker_data = ticker_data[0]
            elif isinstance(ticker_data, list) and len(ticker_data) == 0:
                raise Exception(f"未找到交易对 {symbol} 的价格数据")
            
            if not isinstance(ticker_data, dict):
                raise Exception(f"返回的数据格式不正确: {type(ticker_data)}")
            
            # 转换价格（根据 GRVT API 文档，fetch_ticker 返回的价格已经是实际价格，不需要除以 PRICE_MULTIPLIER）
            def parse_price(price_str: Optional[str]) -> Optional[float]:
                if not price_str or price_str == "0":
                    return None
                try:
                    return float(price_str)
                except (ValueError, TypeError):
                    return None
            
            return {
                "symbol": ticker_data.get("instrument", symbol),
                "bid_price": parse_price(ticker_data.get("best_bid_price")),
                "ask_price": parse_price(ticker_data.get("best_ask_price")),
                "mid_price": parse_price(ticker_data.get("mid_price")),
                "last_price": parse_price(ticker_data.get("last_price")),
                "mark_price": parse_price(ticker_data.get("mark_price")),
                "index_price": parse_price(ticker_data.get("index_price")),
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取价格失败: {e}")
    
    def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """获取订单簿"""
        raise NotImplementedError("GRVT 订单簿查询功能待实现")
