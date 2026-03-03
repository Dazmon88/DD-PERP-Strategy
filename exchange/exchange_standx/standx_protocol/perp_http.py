"""
StandX Perps HTTP API Client
"""
from typing import Dict, Any, Optional, List
import requests
import json
import time
import uuid


class RegionResponse:
    """Region and server time response"""
    def __init__(self, data: Dict[str, Any]):
        self.system_time = data.get("systemTime")
        self.region = data.get("region")


class StandXPerpHTTP:
    """StandX Perps HTTP API Client"""
    
    def __init__(self, base_url: str = "https://perps.standx.com", geo_url: str = "https://geo.standx.com"):
        """
        Initialize StandX Perps HTTP client.
        
        Args:
            base_url: Base URL for perps API (default: https://perps.standx.com)
            geo_url: Base URL for geo API (default: https://geo.standx.com)
        """
        self.base_url = base_url.rstrip('/')
        self.geo_url = geo_url.rstrip('/')
    
    def health_check(self) -> str:
        """
        Health check endpoint.
        
        Returns:
            "OK" string if healthy
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/health"
        response = requests.get(url, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.text.strip()
    
    def get_region(self) -> RegionResponse:
        """
        Get region and server time.
        
        Returns:
            RegionResponse object with systemTime and region
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.geo_url}/v1/region"
        # 增加超时时间，防止网络问题导致长时间阻塞
        response = requests.get(url, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        region = RegionResponse(data)
        return region

    def _get_sign_timestamp(self) -> int:
        """
        获取用于签名的时间戳（秒）
        
        优先使用服务器时间；如果无法获取服务器时间，则回退到本地时间。
        """
        try:
            region = self.get_region()
            if region.system_time is not None:
                return int(region.system_time)
        except Exception:
            pass
        
        # 回退：使用本地时间（秒）
        return int(time.time())
    
    def query_balance(
        self,
        token: str
    ) -> Dict[str, Any]:
        """
        Query user balances (unified balance snapshot).
        
        Args:
            token: Authentication token
            
        Returns:
            Balance data as dictionary with fields:
            - isolated_balance: Isolated wallet total
            - isolated_upnl: Isolated unrealized PnL
            - cross_balance: Cross wallet free balance
            - cross_margin: Cross margin used
            - cross_upnl: Cross unrealized PnL
            - locked: Order lock (margin + fee)
            - cross_available: cross_balance - cross_margin - locked + cross_upnl
            - balance: Total account assets
            - upnl: Total unrealized PnL
            - equity: Account equity
            - pnl_freeze: 24h realized PnL
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/query_balance"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(url, headers=headers, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def place_order(
        self,
        token: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        time_in_force: str,
        reduce_only: bool,
        price: Optional[str] = None,
        cl_ord_id: Optional[str] = None,
        margin_mode: Optional[str] = None,
        leverage: Optional[int] = None,
        session_id: Optional[str] = None,
        auth: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Create new order.
        
        Args:
            token: Authentication token
            symbol: Trading pair (e.g., "BTC-USD")
            side: Order side ("buy" or "sell")
            order_type: Order type ("limit", "market", etc.)
            qty: Order quantity (decimal as string)
            time_in_force: Time in force ("gtc", "ioc", "fok", etc.)
            reduce_only: Only reduce position if true
            price: Order price (required for limit orders, decimal as string)
            cl_ord_id: Client order ID (auto-generated if omitted)
            margin_mode: Margin mode (must match position)
            leverage: Leverage value (must match position)
            session_id: Session ID for order response stream
            auth: StandXAuth instance for request signing (required)
            
        Returns:
            Response dictionary with code, message, and request_id
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/new_order"
        payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "time_in_force": time_in_force,
            "reduce_only": reduce_only
        }
        
        if price is not None:
            payload["price"] = price
        if cl_ord_id is not None:
            payload["cl_ord_id"] = cl_ord_id
        if margin_mode is not None:
            payload["margin_mode"] = margin_mode
        if leverage is not None:
            payload["leverage"] = leverage
        
        payload_str = json.dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Add session_id if provided
        if session_id:
            headers["x-session-id"] = session_id
        
        # Request signing is required
        if not auth:
            raise ValueError("StandXAuth instance is required for request signing")
        
        # 使用缓存的服务器时间或本地时间进行签名，避免频繁访问 geo 接口导致阻塞
        request_id = str(uuid.uuid4())
        timestamp = self._get_sign_timestamp()
        sign_headers = auth.sign_request(payload_str, request_id, timestamp)
        headers.update(sign_headers)
        
        response = requests.post(url, headers=headers, data=payload_str, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def query_positions(
        self,
        token: str,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query user positions.
        
        Args:
            token: Authentication token
            symbol: Trading pair (optional, e.g., "BTC-USD")
            
        Returns:
            List of position dictionaries with fields:
            - id: Position ID
            - symbol: Trading pair
            - qty: Position quantity (positive for long, negative for short)
            - entry_price: Entry price
            - mark_price: Mark price
            - upnl: Unrealized PnL
            - leverage: Leverage
            - margin_mode: Margin mode ("isolated" or "cross")
            - status: Position status ("open" or "closed")
            - and other fields...
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/query_positions"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        response = requests.get(url, headers=headers, params=params, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def query_symbol_price(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Query symbol price.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD")
            
        Returns:
            Price data as dictionary with fields:
            - base: Base currency
            - index_price: Index price
            - last_price: Last trade price (may be null)
            - mark_price: Mark price
            - mid_price: Mid price (may be null)
            - quote: Quote currency
            - spread_ask: Ask price (may be null)
            - spread_bid: Bid price (may be null)
            - symbol: Trading pair
            - time: Timestamp
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/query_symbol_price"
        params = {"symbol": symbol}
        
        response = requests.get(url, params=params, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def query_open_orders(
        self,
        token: str,
        symbol: Optional[str] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        Query user all open orders.
        
        Args:
            token: Authentication token
            symbol: Trading pair (optional, e.g., "BTC-USD")
            limit: Results limit (default: 500, max: 1200)
            
        Returns:
            Response dictionary with fields:
            - page_size: Page size
            - result: List of order dictionaries
            - total: Total number of orders
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/query_open_orders"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        params = {}
        if symbol:
            params["symbol"] = symbol
        if limit:
            params["limit"] = limit
        
        response = requests.get(url, headers=headers, params=params, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def cancel_orders(
        self,
        token: str,
        order_id_list: Optional[List[int]] = None,
        cl_ord_id_list: Optional[List[str]] = None,
        auth: Optional[Any] = None
    ) -> List[Any]:
        """
        Cancel multiple orders.
        
        Args:
            token: Authentication token
            order_id_list: List of order IDs to cancel
            cl_ord_id_list: List of client order IDs to cancel
            auth: StandXAuth instance for request signing (required)
            
        Returns:
            Empty list on success
            
        Raises:
            ValueError: If request fails or neither order_id_list nor cl_ord_id_list is provided
        """
        if not order_id_list and not cl_ord_id_list:
            raise ValueError("At least one of order_id_list or cl_ord_id_list is required")
        
        url = f"{self.base_url}/api/cancel_orders"
        payload = {}
        
        if order_id_list:
            payload["order_id_list"] = order_id_list
        if cl_ord_id_list:
            payload["cl_ord_id_list"] = cl_ord_id_list
        
        payload_str = json.dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Request signing is required
        if not auth:
            raise ValueError("StandXAuth instance is required for request signing")
        
        # 使用缓存的服务器时间或本地时间进行签名，避免频繁访问 geo 接口导致阻塞
        request_id = str(uuid.uuid4())
        timestamp = self._get_sign_timestamp()
        sign_headers = auth.sign_request(payload_str, request_id, timestamp)
        headers.update(sign_headers)
        
        response = requests.post(url, headers=headers, data=payload_str, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def query_positions(
        self,
        token: str,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query user positions.
        
        Args:
            token: Authentication token
            symbol: Trading pair (optional, e.g., "BTC-USD")
            
        Returns:
            List of position dictionaries with fields:
            - id: Position ID
            - symbol: Trading pair
            - qty: Position quantity (positive for long, negative for short)
            - entry_price: Entry price
            - mark_price: Mark price
            - upnl: Unrealized PnL
            - leverage: Leverage
            - margin_mode: Margin mode ("isolated" or "cross")
            - status: Position status ("open" or "closed")
            - and other fields...
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/query_positions"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        response = requests.get(url, headers=headers, params=params, timeout=2.0)
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
