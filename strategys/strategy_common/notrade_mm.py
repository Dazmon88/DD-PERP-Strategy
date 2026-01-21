#!/usr/bin/env python3
"""
StandX 策略脚本 - 获取 BTC 价格
"""
import sys
import os
import yaml
import time
import random
import argparse
from decimal import Decimal

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
    if exchange_name.lower() == "grvt":
        # GRVT 使用 BTC_USDT_Perp 格式
        # 将 "BTC-USDT" 转换为 "BTC_USDT_Perp"
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            return f"{base}_{quote}_Perp"
        return symbol
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
    global EXCHANGE_CONFIG, SYMBOL, GRID_CONFIG, RISK_CONFIG, CANCEL_STALE_ORDERS_CONFIG
    
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
    raw_symbol = EXCHANGE_CONFIG.pop('symbol', None)
    
    if not raw_symbol:
        raise ValueError(f"配置错误: exchanges.{active_exchange_name} 中缺少 symbol 配置")
    
    exchange_name = EXCHANGE_CONFIG.get('exchange_name', active_exchange_name)
    # 根据交易所类型转换交易对格式
    SYMBOL = convert_symbol_format(raw_symbol, exchange_name)
    
    GRID_CONFIG = config['grid']
    RISK_CONFIG = config.get('risk', {})
    CANCEL_STALE_ORDERS_CONFIG = config.get('cancel_stale_orders', {})


def generate_grid_arrays(current_price, price_step, grid_count, price_spread):
    """根据当前价格和价格间距生成做多数组和做空数组，过滤超过当前价格上下1%的价格"""
    if price_step <= 0:
        raise ValueError("price_step 必须大于 0")
    if grid_count < 0:
        raise ValueError("grid_count 必须大于等于 0")
    if price_spread < 0:
        raise ValueError("price_spread 必须大于等于 0")
    
    # 计算价格上下限（当前价格的上下1%）
    price_upper_limit = current_price * 1.01  # 上限：当前价格 +1%
    price_lower_limit = current_price * 0.99   # 下限：当前价格 -1%
    
    # 计算 bid 和 ask 价格
    bid_price = current_price - price_spread
    ask_price = current_price + price_spread
    
    # 将 bid 价格向下取整到最近的 price_step 倍数
    bid_base = int(bid_price / price_step) * price_step
    
    # 将 ask 价格向上取整到最近的 price_step 倍数
    ask_base = int((ask_price + price_step - 1) / price_step) * price_step
    
    # 做多数组：从 bid_base 向下 grid_count 个（包括 bid_base）
    long_grid = []
    for i in range(grid_count):
        price = bid_base - i * price_step
        # 过滤：做多价格不能低于当前价格的1%（即不能低于 price_lower_limit）
        if price >= price_lower_limit:
            long_grid.append(price)
    long_grid = sorted(long_grid)
    
    # 做空数组：从 ask_base 向上 grid_count 个（包括 ask_base）
    short_grid = []
    for i in range(grid_count):
        price = ask_base + i * price_step
        # 过滤：做空价格不能超过当前价格的1%（即不能高于 price_upper_limit）
        if price <= price_upper_limit:
            short_grid.append(price)
    short_grid = sorted(short_grid)
    
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
        
        for order in open_orders:
            # 只处理未成交的订单（状态为 pending, open, partially_filled）
            if order.status in ["pending", "open", "partially_filled"]:
                if order.price is not None:
                    price = int(float(order.price))
                    try:
                        order_id = int(order.order_id)
                    except (ValueError, TypeError):
                        continue  # 跳过无效的订单ID
                    
                    if order.side in ["buy", "long"]:
                        if price not in long_prices:
                            long_prices.append(price)
                        if price not in long_price_to_ids:
                            long_price_to_ids[price] = []
                        long_price_to_ids[price].append(order_id)
                    elif order.side in ["sell", "short"]:
                        if price not in short_prices:
                            short_prices.append(price)
                        if price not in short_price_to_ids:
                            short_price_to_ids[price] = []
                        short_price_to_ids[price].append(order_id)
        
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
                                order_id = int(order.order_id)
                                stale_order_ids.append(order_id)
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


def cancel_orders_by_prices(cancel_long, cancel_short, long_price_to_ids, short_price_to_ids, adapter):
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
                    adapter.cancel_order(order_id=str(order_id))
                except:
                    pass
    except:
        pass


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
    
    # 做多订单：buy
    for price in place_long:
        try:
            order = adapter.place_order(
                symbol=symbol,
                side="buy",
                order_type="limit",
                quantity=quantity_decimal,
                price=Decimal(str(price)),
                time_in_force="gtc",
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
                time_in_force="gtc",
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
    # 将当前数组转换为集合，便于查找
    current_long_set = set(current_long)
    current_short_set = set(current_short)
    
    # 下单做多数组：在目标做多数组中，但不在当前做多数组中的价格
    place_long = [price for price in target_long if price not in current_long_set]
    
    # 下单做空数组：在目标做空数组中，但不在当前做空数组中的价格
    place_short = [price for price in target_short if price not in current_short_set]
    
    return sorted(place_long), sorted(place_short)


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


def calculate_dynamic_price_spread(adx, current_price, default_spread, adx_threshold, adx_max=60):
    """根据 ADX 值动态计算 price_spread
    
    Args:
        adx: ADX 指标值
        current_price: 当前价格
        default_spread: 默认 price_spread
        adx_threshold: ADX 阈值，低于此值使用默认值（通常为25）
        adx_max: ADX 最大值，超过此值按此值处理（默认60）
    
    Returns:
        int: 计算后的 price_spread
    """
    max_spread = current_price * 0.01  # 最大为价格的1%
    
    if adx is not None:
        print(f"ADX(5m): {adx:.2f}")
        # ADX <= threshold 时使用默认值
        if adx <= adx_threshold:
            price_spread = default_spread
        else:
            # 超过 60 按 60 处理
            effective_adx = min(adx, adx_max)
            # ADX 在 [threshold, 60] 范围内映射到 [默认值, 最大值]
            ratio = (effective_adx - adx_threshold) / (adx_max - adx_threshold)  # ADX 25-60 映射到 0-1
            dynamic_spread = default_spread + ratio * (max_spread - default_spread)
            price_spread = int(min(dynamic_spread, max_spread))
        print(f"动态 price_spread: {price_spread} (默认: {default_spread}, 最大: {int(max_spread)})")
        return price_spread
    else:
        print(f"ADX(5m): 获取失败，使用默认 price_spread: {default_spread}")
        return default_spread


def run_strategy_cycle(adapter):
    """执行一次策略循环
    
    Args:
        adapter: 适配器实例
    """
    price_info = adapter.get_ticker(SYMBOL)
    last_price = price_info.get('last_price') or price_info.get('mid_price') or price_info.get('mark_price')
    print(f"{SYMBOL} 价格: {last_price:.2f}")

    # 获取 ADX 指标并动态调整 price_spread
    default_spread = GRID_CONFIG['price_spread']
    
    if RISK_CONFIG.get('enable', False):
        indicator_tool = IndicatorTool()
        adx_symbol = convert_symbol_for_adx(SYMBOL)
        adx = indicator_tool.get_adx(adx_symbol, "5m", period=14)
        adx_threshold = RISK_CONFIG.get('adx_threshold', 25)
        adx_max = RISK_CONFIG.get('adx_max', 60)
        price_spread = calculate_dynamic_price_spread(adx, last_price, default_spread, adx_threshold, adx_max)
    else:
        price_spread = default_spread
    
    long_grid, short_grid = generate_grid_arrays(
        last_price, 
        GRID_CONFIG['price_step'], 
        GRID_CONFIG['grid_count'],
        price_spread
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
        cancel_long, cancel_short, long_price_to_ids, short_price_to_ids, adapter
    )

    # 随机取消未成交时间过长的订单
    if CANCEL_STALE_ORDERS_CONFIG.get('enable', False):
        stale_seconds = CANCEL_STALE_ORDERS_CONFIG.get('stale_seconds', 5)
        cancel_probability = CANCEL_STALE_ORDERS_CONFIG.get('cancel_probability', 0.5)
        cancel_stale_order_ids(adapter, SYMBOL, stale_seconds, cancel_probability)
    
    # 计算需要下单的数组
    place_long, place_short = calculate_place_orders(
        long_grid, short_grid, long_pending, short_pending
    )
    print(f"下单做多数组: {place_long}")
    print(f"下单做空数组: {place_short}")
    
    # 执行下单
    place_orders_by_prices(
        place_long, place_short, adapter, SYMBOL, GRID_CONFIG.get('order_quantity', 0.001)
    )
    # 检查持仓，如果有持仓则市价平仓
    close_position_if_exists(adapter, SYMBOL)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='网格交易策略脚本（支持 StandX 和 GRVT）')
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
        help='指定要使用的交易所名称（必需），例如: standx 或 grvt'
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
        
        while True:
            try:
                run_strategy_cycle(adapter)
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
