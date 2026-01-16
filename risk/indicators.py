"""
Technical Indicators Tool
技术指标工具类
"""
import requests
import pandas as pd
import talib
from typing import Optional


class IndicatorTool:
    """技术指标工具类"""
    
    def get_adx(
        self,
        symbol: str,
        resolution: str,
        period: int = 14
    ) -> Optional[float]:
        """
        获取 ADX 指标（使用币安数据）
        
        Args:
            symbol: 交易对符号 (e.g., "BTC-USD" 转换为 "BTCUSDT")
            resolution: 时间周期 (e.g., "1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M")
            period: ADX 计算周期，默认 14
            
        Returns:
            Optional[float]: ADX 值，如果计算失败返回 None
        """
        try:
            # 转换交易对格式为币安格式: BTC-USD/BTC-USDT/BTC_USDT_Perp -> BTCUSDT
            binance_symbol = symbol.upper().replace("_PERP", "").replace("-", "").replace("_", "")
            if binance_symbol.endswith("USD") and not binance_symbol.endswith("USDT"):
                binance_symbol = binance_symbol[:-3] + "USDT"
            
            # 从币安获取K线数据
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": binance_symbol,
                "interval": resolution,
                "limit": 100
            }
            
            try:
                response = requests.get(url, params=params, timeout=5)
            except requests.exceptions.RequestException as e:
                print(f"ADX指标: 无法连接币安API - {type(e).__name__}")
                return None
            
            if not response.ok:
                print(f"ADX指标: 币安API返回错误 - HTTP {response.status_code}")
                return None
            
            data = response.json()
            if not data:
                print(f"ADX指标: 币安API返回空数据")
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # 转换为数值类型
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            
            # 计算 ADX
            adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=period)
            
            # 返回最新的 ADX 值
            return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else None
            
        except Exception:
            return None
