"""
StandX Exchange Adapter Implementation

This module implements BasePerpAdapter for StandX exchange.
"""
import sys
import os
import time
import base64
import base58
from typing import Dict, Any, Optional, List
from decimal import Decimal

# 添加项目路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from adapters.base_adapter import BasePerpAdapter, Balance, Position, Order

# 导入 StandX 相关模块
import sys
import os
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from exchange.exchange_standx.standx_protocol.perps_auth import StandXAuth
from exchange.exchange_standx.standx_protocol.perp_http import StandXPerpHTTP
from eth_account.messages import encode_defunct
from eth_account import Account
from web3 import Web3


class StandXAdapter(BasePerpAdapter):
    """StandX 交易所适配器实现"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 StandX 适配器
        
        Args:
            config: 配置字典，支持两种认证方式：
                方式1（优先）: API Token 方式
                    - api_key: StandX API Token
                    - signing_key: Ed25519 签名私钥（base64/hex/base58 格式）
                方式2: 钱包私钥方式
                    - private_key: 钱包私钥
                    - chain: 链名称，如 "bsc" 或 "solana"
                - base_url: API 基础 URL（可选，默认 https://perps.standx.com）
        """
        super().__init__(config)
        
        # 优先使用 API Token 方式
        self.api_key = config.get("api_key", "").strip()
        self.signing_key = config.get("signing_key", "").strip()
        
        # 如果没有 API Token，则使用钱包私钥方式
        self.private_key = config.get("private_key", "").strip()
        self.chain = config.get("chain", "bsc")
        
        # 验证配置：支持两种登录方式，但只需要提供一种
        has_api_token = bool(self.api_key)
        has_wallet_key = bool(self.private_key)
        
        if not has_api_token and not has_wallet_key:
            raise ValueError("配置中必须包含 api_key 或 private_key（至少一种）")
        
        # 如果使用 API Token 方式，必须提供 signing_key
        if has_api_token and not self.signing_key:
            raise ValueError("使用 API Token 方式时，必须提供 signing_key（与 api_key 配对）")
        
        # 如果只使用钱包私钥方式，不需要 signing_key（会自动生成 Ed25519 密钥对）
        # chain 字段有默认值 "bsc"，所以即使不提供也可以工作
        
        base_url = config.get("base_url", "https://perps.standx.com")
        self.http_client = StandXPerpHTTP(base_url=base_url)
        
        # 根据配置选择认证方式
        if self.api_key:
            # API Token 方式：使用提供的 signing_key 初始化 StandXAuth
            signing_key_bytes = self._parse_signing_key(self.signing_key)
            self.auth = StandXAuth(private_key=signing_key_bytes)
            self.use_api_token = True
            self.token = self.api_key  # API Token 直接作为 token 使用
        else:
            # 钱包私钥方式：生成新的 Ed25519 密钥对用于请求签名
            self.auth = StandXAuth()
            self.use_api_token = False
            
            # 获取钱包地址
            if self.private_key.startswith('0x'):
                private_key = self.private_key[2:]
            else:
                private_key = self.private_key
            
            account = Web3().eth.account.from_key(private_key)
            self.wallet_address = account.address
            self.token: Optional[str] = None
    
    def _parse_signing_key(self, signing_key: str) -> bytes:
        """
        解析 signing_key，支持多种编码格式
        
        Args:
            signing_key: Ed25519 私钥，支持 base64、hex、base58 格式
            
        Returns:
            32 字节的私钥 bytes
        """
        if not signing_key:
            raise ValueError("signing_key 不能为空")
        
        signing_key = signing_key.strip()
        
        # 尝试 base64 解码
        try:
            decoded = base64.b64decode(signing_key)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        
        # 尝试 base64url 解码
        try:
            # base64url 使用 - 和 _ 而不是 + 和 /
            base64url = signing_key.replace('-', '+').replace('_', '/')
            # 添加 padding
            padding = len(base64url) % 4
            if padding:
                base64url += '=' * (4 - padding)
            decoded = base64.b64decode(base64url)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        
        # 尝试 hex 解码
        try:
            if signing_key.startswith('0x'):
                signing_key = signing_key[2:]
            decoded = bytes.fromhex(signing_key)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        
        # 尝试 base58 解码
        try:
            decoded = base58.b58decode(signing_key)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        
        raise ValueError(f"无法解析 signing_key，支持的格式：base64、hex、base58。当前长度: {len(signing_key)}")
    
    def _sign_message(self, message: str) -> str:
        """签名消息"""
        private_key = self.private_key
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        account = Account.from_key(private_key)
        message_encoded = encode_defunct(text=message)
        signed = account.sign_message(message_encoded)
        return "0x" + signed.signature.hex()
    
    def connect(self) -> bool:
        """连接到 StandX 并完成认证"""
        try:
            if self.use_api_token:
                # API Token 方式：直接使用 API Token，无需登录
                # token 已经在 __init__ 中设置为 api_key
                return True
            else:
                # 钱包私钥方式：需要先登录获取 token
                def sign_message(msg: str) -> str:
                    return self._sign_message(msg)
                
                login_response = self.auth.authenticate(
                    chain=self.chain,
                    wallet_address=self.wallet_address,
                    sign_message=sign_message
                )
                
                self.token = login_response.token
                return True
        except Exception as e:
            raise Exception(f"StandX 认证失败: {e}")
    
    def get_balance(self) -> Balance:
        """查询账户余额"""
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        try:
            balance_data = self.http_client.query_balance(self.token)
            
            return Balance(
                total_balance=Decimal(str(balance_data.get("balance", "0"))),
                available_balance=Decimal(str(balance_data.get("cross_available", "0"))),
                equity=Decimal(str(balance_data.get("equity", "0"))),
                unrealized_pnl=Decimal(str(balance_data.get("upnl", "0"))),
                margin_used=Decimal(str(balance_data.get("cross_margin", "0"))) if balance_data.get("cross_margin") else None,
                margin_available=Decimal(str(balance_data.get("cross_available", "0"))) if balance_data.get("cross_available") else None,
            )
        except Exception as e:
            raise Exception(f"查询余额失败: {e}")
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        查询持仓信息
        
        Args:
            symbol: 交易对符号，如果为 None 则返回所有持仓
            
        Returns:
            List[Position]: 持仓信息列表
        """
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        try:
            positions_data = self.http_client.query_positions(
                token=self.token,
                symbol=symbol
            )
            
            positions = []
            for pos_data in positions_data:
                # 只处理状态为 "open" 的持仓
                if pos_data.get("status") != "open":
                    continue
                
                qty = Decimal(str(pos_data.get("qty", "0")))
                # 如果数量为 0，跳过
                if qty == Decimal("0"):
                    continue
                
                # 根据数量正负判断方向
                side = "long" if qty > 0 else "short"
                
                position = Position(
                    symbol=pos_data.get("symbol", ""),
                    size=abs(qty),  # 使用绝对值
                    side=side,
                    entry_price=Decimal(str(pos_data.get("entry_price", "0"))),
                    mark_price=Decimal(str(pos_data.get("mark_price", "0"))),
                    unrealized_pnl=Decimal(str(pos_data.get("upnl", "0"))),
                    leverage=int(pos_data.get("leverage", 1)) if pos_data.get("leverage") else None,
                    margin_mode=pos_data.get("margin_mode"),
                )
                positions.append(position)
            
            return positions
        except Exception as e:
            raise Exception(f"查询持仓失败: {e}")
    
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
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        if order_type == "limit" and price is None:
            raise ValueError("限价单必须指定价格")
        
        try:
            # 转换 side: "long"/"short" -> "buy"/"sell"
            if side in ["long", "buy"]:
                side_str = "buy"
            elif side in ["short", "sell"]:
                side_str = "sell"
            else:
                side_str = side
            
            response = self.http_client.place_order(
                token=self.token,
                symbol=symbol,
                side=side_str,
                order_type=order_type,
                qty=str(quantity),
                price=str(price) if price else None,
                time_in_force=time_in_force,
                reduce_only=reduce_only,
                cl_ord_id=client_order_id,
                auth=self.auth,
                **kwargs
            )
            
            if response.get("code") != 0:
                raise Exception(f"下单失败: {response.get('message', '未知错误')}")
            
            # 构造订单对象
            order_id = response.get("request_id", "")
            
            return Order(
                order_id=order_id,
                symbol=symbol,
                side=side_str,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="pending",
                time_in_force=time_in_force,
                reduce_only=reduce_only,
                client_order_id=client_order_id,
            )
        except Exception as e:
            raise Exception(f"下单失败: {e}")
    
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
            symbol: 交易对符号（可选）
            client_order_id: 客户端订单ID（可选）
        
        Returns:
            bool: 撤单是否成功
        """
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        if not order_id and not client_order_id:
            raise ValueError("必须提供 order_id 或 client_order_id")
        
        try:
            order_id_list = None
            cl_ord_id_list = None
            
            if order_id:
                # 将字符串转换为整数
                try:
                    order_id_list = [int(order_id)]
                except ValueError:
                    raise ValueError(f"无效的订单ID: {order_id}")
            
            if client_order_id:
                cl_ord_id_list = [client_order_id]
            
            result = self.http_client.cancel_orders(
                token=self.token,
                order_id_list=order_id_list,
                cl_ord_id_list=cl_ord_id_list,
                auth=self.auth
            )
            
            # API 返回空数组表示成功
            return True
        except Exception as e:
            raise Exception(f"撤单失败: {e}")
    
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
        """
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        try:
            # 获取所有未成交订单
            open_orders = self.get_open_orders(symbol=symbol)
            
            if not open_orders:
                return True  # 没有订单，直接返回成功
            
            # 提取订单ID
            order_id_list = []
            for order in open_orders:
                try:
                    order_id_list.append(int(order.order_id))
                except (ValueError, TypeError):
                    # 如果订单ID不是整数，尝试使用客户端订单ID
                    if order.client_order_id:
                        # 如果有客户端订单ID，需要单独处理
                        pass
            
            if not order_id_list:
                return True  # 没有有效的订单ID
            
            # 批量撤单
            result = self.http_client.cancel_orders(
                token=self.token,
                order_id_list=order_id_list,
                auth=self.auth
            )
            
            return True
        except Exception as e:
            raise Exception(f"批量撤单失败: {e}")
    
    def cancel_orders_by_ids(
        self,
        order_id_list: Optional[List[int]] = None,
        cl_ord_id_list: Optional[List[str]] = None,
    ) -> bool:
        """
        批量撤单（根据订单ID列表）
        
        Args:
            order_id_list: 订单ID列表
            cl_ord_id_list: 客户端订单ID列表
        
        Returns:
            bool: 撤单是否成功
        """
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        if not order_id_list and not cl_ord_id_list:
            raise ValueError("必须提供 order_id_list 或 cl_ord_id_list")
        
        try:
            result = self.http_client.cancel_orders(
                token=self.token,
                order_id_list=order_id_list,
                cl_ord_id_list=cl_ord_id_list,
                auth=self.auth
            )
            return True
        except Exception as e:
            raise Exception(f"批量撤单失败: {e}")
    
    def get_order(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Order]:
        """
        查询订单状态
        
        注意: 需要根据 StandX API 文档实现
        """
        # TODO: 实现订单查询
        raise NotImplementedError("StandX 订单查询功能待实现")
    
    def get_open_orders(
        self,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """
        查询所有未成交订单
        
        Args:
            symbol: 交易对符号，如果为 None 则返回所有交易对的订单
            
        Returns:
            List[Order]: 未成交订单列表
        """
        if not self.token:
            raise Exception("未认证，请先调用 connect()")
        
        try:
            orders_data = self.http_client.query_open_orders(
                token=self.token,
                symbol=symbol,
                limit=1200
            )
            
            orders = []
            for order_data in orders_data.get("result", []):
                # 映射订单状态
                status_map = {
                    "new": "open",
                    "pending": "pending",
                    "partially_filled": "partially_filled",
                    "filled": "filled",
                    "cancelled": "cancelled",
                    "rejected": "rejected"
                }
                status = status_map.get(order_data.get("status", "").lower(), "pending")
                
                # 只返回未成交的订单
                if status not in ["open", "pending", "partially_filled"]:
                    continue
                
                # 解析时间戳
                created_at = None
                updated_at = None
                if order_data.get("created_at"):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(order_data["created_at"].replace("Z", "+00:00"))
                        created_at = int(dt.timestamp() * 1000)
                    except:
                        pass
                if order_data.get("updated_at"):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(order_data["updated_at"].replace("Z", "+00:00"))
                        updated_at = int(dt.timestamp() * 1000)
                    except:
                        pass
                
                order = Order(
                    order_id=str(order_data.get("id", "")),
                    symbol=order_data.get("symbol", ""),
                    side=order_data.get("side", "").lower(),
                    order_type=order_data.get("order_type", "").lower(),
                    quantity=Decimal(str(order_data.get("qty", "0"))),
                    price=Decimal(str(order_data.get("price", "0"))) if order_data.get("price") else None,
                    filled_quantity=Decimal(str(order_data.get("fill_qty", "0"))),
                    status=status,
                    time_in_force=order_data.get("time_in_force", "gtc").lower(),
                    reduce_only=order_data.get("reduce_only", False),
                    client_order_id=order_data.get("cl_ord_id"),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                orders.append(order)
            
            return orders
        except Exception as e:
            raise Exception(f"查询未成交订单失败: {e}")
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对的最新价格信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            Dict[str, Any]: 包含最新价、买一价、卖一价等信息
        """
        try:
            price_data = self.http_client.query_symbol_price(symbol)
            
            return {
                "symbol": price_data.get("symbol", symbol),
                "bid_price": float(price_data["spread_bid"]) if price_data.get("spread_bid") else None,
                "ask_price": float(price_data["spread_ask"]) if price_data.get("spread_ask") else None,
                "mid_price": float(price_data["mid_price"]) if price_data.get("mid_price") else None,
                "last_price": float(price_data["last_price"]) if price_data.get("last_price") else None,
                "mark_price": float(price_data["mark_price"]) if price_data.get("mark_price") else None,
                "index_price": float(price_data["index_price"]) if price_data.get("index_price") else None,
                "timestamp": int(time.time() * 1000),
            }
        except Exception as e:
            raise Exception(f"获取价格失败: {e}")
    
    def get_orderbook(
        self,
        symbol: str,
        depth: int = 20,
    ) -> Dict[str, Any]:
        """
        获取订单簿
        
        注意: StandX API 可能没有公开的订单簿接口
        
        Args:
            symbol: 交易对符号
            depth: 深度，默认 20
            
        Returns:
            Dict[str, Any]: 包含 bids 和 asks 的订单簿数据
        """
        raise NotImplementedError("StandX 订单簿查询功能待实现")
