import asyncio
import json
import uuid
import time
from typing import Dict, Any, Optional, Callable, List
import websockets
from websockets.exceptions import ConnectionClosed


class StandXMarketStream:
    """Market Stream - 市场数据流"""
    
    def __init__(self, base_url: str = "wss://perps.standx.com/ws-stream/v1"):
        self.base_url = base_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.callbacks: Dict[str, Callable] = {}
        self.connected = False
        self._connect_time: Optional[float] = None  # 记录连接时间，用于 24 小时重连
    
    async def connect(self):
        """建立 WebSocket 连接"""
        try:
            # 禁用代理，避免需要 python-socks
            # 启用 websockets 库的自动 ping/pong 处理
            # 服务器每 10 秒发送 ping，客户端自动响应 pong
            # ping_interval=None 表示不主动发送 ping，只响应服务器的 ping
            # ping_timeout 设置为 5 分钟（服务器要求 5 分钟内响应）
            self.ws = await websockets.connect(
                self.base_url, 
                proxy=None,
                ping_interval=None,      # 不主动发送 ping（服务器会发送）
                ping_timeout=300.0       # 5 分钟超时（服务器要求）
            )
            self.connected = True
            self._connect_time = time.time()  # 记录连接时间
            # 启动消息接收任务
            asyncio.create_task(self._receive_messages())
        except Exception as e:
            self.connected = False
            raise Exception(f"WebSocket 连接失败: {e}")
    
    async def _receive_messages(self):
        """接收消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    # 异步处理消息，避免阻塞接收循环
                    asyncio.create_task(self._handle_message(data))
                except Exception as e:
                    print(f"处理消息错误: {e}")
        except ConnectionClosed:
            self.connected = False
        except Exception as e:
            print(f"接收消息错误: {e}")
            self.connected = False
    
    async def _handle_message(self, data: Dict[str, Any]):
        """处理接收到的消息"""
        channel = data.get("channel")
        if channel and channel in self.callbacks:
            callback = self.callbacks[channel]
            # 如果回调是协程函数，使用 await；否则直接调用
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                # 在事件循环中执行同步回调，避免阻塞
                callback(data)
    
    async def authenticate(self, token: str, streams: Optional[List[Dict[str, str]]] = None):
        """使用 JWT token 认证"""
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        
        auth_msg = {
            "auth": {
                "token": token
            }
        }
        
        if streams:
            auth_msg["auth"]["streams"] = streams
        
        await self.ws.send(json.dumps(auth_msg))
    
    async def subscribe(self, channel: str, symbol: Optional[str] = None, callback: Optional[Callable] = None):
        """订阅频道"""
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        
        subscribe_msg = {"subscribe": {"channel": channel}}
        if symbol:
            subscribe_msg["subscribe"]["symbol"] = symbol
        
        await self._send_message(subscribe_msg)
        
        if callback:
            self.callbacks[channel] = callback
    
    async def _send_message(self, message: Dict[str, Any]):
        """发送消息"""
        if self.ws:
            await self.ws.send(json.dumps(message))
    
    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            self._connect_time = None


class StandXOrderStream:
    """Order Response Stream - 订单响应流"""
    
    def __init__(self, base_url: str = "wss://perps.standx.com/ws-api/v1"):
        self.base_url = base_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session_id = str(uuid.uuid4())
        self.callbacks: Dict[str, Callable] = {}
        self.connected = False
        self.auth: Optional[Any] = None  # StandXAuth 实例，用于签名
        self._connect_time: Optional[float] = None  # 记录连接时间，用于 24 小时重连
    
    async def connect(self):
        """建立 WebSocket 连接"""
        try:
            # 禁用代理，避免需要 python-socks
            # 启用 websockets 库的自动 ping/pong 处理
            # 服务器每 10 秒发送 ping，客户端自动响应 pong
            # ping_interval=None 表示不主动发送 ping，只响应服务器的 ping
            # ping_timeout 设置为 5 分钟（服务器要求 5 分钟内响应）
            self.ws = await websockets.connect(
                self.base_url, 
                proxy=None,
                ping_interval=None,      # 不主动发送 ping（服务器会发送）
                ping_timeout=300.0       # 5 分钟超时（服务器要求）
            )
            self.connected = True
            self._connect_time = time.time()  # 记录连接时间
            # 启动消息接收任务
            asyncio.create_task(self._receive_messages())
        except Exception as e:
            self.connected = False
            raise Exception(f"WebSocket 连接失败: {e}")
    
    async def _receive_messages(self):
        """接收消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    # 异步处理消息，避免阻塞接收循环
                    asyncio.create_task(self._handle_message(data))
                except Exception as e:
                    print(f"处理消息错误: {e}")
        except ConnectionClosed:
            self.connected = False
        except Exception as e:
            print(f"接收消息错误: {e}")
            self.connected = False
    
    async def _handle_message(self, data: Dict[str, Any]):
        """处理接收到的消息"""
        request_id = data.get("request_id")
        if request_id and request_id in self.callbacks:
            callback = self.callbacks[request_id]
            # 如果回调是协程函数，使用 await；否则直接调用
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
            # 一次性回调，处理完后删除
            del self.callbacks[request_id]
    
    async def login(self, token: str, callback: Optional[Callable] = None):
        """使用 JWT token 登录"""
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        
        request_id = str(uuid.uuid4())
        message = {
            "session_id": self.session_id,
            "request_id": request_id,
            "method": "auth:login",
            "params": json.dumps({"token": token})
        }
        
        if callback:
            self.callbacks[request_id] = callback
        
        await self.ws.send(json.dumps(message))
    
    async def new_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        time_in_force: str,
        reduce_only: bool,
        price: Optional[str] = None,
        cl_ord_id: Optional[str] = None,
        callback: Optional[Callable] = None
    ):
        """创建新订单"""
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        
        if not self.auth:
            raise Exception("需要 StandXAuth 实例进行请求签名")
        
        # 构建订单参数
        params = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "time_in_force": time_in_force,
            "reduce_only": reduce_only
        }
        
        if price:
            params["price"] = price
        if cl_ord_id:
            params["cl_ord_id"] = cl_ord_id
        
        params_str = json.dumps(params)
        request_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # 生成签名头
        sign_headers = self.auth.sign_request(params_str, request_id, timestamp)
        
        message = {
            "session_id": self.session_id,
            "request_id": request_id,
            "method": "order:new",
            "header": {
                "x-request-id": sign_headers["x-request-id"],
                "x-request-timestamp": sign_headers["x-request-timestamp"],
                "x-request-signature": sign_headers["x-request-signature"]
            },
            "params": params_str
        }
        
        if callback:
            self.callbacks[request_id] = callback
        
        await self.ws.send(json.dumps(message))
    
    async def cancel_order(
        self,
        order_id_list: Optional[List[int]] = None,
        cl_ord_id_list: Optional[List[str]] = None,
        callback: Optional[Callable] = None
    ):
        """取消订单"""
        if not self.connected or not self.ws:
            raise Exception("WebSocket 未连接")
        
        if not self.auth:
            raise Exception("需要 StandXAuth 实例进行请求签名")
        
        if not order_id_list and not cl_ord_id_list:
            raise ValueError("必须提供 order_id_list 或 cl_ord_id_list")
        
        params = {}
        if order_id_list:
            params["order_id_list"] = order_id_list
        if cl_ord_id_list:
            params["cl_ord_id_list"] = cl_ord_id_list
        
        params_str = json.dumps(params)
        request_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        # 生成签名头
        sign_headers = self.auth.sign_request(params_str, request_id, timestamp)
        
        message = {
            "session_id": self.session_id,
            "request_id": request_id,
            "method": "order:cancel",
            "header": {
                "x-request-id": sign_headers["x-request-id"],
                "x-request-timestamp": sign_headers["x-request-timestamp"],
                "x-request-signature": sign_headers["x-request-signature"]
            },
            "params": params_str
        }
        
        if callback:
            self.callbacks[request_id] = callback
        
        await self.ws.send(json.dumps(message))
    
    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            self._connect_time = None