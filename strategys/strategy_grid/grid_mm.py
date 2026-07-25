import sys
import os
import yaml
import time
import random
import argparse
import math
import urllib.request
import urllib.parse
from decimal import Decimal
from typing import Any, Dict, List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from adapters import create_adapter
from risk import IndicatorTool

# 全局配置变量
EXCHANGE_CONFIG = None
SYMBOL = None
GRID_CONFIG = None
RISK_CONFIG = None
CANCEL_STALE_ORDERS_CONFIG = None
TELEGRAM_CONFIG = None
_LAST_BALANCE_SENT_AT = 0.0


def load_config(config_file="config.yaml"):
    """
    加载配置文件
    
    Args:
        config_file: 配置文件路径，可以是相对路径或绝对路径
    
    Returns:
        dict: 配置字典
    """
    # 如果是相对路径，相对于脚本目录
    if not os.path.isabs(config_file):
        config_path = os.path.join(current_dir, config_file)
    else:
        config_path = config_file
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def convert_symbol_format(symbol, exchange_name):
    """根据交易所类型转换交易对格式
    
    Args:
        symbol: 原始交易对，如 "BTC-USDT" 或 "BTC-USD"
        exchange_name: 交易所名称，如 "standx" 或 "grvt"
    
    Returns:
        转换后的交易对格式
    """
    exchange_name = exchange_name.lower()
    if exchange_name == "grvt":
        # GRVT 使用 BTC_USDT_Perp 格式
        # 将 "BTC-USDT" 转换为 "BTC_USDT_Perp"
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            return f"{base}_{quote}_Perp"
        return symbol
    elif exchange_name == "hype":
        # Hype 永续通常使用 coin 作为 symbol，例如 BTC / ETH
        # 兼容 "BTC-USDT"、"BTC-USD"、"BTC_USDT_Perp" 等输入
        if "_" in symbol and "_Perp" in symbol:
            # GRVT 格式: BTC_USDT_Perp -> BTC
            return symbol.split("_", 1)[0]
        if "-" in symbol:
            # 通用格式: BTC-USDT / BTC-USD -> BTC
            return symbol.split("-", 1)[0]
        return symbol
    elif exchange_name == "lighter":
        # Lighter 适配器内部会做 normalize（移除分隔符并大写），这里保持原样
        return symbol
    elif exchange_name == "popdex":
        # PopDEX: BTC-USDT / BTC-USD -> BTCUSDT
        s = symbol.replace("_Perp", "").replace("_", "").replace("-", "")
        return s.upper()
    elif exchange_name in ("ondo", "ondoperp", "ondoperps"):
        # Ondo: AAPL-USD / AAPL → AAPL-USD.P
        s = symbol.strip()
        if s.upper().endswith(".P"):
            if "." in s:
                base, suf = s.rsplit(".", 1)
                return f"{base.upper()}.{suf.upper()}"
            return s.upper()
        if "_" in s:
            s = s.replace("_Perp", "").replace("_P", "").replace("_", "-")
        if "-" not in s:
            s = f"{s}-USD"
        if not s.upper().endswith(".P"):
            s = f"{s}.P"
        if "." in s:
            base, suf = s.rsplit(".", 1)
            return f"{base.upper()}.{suf.upper()}"
        return s.upper()
    else:
        # StandX 等其他交易所保持原格式
        return symbol


def convert_symbol_for_adx(symbol):
    """将交易对格式转换为指标需要的格式（币安格式）
    
    ADX 指标使用币安数据，IndicatorTool 内部会将 "BTC-USD" 转换为 "BTCUSDT"
    对于 GRVT 的 "BTC_USDT_Perp" 格式，需要先转换为 "BTC-USDT" 格式
    
    Args:
        symbol: 交易对符号，支持多种格式：
               - "BTC-USD" (StandX 格式)
               - "BTC-USDT" (通用格式)
               - "BTC_USDT_Perp" (GRVT 格式)
    
    Returns:
        转换后的交易对格式，用于 ADX 指标计算
    """
    if "_" in symbol and "_Perp" in symbol:
        # GRVT 格式: BTC_USDT_Perp -> BTC-USDT
        return symbol.replace("_Perp", "").replace("_", "-")
    if "-" not in symbol and "_" not in symbol:
        # Hype 格式: BTC -> BTC-USDT（供 IndicatorTool 转币安符号）
        return f"{symbol}-USDT"
    else:
        # StandX 等其他格式保持原样
        return symbol


def initialize_config(config_file="config.yaml", active_exchange_override=None):
    """初始化全局配置变量
    
    使用多交易所配置格式：
    - exchanges: 包含多个交易所的配置
    - 必须通过命令行参数 --exchange 指定当前使用的交易所
    
    Args:
        config_file: 配置文件路径
        active_exchange_override: 通过命令行参数指定的交易所名称（必需）
    """
    global EXCHANGE_CONFIG, SYMBOL, GRID_CONFIG, RISK_CONFIG, CANCEL_STALE_ORDERS_CONFIG, TELEGRAM_CONFIG
    
    config = load_config(config_file)
    
    # 检查必需的配置项
    if 'exchanges' not in config:
        raise ValueError("配置错误: 必须提供 exchanges 配置")
    
    # 必须通过命令行参数指定交易所
    if not active_exchange_override:
        raise ValueError("配置错误: 必须通过命令行参数 --exchange 指定交易所")
    
    active_exchange_name = active_exchange_override
    if active_exchange_name not in config['exchanges']:
        raise ValueError(f"配置错误: 交易所 '{active_exchange_name}' 在 exchanges 中不存在")
    
    EXCHANGE_CONFIG = config['exchanges'][active_exchange_name].copy()

    def _expand(v):
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            return os.getenv(v[2:-1], "").strip()
        return v

    for k, v in list(EXCHANGE_CONFIG.items()):
        EXCHANGE_CONFIG[k] = _expand(v)

    raw_symbol = EXCHANGE_CONFIG.pop('symbol', None)
    
    if not raw_symbol:
        raise ValueError(f"配置错误: exchanges.{active_exchange_name} 中缺少 symbol 配置")
    
    exchange_name = EXCHANGE_CONFIG.get('exchange_name', active_exchange_name)
    # 根据交易所类型转换交易对格式
    SYMBOL = convert_symbol_format(raw_symbol, exchange_name)
    
    GRID_CONFIG = config['grid']
    RISK_CONFIG = config.get('risk', {})
    CANCEL_STALE_ORDERS_CONFIG = config.get('cancel_stale_orders', {})
    TELEGRAM_CONFIG = config.get('telegram', {})


def get_price_precision(price_step):
    """根据 price_step 推断价格小数位数。"""
    step_decimal = Decimal(str(price_step)).normalize()
    exponent = step_decimal.as_tuple().exponent
    return max(0, -exponent)


def normalize_price(price, price_step):
    """按 price_step 网格归一化价格，避免浮点误差。"""
    step = Decimal(str(price_step))
    if step <= 0:
        raise ValueError("price_step 必须大于 0")
    price_decimal = Decimal(str(price))
    precision = get_price_precision(price_step)
    normalized = (price_decimal / step).quantize(Decimal("1")) * step
    return round(float(normalized), precision)


def normalize_price_list(prices, price_step):
    """归一化价格数组并去重排序。"""
    normalized = [normalize_price(price, price_step) for price in prices]
    return sorted(set(normalized))


def build_price_ladder(lower_price, upper_price, price_step):
    """构建 [lower_price, upper_price] 闭区间的价格梯子。"""
    lower = Decimal(str(lower_price))
    upper = Decimal(str(upper_price))
    step = Decimal(str(price_step))
    if step <= 0:
        raise ValueError("price_step 必须大于 0")
    if lower > upper:
        raise ValueError("lower_price 不能大于 upper_price")

    ladder = []
    current = lower
    precision = get_price_precision(price_step)
    while current <= upper:
        ladder.append(round(float(current), precision))
        current += step
    return ladder


def generate_grid_arrays(
    current_price,
    price_step,
    grid_count,
    signed_position_size=Decimal("0"),
    order_quantity=Decimal("1"),
    max_position_multiplier=3,
    lower_price=None,
    upper_price=None,
    mode="neutral",
):
    """从价格梯子中围绕当前价生成多空数组，并按持仓动态调整多空比例。

    mode:
      - neutral: 双边挂单（默认）
      - long: 正常挂 buy；仅持仓为正时按可平仓量挂 sell
      - short: 正常挂 sell；仅持仓为负时按可平仓量挂 buy
    """
    if price_step <= 0:
        raise ValueError("price_step 必须大于 0")
    if grid_count < 0:
        raise ValueError("grid_count 必须大于等于 0")

    if lower_price is None or upper_price is None:
        raise ValueError("必须配置 lower_price 和 upper_price")

    mode = str(mode or "neutral").strip().lower()
    if mode not in ("neutral", "long", "short"):
        raise ValueError("mode 必须是 neutral / long / short")

    price_ladder = build_price_ladder(lower_price, upper_price, price_step)
    current_price = float(current_price)
    pos = Decimal(str(signed_position_size))
    order_qty_decimal = Decimal(str(order_quantity))

    # 按当前持仓动态调整多空数组个数
    total_grid_count = grid_count * 2
    long_count = grid_count
    short_count = grid_count
    try:
        max_multiplier_decimal = Decimal(str(max_position_multiplier))
        max_position = order_qty_decimal * max_multiplier_decimal
        if max_position > 0:
            utilization = float(pos / max_position)
            utilization = max(-1.0, min(1.0, utilization))
            bias = int(round(grid_count * utilization))
            long_count = max(0, min(total_grid_count, grid_count - bias))
            short_count = total_grid_count - long_count
    except Exception:
        # 参数异常时回退到默认对称网格
        long_count = grid_count
        short_count = grid_count

    long_candidates = [p for p in price_ladder if p < current_price]
    short_candidates = [p for p in price_ladder if p > current_price]

    # long: 取离当前价最近的 N 个，按“近到远”输出
    long_grid = list(reversed(long_candidates[-long_count:])) if long_count > 0 else []
    # short: 取离当前价最近的 N 个，按“近到远”输出
    short_grid = short_candidates[:short_count] if short_count > 0 else []

    # 按模式裁剪平仓侧：可平仓档数 = floor(|pos| / order_quantity)
    if order_qty_decimal > 0:
        close_levels = int(abs(pos) // order_qty_decimal)
    else:
        close_levels = 0

    if mode == "long":
        # 只建多；无多仓时不挂 sell，有多仓时 sell 不超过可平仓量
        if pos <= 0:
            short_grid = []
        else:
            short_grid = short_grid[:close_levels]
    elif mode == "short":
        # 只建空；无空仓时不挂 buy，有空仓时 buy 不超过可平仓量
        if pos >= 0:
            long_grid = []
        else:
            long_grid = long_grid[:close_levels]

    return long_grid, short_grid


def get_pending_orders_arrays(adapter, symbol):
    """获取当前账号未成交订单数组，按做多和做空分类，同时返回价格到订单ID的映射
    
    Returns:
        (long_prices, short_prices, long_price_to_ids, short_price_to_ids):
        - long_prices: 做多价格数组
        - short_prices: 做空价格数组
        - long_price_to_ids: 做多价格到订单ID列表的字典映射
        - short_price_to_ids: 做空价格到订单ID列表的字典映射
    """
    try:
        open_orders = adapter.get_open_orders(symbol=symbol)
        
        # 做多订单：side 为 "buy" 或 "long"
        long_prices = []
        long_price_to_ids = {}  # 价格 -> 订单ID列表
        # 做空订单：side 为 "sell" 或 "short"
        short_prices = []
        short_price_to_ids = {}  # 价格 -> 订单ID列表
        
        valid_pending_statuses = {"pending", "open", "partially_filled", "resting", "new"}
        for order in open_orders:
            # 只处理未成交订单；部分适配器会返回 "resting"/"new"
            order_status = str(getattr(order, "status", "") or "").lower()
            if order_status not in valid_pending_statuses:
                continue

            if order.price is None:
                continue

            step = GRID_CONFIG['price_step'] if GRID_CONFIG and 'price_step' in GRID_CONFIG else 0.01
            price = normalize_price(order.price, step)
            side = str(getattr(order, "side", "") or "").lower()

            parsed_order_id = None
            raw_id = getattr(order, "order_id", None)
            if raw_id is not None and str(raw_id).strip():
                # 保留字符串 ID（PopDEX 等）；数值型也统一成 str，兼容 cancel_orders_by_ids
                parsed_order_id = str(raw_id).strip()

            if side in ["buy", "long"]:
                if price not in long_prices:
                    long_prices.append(price)
                if price not in long_price_to_ids:
                    long_price_to_ids[price] = []
                if parsed_order_id is not None:
                    long_price_to_ids[price].append(parsed_order_id)
            elif side in ["sell", "short"]:
                if price not in short_prices:
                    short_prices.append(price)
                if price not in short_price_to_ids:
                    short_price_to_ids[price] = []
                if parsed_order_id is not None:
                    short_price_to_ids[price].append(parsed_order_id)
            else:
                continue
        
        return sorted(long_prices), sorted(short_prices), long_price_to_ids, short_price_to_ids
    except NotImplementedError:
        # 如果适配器未实现，返回空数组
        return [], [], {}, {}
    except Exception as e:
        print(f"获取未成交订单失败: {e}")
        return [], [], {}, {}


def cancel_stale_order_ids(adapter, symbol, stale_seconds=5, cancel_probability=0.5):
    """随机取消未成交时间大于指定秒数的订单
    
    Args:
        adapter: 适配器实例
        symbol: 交易对符号
        stale_seconds: 未成交时间阈值（秒），默认5秒
        cancel_probability: 取消概率（0-1之间），默认0.5（50%）
    """
    try:
        open_orders = adapter.get_open_orders(symbol=symbol)
        stale_order_ids = []
        current_time = int(time.time() * 1000)  # 当前时间（毫秒）
        
        for order in open_orders:
            # 只处理未成交的订单
            if order.status in ["pending", "open", "partially_filled"]:
                if order.created_at:
                    # 计算未成交时间（毫秒）
                    elapsed_time = current_time - order.created_at
                    if elapsed_time > stale_seconds * 1000:  # 转换为毫秒
                        # 根据概率决定是否取消
                        if random.random() < cancel_probability:
                            try:
                                raw_id = getattr(order, "order_id", None)
                                if raw_id is not None and str(raw_id).strip():
                                    stale_order_ids.append(str(raw_id).strip())
                            except (ValueError, TypeError):
                                pass
        
        # 如果有需要取消的订单，执行批量撤单
        if stale_order_ids:
            print(f"随机取消未成交时间>{stale_seconds}秒的订单: {stale_order_ids} (概率: {cancel_probability*100}%)")
            try:
                if hasattr(adapter, 'cancel_orders_by_ids'):
                    adapter.cancel_orders_by_ids(order_id_list=stale_order_ids)
            except:
                pass
    except Exception:
        pass


def cancel_orders_by_prices(cancel_long, cancel_short, long_price_to_ids, short_price_to_ids, adapter, symbol=None):
    """根据价格列表撤单
    
    Args:
        cancel_long: 需要撤单的做多价格列表
        cancel_short: 需要撤单的做空价格列表
        long_price_to_ids: 做多价格到订单ID列表的字典映射
        short_price_to_ids: 做空价格到订单ID列表的字典映射
        adapter: 适配器实例
    """
    if not cancel_long and not cancel_short:
        return
    
    step = GRID_CONFIG['price_step'] if GRID_CONFIG and 'price_step' in GRID_CONFIG else 0.01
    cancel_long = normalize_price_list(cancel_long, step)
    cancel_short = normalize_price_list(cancel_short, step)
    # 根据价格映射获取订单ID
    all_order_ids = []
    for price in cancel_long:
        if price in long_price_to_ids:
            all_order_ids.extend(long_price_to_ids[price])
    for price in cancel_short:
        if price in short_price_to_ids:
            all_order_ids.extend(short_price_to_ids[price])
    
    if not all_order_ids:
        return
    
    # 批量撤单
    try:
        if hasattr(adapter, 'cancel_orders_by_ids'):
            adapter.cancel_orders_by_ids(order_id_list=all_order_ids)
        else:
            # 如果适配器没有批量撤单方法，逐个撤单
            for order_id in all_order_ids:
                try:
                    if symbol is not None:
                        adapter.cancel_order(order_id=str(order_id), symbol=symbol)
                    else:
                        adapter.cancel_order(order_id=str(order_id))
                except Exception as e:
                    print(f"撤单失败: order_id={order_id}, error={e}")
    except Exception as e:
        print(f"撤单异常: {e}")


def place_orders_by_prices(place_long, place_short, adapter, symbol, quantity):
    """根据价格列表下单
    
    Args:
        place_long: 需要下单的做多价格列表
        place_short: 需要下单的做空价格列表
        adapter: 适配器实例
        symbol: 交易对符号
        quantity: 订单数量
    """
    if not place_long and not place_short:
        return
    
    quantity_decimal = Decimal(str(quantity))
    exchange_name = str(EXCHANGE_CONFIG.get("exchange_name", "")).lower() if EXCHANGE_CONFIG else ""
    # Lighter: gtc；PopDEX/Ondo: postonly；其余 (hype 等): alo
    if exchange_name == "lighter":
        limit_tif = "gtc"
    elif exchange_name in ("popdex", "ondo", "ondoperp", "ondoperps"):
        limit_tif = "postonly"
    else:
        limit_tif = "alo"
    
    # 做多订单：buy
    for price in place_long:
        try:
            order = adapter.place_order(
                symbol=symbol,
                side="buy",
                order_type="limit",
                quantity=quantity_decimal,
                price=Decimal(str(price)),
                time_in_force=limit_tif,
                reduce_only=False
            )
            print(f"[下单成功][多单] 价格={price}, 数量={quantity_decimal}, 订单ID={getattr(order, 'order_id', None)}")
        except Exception as e:
            print(f"[下单失败][多单] 价格={price}, 数量={quantity_decimal}, 错误={e}")
    
    # 做空订单：sell
    for price in place_short:
        try:
            order = adapter.place_order(
                symbol=symbol,
                side="sell",
                order_type="limit",
                quantity=quantity_decimal,
                price=Decimal(str(price)),
                time_in_force=limit_tif,
                reduce_only=False
            )
            print(f"[下单成功][空单] 价格={price}, 数量={quantity_decimal}, 订单ID={getattr(order, 'order_id', None)}")
        except Exception as e:
            print(f"[下单失败][空单] 价格={price}, 数量={quantity_decimal}, 错误={e}")


def calculate_cancel_orders(target_long, target_short, current_long, current_short):
    """计算需要撤单的多空数组
    
    Args:
        target_long: 目标做多数组（应该存在的订单价格）
        target_short: 目标做空数组（应该存在的订单价格）
        current_long: 当前做多数组（实际存在的订单价格）
        current_short: 当前做空数组（实际存在的订单价格）
    
    Returns:
        (cancel_long, cancel_short): 需要撤单的做多数组和做空数组
    """
    step = GRID_CONFIG['price_step'] if GRID_CONFIG and 'price_step' in GRID_CONFIG else 0.01
    target_long = normalize_price_list(target_long, step)
    target_short = normalize_price_list(target_short, step)
    current_long = normalize_price_list(current_long, step)
    current_short = normalize_price_list(current_short, step)

    # 将目标数组转换为集合，便于查找
    target_long_set = set(target_long)
    target_short_set = set(target_short)
    
    # 撤单做多数组：在当前做多数组中，但不在目标做多数组中的价格
    cancel_long = [price for price in current_long if price not in target_long_set]
    
    # 撤单做空数组：在当前做空数组中，但不在目标做空数组中的价格
    cancel_short = [price for price in current_short if price not in target_short_set]
    
    return sorted(cancel_long), sorted(cancel_short)


def calculate_place_orders(target_long, target_short, current_long, current_short):
    """计算需要下单的多空数组
    
    Args:
        target_long: 目标做多数组（应该存在的订单价格）
        target_short: 目标做空数组（应该存在的订单价格）
        current_long: 当前做多数组（实际存在的订单价格）
        current_short: 当前做空数组（实际存在的订单价格）
    
    Returns:
        (place_long, place_short): 需要下单的做多数组和做空数组
    """
    step = GRID_CONFIG['price_step'] if GRID_CONFIG and 'price_step' in GRID_CONFIG else 0.01
    target_long = normalize_price_list(target_long, step)
    target_short = normalize_price_list(target_short, step)
    current_long = normalize_price_list(current_long, step)
    current_short = normalize_price_list(current_short, step)

    # 将当前数组转换为集合，便于查找
    current_long_set = set(current_long)
    current_short_set = set(current_short)
    
    # 下单做多数组：在目标做多数组中，但不在当前做多数组中的价格
    place_long = [price for price in target_long if price not in current_long_set]
    
    # 下单做空数组：在目标做空数组中，但不在当前做空数组中的价格
    place_short = [price for price in target_short if price not in current_short_set]
    
    return sorted(place_long), sorted(place_short)


def filter_orders_by_min_distance(place_long, place_short, current_price, min_distance):
    """过滤与当前价格过近的下单价格。"""
    if min_distance <= 0:
        return place_long, place_short

    filtered_long = [p for p in place_long if abs(float(current_price) - float(p)) >= min_distance]
    filtered_short = [p for p in place_short if abs(float(current_price) - float(p)) >= min_distance]
    return filtered_long, filtered_short


def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: Optional[str] = None) -> bool:
    """发送文本到 Telegram。parse_mode 可选 'HTML' 或 'Markdown' 以保留格式。"""
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram 发送失败: {e}")
        return False


def try_send_balance_to_telegram(adapter, exchange_name: str) -> None:
    """若开启 TG 且到达间隔，则获取余额并按配置格式发送到 Telegram。"""
    global _LAST_BALANCE_SENT_AT
    cfg = TELEGRAM_CONFIG or {}
    if not cfg.get("enable", False):
        return
    interval = int(cfg.get("interval_seconds", 3600))
    if interval <= 0:
        return
    now = time.time()
    if now - _LAST_BALANCE_SENT_AT < interval:
        return
    bot_token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()
    if not bot_token or not chat_id:
        return
    try:
        balance = adapter.get_balance()
        total = float(balance.total_balance) if balance else 0.0
        position_val = getattr(balance, "position_value", None)
        if position_val is not None:
            position_str = f"{float(position_val):.1f}"
        else:
            position_str = "0"
    except Exception as e:
        print(f"获取余额失败(Telegram): {e}")
        return
    fmt = cfg.get("message_format", "[{exchange}余额] {balance}U").strip()
    exchange_display = (exchange_name or "exchange").upper()
    text = fmt.format(
        exchange=exchange_display,
        balance=f"{total:.1f}",
        position_value=position_str,
    )
    if send_telegram_message(bot_token, chat_id, text):
        _LAST_BALANCE_SENT_AT = now

    if not cfg.get("send_positions", False):
        return
    if not hasattr(adapter, "get_positions_table_data"):
        return
    try:
        rows = adapter.get_positions_table_data()
    except Exception as e:
        print(f"获取持仓表格失败(Telegram): {e}")
        return
    if not rows:
        return
    table_text = format_positions_table(rows, exchange_display)
    if table_text:
        send_telegram_message(bot_token, chat_id, table_text, parse_mode="HTML")


def format_positions_table(rows: List[Dict[str, Any]], exchange_name: str) -> str:
    """将持仓列表格式化为等宽表格，便于 TG 展示。使用 <pre> 保持对齐。"""
    if not rows:
        return ""
    col = {"coin": 10, "size": 12, "liq": 12, "posval": 12}

    def _str(x: Any, w: int) -> str:
        s = str(x) if x is not None and x != "" else "-"
        return (s[: w - 1] + "…") if len(s) > w else s.ljust(w)

    def _num(x: Any, w: int) -> str:
        if x == "-" or x is None or x == "":
            return "-".ljust(w)
        try:
            v = float(x)
            s = ("%.4f" % v).rstrip("0").rstrip(".")
            return s.rjust(w)
        except Exception:
            return _str(x, w)

    header = (
        _str("币种", col["coin"])
        + _str("数量", col["size"])
        + _str("清算", col["liq"])
        + _str("仓位", col["posval"])
    )
    lines = [f"[{exchange_name}仓位]", "", header]
    for r in rows:
        coin = r.get("coin", "")
        size = r.get("size", 0)
        liq = r.get("liquidation_px", "-")
        posval = r.get("position_value", "-")
        line = (
            _str(coin, col["coin"])
            + _num(size, col["size"])
            + _num(liq, col["liq"])
            + _num(posval, col["posval"])
        )
        lines.append(line)
    def _escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body = "\n".join(_escape(line) for line in lines)
    return f"<pre>{body}</pre>"


def close_position_if_exists(adapter, symbol):
    """检查持仓，如果有持仓则市价平仓
    
    注意: StandX 适配器的持仓查询接口可能未实现，此功能可能无法使用
    
    Args:
        adapter: 适配器实例
        symbol: 交易对符号
    """
    try:
        positions = adapter.get_positions(symbol)
        # get_positions 返回列表，取第一个持仓
        position = positions[0] if positions else None
        if position and position.size != Decimal("0"):
            print(f"检测到持仓: {position.size} {position.side}")
            print("取消所有未成交订单...")
            adapter.cancel_all_orders(symbol=symbol)
            # 然后市价平仓
            print("市价平仓中...")
            adapter.close_position(symbol, order_type="market")
            print("平仓完成")
        # 如果 position 为 None，说明 StandX 适配器的持仓查询接口可能未实现
    except Exception as e:
        # 如果持仓查询失败，静默处理（StandX 可能没有持仓查询接口）
        pass


def current_position(adapter, symbol):
    """获取当前币种持仓（返回签名持仓、原始持仓对象）。"""
    try:
        positions = adapter.get_positions(symbol)
        if not positions:
            return Decimal("0"), None
        position = positions[0]
        size = Decimal(str(position.size))
        if str(position.side).lower() == "short":
            size = -abs(size)
        else:
            size = abs(size)
        return size, position
    except Exception as e:
        print(f"当前持仓查询失败: {e}")
        return Decimal("0"), None


def run_strategy_cycle(adapter):
    """执行一次策略循环
    
    Args:
        adapter: 适配器实例
    """
    price_info = adapter.get_ticker(SYMBOL)
    last_price = price_info.get('last_price') or price_info.get('mid_price') or price_info.get('mark_price')
    print(f"{SYMBOL} 价格: {last_price:.2f}")

    signed_position, position_obj = current_position(adapter, SYMBOL)
    if position_obj is None or signed_position == Decimal("0"):
        print("当前持仓: 无")
    else:
        print(
            f"当前持仓: side={position_obj.side}, size={position_obj.size}, "
            f"signed_size={signed_position}"
        )

    order_quantity = Decimal(str(GRID_CONFIG.get('order_quantity', 1)))
    max_position_multiplier = GRID_CONFIG.get('max_position_multiplier', 3)
    mode = str(GRID_CONFIG.get('mode', 'neutral')).strip().lower()
    # 贴市价过滤：直接用 price_step 作为最小挂单距离
    min_distance = float(GRID_CONFIG['price_step'])

    long_grid, short_grid = generate_grid_arrays(
        last_price, 
        GRID_CONFIG['price_step'], 
        GRID_CONFIG['grid_count'],
        signed_position_size=signed_position,
        order_quantity=order_quantity,
        max_position_multiplier=max_position_multiplier,
        lower_price=GRID_CONFIG.get('lower_price'),
        upper_price=GRID_CONFIG.get('upper_price'),
        mode=mode,
    )
    max_position = order_quantity * Decimal(str(max_position_multiplier))
    print(
        f"网格动态分配: mode={mode}, signed_position={signed_position}, "
        f"max_position={max_position}, long_count={len(long_grid)}, short_count={len(short_grid)}"
    )
    print(f"做多数组: {long_grid}")
    print(f"做空数组: {short_grid}")
    
    # 获取未成交订单数组和价格到订单ID的映射
    long_pending, short_pending, long_price_to_ids, short_price_to_ids = get_pending_orders_arrays(adapter, SYMBOL)
    print(f"当前做多数组: {long_pending}")
    print(f"当前做空数组: {short_pending}")

    # 计算需要撤单的数组
    cancel_long, cancel_short = calculate_cancel_orders(
        long_grid, short_grid, long_pending, short_pending
    )
    print(f"撤单做多数组: {cancel_long}")
    print(f"撤单做空数组: {cancel_short}")
    
    # 执行撤单
    cancel_orders_by_prices(
        cancel_long, cancel_short, long_price_to_ids, short_price_to_ids, adapter, SYMBOL
    )
    
    # 计算需要下单的数组
    place_long, place_short = calculate_place_orders(
        long_grid, short_grid, long_pending, short_pending
    )

    place_long, place_short = filter_orders_by_min_distance(
        place_long, place_short, last_price, min_distance
    )

    print(f"下单做多数组: {place_long}")
    print(f"下单做空数组: {place_short}")
    
    # 执行下单
    place_orders_by_prices(
        place_long, place_short, adapter, SYMBOL, GRID_CONFIG.get('order_quantity', 0.001)
    )
    


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="网格交易策略脚本（支持 StandX / GRVT / Hype / Lighter / PopDEX / Ondo）"
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config.yaml',
        help='指定配置文件路径（默认: config.yaml）'
    )
    parser.add_argument(
        '-e', '--exchange',
        type=str,
        required=True,
        help='交易所名称，例如: standx、grvt、hype、lighter、popdex 或 ondo'
    )
    args = parser.parse_args()
    
    # 加载配置文件
    try:
        print(f"加载配置文件: {args.config}")
        print(f"使用交易所: {args.exchange}")
        initialize_config(args.config, active_exchange_override=args.exchange)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        sys.exit(1)
    
    try:
        adapter = create_adapter(EXCHANGE_CONFIG)
        adapter.connect()
        
        sleep_interval = GRID_CONFIG.get('sleep_interval', 60)
        
        print("策略开始运行，按 Ctrl+C 停止...")
        print(f"休眠间隔: {sleep_interval} 秒\n")
        
        exchange_name = (EXCHANGE_CONFIG or {}).get("exchange_name", args.exchange) or ""
        while True:
            try:
                run_strategy_cycle(adapter)
                try_send_balance_to_telegram(adapter, exchange_name)
                print(f"\n等待 {sleep_interval} 秒后继续...\n")
                time.sleep(sleep_interval)
            except KeyboardInterrupt:
                print("\n\n策略已停止")
                break
            except Exception as e:
                print(f"策略循环错误: {e}")
                print(f"等待 {sleep_interval} 秒后重试...\n")
                time.sleep(sleep_interval)
        
    except Exception as e:
        print(f"错误: {e}")
        return None


if __name__ == "__main__":
    main()
