"""
打开指定环境并访问页面
"""

import sys
import csv
import os
import time
import json
import requests
from playwright.sync_api import sync_playwright


def start(envId, uniqueId):
    """启动浏览器配置文件，返回 CDP URL"""
    if envId and envId.strip():
        data = {"envId": envId}
    elif uniqueId:
        data = {"uniqueId": uniqueId}
    else:
        print("错误: 必须设置 env_id 或 unique_id 之一")
        return None
    
    response = requests.post("http://localhost:40000/api/env/start", json=data).json()
    
    if response["code"] != 0:
        print(f"启动失败: {response.get('msg', '')}")
        return None

    port = response["data"]["debugPort"]
    return "http://127.0.0.1:" + port


def get_url(symbol, platform="nado"):
    """根据交易对和平台生成URL"""
    symbol = symbol.upper()
    if platform == "variational":
        return f"https://omni.variational.io/perpetual/{symbol}"
    elif platform == "nado":
        return f"https://app.nado.xyz/perpetuals?market={symbol}USDT0"
    else:
        raise ValueError(f"不支持的平台: {platform}")


def open_page(playwright, env_id, url):
    """打开指定环境并访问页面，返回页面对象"""
    cdp_url = start(env_id, None)
    if cdp_url is None:
        return None
    
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto(url)
    return page


def load_config(csv_file="config.csv"):
    """从CSV文件加载配置"""
    configs = []
    csv_path = os.path.join(os.path.dirname(__file__), csv_file)
    
    if not os.path.exists(csv_path):
        print(f"配置文件不存在: {csv_path}")
        return configs
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 跳过空行
            if not row.get('nado_env_id') or not row.get('variational_env_id') or not row.get('symbol'):
                continue
            configs.append({
                'nado_env_id': row['nado_env_id'].strip(),
                'variational_env_id': row['variational_env_id'].strip(),
                'symbol': row['symbol'].strip().upper(),
                'size': row.get('size', '').strip(),
                'price_offset': row.get('price_offset', '-5').strip()  # 默认-5
            })
    
    return configs


def get_product_id_cache_file():
    """获取product_id缓存文件路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'product_id_cache.json')


def load_product_id_cache():
    """加载product_id缓存"""
    cache_file = get_product_id_cache_file()
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_product_id_cache(cache):
    """保存product_id缓存"""
    cache_file = get_product_id_cache_file()
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"  警告: 无法保存缓存文件: {e}")


def get_product_id_from_api(symbol, product_type="perp"):
    """
    从API获取product_id
    
    Args:
        symbol: 交易对符号（如BTC）
        product_type: 产品类型，"spot" 或 "perp"，默认"perp"
    
    Returns:
        int: product_id，如果获取失败返回None
    """
    try:
        base_url = "https://gateway.prod.nado.xyz/v1/query"
        params_symbols = {
            "type": "symbols",
            "product_type": product_type
        }
        
        response = requests.get(base_url, params=params_symbols, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # API响应结构: {'status': 'success', 'data': {'symbols': {'BTC-PERP': {...}}}}
        symbols_dict = data.get('data', {}).get('symbols', {})
        
        if not symbols_dict:
            return None
        
        # 查找对应的交易对，格式是 'BTC-PERP'
        symbol_upper = symbol.upper()
        search_key = f"{symbol_upper}-PERP" if product_type == "perp" else f"{symbol_upper}-SPOT"
        
        symbol_info = symbols_dict.get(search_key)
        if not symbol_info:
            return None
        
        product_id = symbol_info.get('product_id')
        return product_id
        
    except requests.exceptions.RequestException:
        return None
    except (ValueError, KeyError, TypeError):
        return None


def get_product_id(symbol, product_type="perp"):
    """
    获取product_id（带缓存）
    
    Args:
        symbol: 交易对符号（如BTC）
        product_type: 产品类型，"spot" 或 "perp"，默认"perp"
    
    Returns:
        int: product_id，如果获取失败返回None
    """
    symbol_upper = symbol.upper()
    
    # 先检查缓存
    cache = load_product_id_cache()
    cache_key = f"{symbol_upper}_{product_type}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    # 缓存中没有，调用API
    product_id = get_product_id_from_api(symbol, product_type)
    
    if product_id:
        cache[cache_key] = product_id
        save_product_id_cache(cache)
        return product_id
    else:
        print(f"交易对 {symbol} ({product_type}) 不存在")
        return None


def get_price_from_api(symbol, product_type="perp"):
    """
    通过API获取交易对价格
    
    Args:
        symbol: 交易对符号（如BTC）
        product_type: 产品类型，"spot" 或 "perp"，默认"perp"
    
    Returns:
        dict: 包含bid、ask、mid价格的字典，格式: {'bid': int, 'ask': int, 'mid': int}
              价格是整数（乘以100后的值，去掉小数点），如果获取失败返回None
    """
    try:
        base_url = "https://gateway.prod.nado.xyz/v1/query"
        
        # 步骤1: 获取product_id（带缓存）
        product_id = get_product_id(symbol, product_type)
        
        if not product_id:
            return None
        
        # 步骤2: 使用product_id获取market_price（带重试）
        params_price = {
            "type": "market_price",
            "product_id": product_id
        }
        
        max_retries = 10
        price_data = None
        
        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params_price, timeout=10)
                
                # 如果是429错误，等待后重试
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 1
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"API请求失败: 429 Too Many Requests (已重试{max_retries}次)")
                        return None
                
                response.raise_for_status()
                price_data = response.json()
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    time.sleep(wait_time)
                else:
                    print(f"API请求失败: {e}")
                    return None
        
        if not price_data:
            return None
        
        # 提取价格，API返回格式: {'data': {'bid_x18': '...', 'ask_x18': '...'}}
        # x18表示18位精度，需要除以10^18
        if isinstance(price_data, dict):
            data_section = price_data.get('data', price_data)
            
            bid_x18 = data_section.get('bid_x18')
            ask_x18 = data_section.get('ask_x18')
            
            result = {}
            bid = None
            ask = None
            
            if bid_x18:
                bid = float(bid_x18) / (10 ** 18)
                bid_int = int(round(bid * 100))
                result['bid'] = bid_int
            
            if ask_x18:
                ask = float(ask_x18) / (10 ** 18)
                ask_int = int(round(ask * 100))
                result['ask'] = ask_int
            
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2
                mid_int = int(round(mid * 100))
                result['mid'] = mid_int
            
            if result:
                return result
        
        print(f"API响应中未找到价格信息")
        return None
        
    except (ValueError, KeyError, TypeError) as e:
        print(f"  解析API响应失败: {e}")
        return None


def show_menu():
    """显示菜单"""
    print("\n" + "=" * 50)
    print("菜单")
    print("=" * 50)
    print("1. 做多Nado做空Variational")
    print("2. 做空Nado做多Variational")
    print("按 Ctrl+C 退出")
    print("=" * 50)


def click_limit_button(page):
    """
    点击页面上的Limit按钮
    
    Args:
        page: Playwright页面对象
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找Limit按钮
        button = page.query_selector('button:has-text("Limit")')
        if button:
            button.click()
            return True
        return False
    except Exception as e:
        print(f"Limit按钮错误: {e}")
        return False


def click_long_tab_button(page):
    """
    点击做多标签按钮（Buy/Long tab）
    
    Args:
        page: Playwright页面对象
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找做多标签按钮
        button = page.query_selector('button:has-text("Buy/Long")[role="tab"]')
        if button:
            button.click()
            return True
        return False
    except Exception as e:
        print(f"做多标签按钮错误: {e}")
        return False


def click_short_tab_button(page):
    """
    点击做空标签按钮（Sell/Short tab）
    
    Args:
        page: Playwright页面对象
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找做空标签按钮
        button = page.query_selector('button:has-text("Sell/Short")[role="tab"]')
        if button:
            button.click()
            return True
        return False
    except Exception as e:
        print(f"做空标签按钮错误: {e}")
        return False


def click_submit_long_button(page, symbol):
    """
    点击提交做多按钮（Buy/Long BTC）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找提交做多按钮
        button = page.query_selector(f'button[type="submit"]:has-text("Buy/Long {symbol}")')
        if button:
            button.click()
            return True
        return False
    except Exception as e:
        print(f"提交做多按钮错误: {e}")
        return False


def click_submit_short_button(page, symbol):
    """
    点击提交做空按钮（Sell/Short BTC）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找提交做空按钮
        button = page.query_selector(f'button[type="submit"]:has-text("Sell/Short {symbol}")')
        if button:
            button.click()
            return True
        return False
    except Exception as e:
        print(f"提交做空按钮错误: {e}")
        return False


def click_open_orders_button(page, symbol):
    """
    点击未成交订单按钮（Open Orders）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号（未使用，保留兼容性）
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找Open Orders按钮
        selectors = [
            'button[role="tab"]:has-text("Open Orders")',
            'button:has-text("Open Orders")',
            'button[id*="open_orders"]'
        ]
        
        for selector in selectors:
            button = page.query_selector(selector)
            if button:
                button_text = button.inner_text()
                if "Open Orders" in button_text:
                    button.click()
                    return True
        return False
    except Exception as e:
        print(f"未成交订单按钮错误: {e}")
        return False


def cancel_all_orders(page, symbol):
    """
    取消所有未成交订单
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
    
    Returns:
        bool: 是否成功取消
    """
    try:
        # 先点击未成交订单按钮
        if not click_open_orders_button(page, symbol):
            print("无法打开订单列表，取消订单失败")
            return False
        
        page.wait_for_timeout(100)
        
        # 查找取消按钮
        cancel_button = page.query_selector('button:has-text("Cancel all")')
        if cancel_button:
            # 检查按钮是否可用
            is_disabled = cancel_button.get_attribute('disabled') is not None
            if is_disabled:
                # 按钮不可用，说明没有订单
                return True
            
            # 尝试点击，如果按钮不可用则忽略
            try:
                cancel_button.click(timeout=2000)
                page.wait_for_timeout(100)
                return True
            except Exception:
                # 点击失败（可能是按钮不可用），视为没有订单
                return True
        return True  # 没有订单也算成功
    except Exception as e:
        # 出错也视为成功（可能是没有订单）
        return True


def check_order_status(page, order_price, symbol):
    """
    检查订单是否成交
    
    Args:
        page: Playwright页面对象
        order_price: 订单价格（用于匹配订单）
        symbol: 交易对符号
    
    Returns:
        dict: 订单信息，包含是否成交、filled、total等，如果未找到订单返回None
    """
    try:
        import re
        
        # 查找所有订单行
        rows = page.query_selector_all('div.flex.items-center.border-overlay-divider')
        
        # 将订单价格转换为数字，移除小数点，用于匹配
        order_price_num = float(order_price)
        order_price_int = int(order_price_num)
        
        # 尝试多种价格格式匹配
        price_patterns = [
            str(order_price_int),  # 90602
            f"{order_price_int:,}",  # 90,602
            f"{order_price_num:.0f}",  # 90602.0
            f"{order_price_num:.2f}",  # 90602.00
        ]
        
        for row in rows:
            row_text = row.inner_text()
            
            # 检查这一行是否包含我们的订单价格（移除逗号后比较）
            row_text_no_comma = row_text.replace(',', '')
            
            # 尝试匹配价格
            price_matched = False
            for pattern in price_patterns:
                if pattern.replace(',', '') in row_text_no_comma:
                    price_matched = True
                    break
            
            if price_matched:
                # 查找Filled/Total列（min-w-28 max-w-40 flex-1）
                # Filled和Total分别在两个div中
                filled_total_div = row.query_selector('div.min-w-28.max-w-40.flex-1')
                if filled_total_div:
                    # 获取所有子div
                    child_divs = filled_total_div.query_selector_all('div')
                    
                    filled = 0.0
                    total = 0.0
                    
                    # 第一个div包含filled（格式：0.00000 /）
                    if len(child_divs) >= 1:
                        filled_text = child_divs[0].inner_text().strip()
                        # 提取数字部分（移除 "/" 等）
                        filled_match = re.search(r'(\d+\.?\d*)', filled_text)
                        if filled_match:
                            filled = float(filled_match.group(1))
                    
                    # 第二个div包含total（格式：0.00150 BTC）
                    if len(child_divs) >= 2:
                        total_text = child_divs[1].inner_text().strip()
                        # 提取数字部分（移除 "BTC" 等）
                        total_match = re.search(r'(\d+\.?\d*)', total_text)
                        if total_match:
                            total = float(total_match.group(1))
                    
                    # 如果正则表达式方法失败，尝试从row_text中提取
                    if total == 0:
                        # 尝试从row_text中查找 "0.00000 / 0.00150" 格式
                        match = re.search(r'(\d+\.?\d*)\s*/\s*(\d+\.?\d*)', row_text)
                        if match:
                            filled = float(match.group(1))
                            total = float(match.group(2))
                    
                    if total > 0:
                        fill_ratio = filled / total
                        is_filled = fill_ratio >= 1.0
                        
                        # 提取实际显示的价格用于调试
                        price_elem = row.query_selector('div.min-w-30.max-w-40.flex-1')
                        actual_price = price_elem.inner_text().strip() if price_elem else str(order_price)
                        
                        return {
                            'found': True,
                            'filled': filled,
                            'total': total,
                            'fill_ratio': fill_ratio,
                            'is_filled': is_filled,
                            'symbol': symbol,
                            'price': order_price,
                            'actual_price': actual_price
                        }
        
        return None  # 未找到订单
    except Exception as e:
        print(f"检查订单状态时出错: {e}")
        return None


def monitor_order_fill(page, symbol, initial_position, check_interval=0.5, max_wait_time=30, retry_timeout=30):
    """
    监控订单是否成交（通过比较持仓变化）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
        initial_position: 初始持仓信息
        check_interval: 检查间隔（秒）
        max_wait_time: 最大等待时间（秒）
        retry_timeout: 重试超时时间（秒），如果在这个时间内未成交，返回None表示需要重新下单
    
    Returns:
        bool: 是否完全成交
        None: 如果retry_timeout内未成交，需要重新下单
    """
    start_time = time.time()
    print(f"监控订单是否成交")
    while True:
        elapsed_time = time.time() - start_time
        
        if elapsed_time >= retry_timeout:
            return None
        
        if elapsed_time > max_wait_time:
            return False
        
        try:
            current_position = get_nado_position(page, symbol)
            if current_position != initial_position:
                print(f"订单已成交: {initial_position} -> {current_position}")
                return True
        except Exception:
            pass
        
        if elapsed_time < max_wait_time:
            page.wait_for_timeout(int(check_interval * 1000))
        else:
            break
    
    return False


def fill_order_form(page, price, size):
    """
    填写订单表单：价格和大小
    
    Args:
        page: Playwright页面对象
        price: 价格（字符串或数字）
        size: 大小（字符串或数字）
    
    Returns:
        bool: 是否成功填写
    """
    try:
        price_input = page.query_selector('#limitPrice')
        if not price_input:
            print("未找到价格输入框")
            return False
        price_input.fill(str(price))
        
        size_input = page.query_selector('#size')
        if not size_input:
            print("未找到大小输入框")
            return False
        size_input.fill(str(size))
        
        return True
    except Exception as e:
        print(f"填写订单表单时出错: {e}")
        return False


def click_short_button_variational(page):
    """
    在variational页面点击做空按钮
    
    Args:
        page: Playwright页面对象
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 通过data-testid="bid-price-display"定位做空按钮（更精准，支持中英文）
        span = page.query_selector('span[data-testid="bid-price-display"]')
        if span:
            clicked = span.evaluate('el => { const btn = el.closest("button"); if (btn) { btn.click(); return true; } return false; }')
            if clicked:
                return True
        return False
    except Exception as e:
        print(f"Variational做空按钮错误: {e}")
        return False


def click_long_button_variational(page):
    """
    在variational页面点击做多按钮
    
    Args:
        page: Playwright页面对象
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 通过data-testid="ask-price-display"定位做多按钮（更精准，支持中英文）
        span = page.query_selector('span[data-testid="ask-price-display"]')
        if span:
            clicked = span.evaluate('el => { const btn = el.closest("button"); if (btn) { btn.click(); return true; } return false; }')
            if clicked:
                return True
        return False
    except Exception as e:
        print(f"Variational做多按钮错误: {e}")
        return False


def fill_quantity_variational(page, size):
    """
    在variational页面输入仓位大小
    
    Args:
        page: Playwright页面对象
        size: 仓位大小
    
    Returns:
        bool: 是否成功输入
    """
    try:
        # 精准查找数量输入框
        input_elem = page.query_selector('input[data-testid="quantity-input"]')
        if input_elem:
            input_elem.fill(str(size))
            return True
        return False
    except Exception as e:
        print(f"输入仓位大小错误: {e}")
        return False


def click_submit_variational(page, symbol):
    """
    在variational页面点击确认按钮
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
    
    Returns:
        bool: 是否成功点击
    """
    try:
        # 精准查找确认按钮
        button = page.query_selector('button[data-testid="submit-button"]')
        if button:
            button_text = button.inner_text()
            if symbol in button_text or "买" in button_text or "卖" in button_text:
                button.click()
                return True
        return False
    except Exception as e:
        print(f"Variational确认按钮错误: {e}")
        return False


def execute_variational_short(pages, configs):
    """
    在variational页面执行做空操作
    
    Args:
        pages: 页面字典
        configs: 配置列表
    """
    if not pages or 'variational' not in pages:
        print("错误: 未找到variational页面")
        return False
    
    variational_page = pages['variational']
    config = configs[0]
    symbol = config['symbol']
    size = config.get('size', '0.0001')
    
    print(f"\n开始执行Variational做空操作 - {symbol}")
    print("=" * 50)
    
    # 点击做空按钮
    print("步骤1: 点击做空按钮...")
    if not click_short_button_variational(variational_page):
        print("无法继续，做空按钮点击失败")
        return False
    variational_page.wait_for_timeout(100)
    
    # 输入仓位大小
    print("\n步骤2: 输入仓位大小...")
    if not fill_quantity_variational(variational_page, size):
        print("无法继续，输入仓位大小失败")
        return False
    variational_page.wait_for_timeout(100)
    
    # 点击确认按钮
    print("\n步骤3: 点击确认按钮...")
    if click_submit_variational(variational_page, symbol):
        print(f"\n✅ Variational做空订单已提交: {symbol}, 大小: {size}")
        return True
    else:
        print("提交订单失败")
        return False


def execute_variational_long(pages, configs):
    """
    在variational页面执行做多操作
    
    Args:
        pages: 页面字典
        configs: 配置列表
    """
    if not pages or 'variational' not in pages:
        print("错误: 未找到variational页面")
        return False
    
    variational_page = pages['variational']
    config = configs[0]
    symbol = config['symbol']
    size = config.get('size', '0.0001')
    
    if not click_long_button_variational(variational_page):
        print("Variational做多按钮点击失败")
        return False
    variational_page.wait_for_timeout(500)
    
    if not fill_quantity_variational(variational_page, size):
        print("输入仓位大小失败")
        return False
    variational_page.wait_for_timeout(500)
    
    if click_submit_variational(variational_page, symbol):
        print(f"Variational做多已提交: {size}")
        return True
    else:
        print("Variational提交失败")
        return False


def get_and_calculate_order_price(page, symbol, price_offset, direction, show_log=True):
    """
    获取交易对价格并计算订单价格
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
        price_offset: 价格偏移量
        direction: 方向，"long"或"short"
        show_log: 是否显示日志
    
    Returns:
        tuple: (当前价格, 订单价格) 或 (None, None) 如果失败
    """
    prices = get_price_from_api(symbol, product_type="perp")
    
    if prices is None:
        print(f"未能通过API获取{symbol}价格")
        return None, None
    
    try:
        price_key = 'bid' if direction == "long" else 'ask'
        price_num = prices.get(price_key)
        
        if price_num is None:
            print(f"未找到{price_key}价格")
            return None, None
        
        price_offset_int = int(round(price_offset * 100))
        order_price = price_num - price_offset_int if direction == "long" else price_num + abs(price_offset_int)
        
        print(f"  价格: ${price_num/100:.2f} -> 订单: ${order_price/100:.2f} (偏移: {price_offset:+.2f})")
        return price_num, order_price
    except ValueError as e:
        print(f"价格转换错误: {e}")
        return None, None


def fill_nado_order_form(page, order_price, size):
    """
    填写Nado订单表单（价格和大小）
    
    Args:
        page: Playwright页面对象
        order_price: 订单价格
        size: 订单大小
    
    Returns:
        bool: 是否成功填写
    """
    price_input = page.query_selector('#limitPrice')
    if price_input:
        price_actual = order_price / 100.0
        price_input.fill(f"{price_actual:.2f}")
    else:
        print("未找到价格输入框")
        return False
    page.wait_for_timeout(300)
    
    size_input = page.query_selector('#size')
    if size_input:
        size_input.fill(str(size))
    else:
        print("未找到大小输入框")
        return False
    page.wait_for_timeout(300)
    
    return True


def execute_nado_order_with_retry(page, symbol, size, price_offset, direction, max_retries=3):
    """
    执行Nado下单流程（带重试逻辑）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
        size: 订单大小
        price_offset: 价格偏移量
        direction: 方向，"long"或"short"
        max_retries: 最大重试次数
    
    Returns:
        bool: 是否完全成交
    """
    retry_count = 0
    
    while retry_count < max_retries:
        if retry_count > 0:
            print(f"\n🔄 第 {retry_count} 次重新下单...")
            cancel_all_orders(page, symbol)
            page.wait_for_timeout(1000)  # 等待1秒，避免API限流
        
        # 重新获取交易对价格，计算订单价格
        if retry_count > 0:
            print("  重新获取价格...")
        price_num, order_price = get_and_calculate_order_price(page, symbol, price_offset, direction)
        if price_num is None:
            return False
        
        initial_position = get_nado_position(page, symbol)
        
        if not execute_nado_order(page, symbol, order_price, size, direction):
            return False
        
        result = monitor_order_fill(page, symbol, initial_position, check_interval=0.5, max_wait_time=300, retry_timeout=30)
        
        if result is True:
            return True
        elif result is None:
            retry_count += 1
        else:
            return False
    
    print(f"\n❌ 已达到最大重试次数 ({max_retries})，停止重试")
    return False


def execute_nado_order(page, symbol, order_price, size, direction):
    """
    执行Nado下单流程（通用函数）
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
        order_price: 订单价格
        size: 订单大小
        direction: 方向，"long"或"short"
    
    Returns:
        bool: 是否成功提交订单
    """
    if not click_limit_button(page):
        print("Limit按钮点击失败")
        return False
    page.wait_for_timeout(500)
    
    if direction == "long":
        if not click_long_tab_button(page):
            print("做多标签按钮点击失败")
            return False
    else:
        if not click_short_tab_button(page):
            print("做空标签按钮点击失败")
            return False
    page.wait_for_timeout(500)
    
    if not fill_nado_order_form(page, order_price, size):
        return False
    
    order_type = "做多" if direction == "long" else "做空"
    if direction == "long":
        success = click_submit_long_button(page, symbol)
    else:
        success = click_submit_short_button(page, symbol)
    
    if success:
        price_actual = order_price / 100.0
        print(f"{order_type}订单已提交: ${price_actual:.2f}, 大小: {size}")
        return True
    else:
        print("提交订单失败")
        return False


def method1(pages, configs):
    """做多Nado做空Variational"""
    if not configs:
        print("错误: 未找到配置")
        return
    
    if not pages or 'nado' not in pages:
        print("错误: 未找到nado页面")
        return
    
    nado_page = pages['nado']
    config = configs[0]
    symbol = config['symbol']
    size = config.get('size', '0.0001')
    price_offset = float(config.get('price_offset', '-5'))
    
    print(f"\n开始执行做多Nado操作 - {symbol}")
    print("=" * 50)
    
    # 执行Nado下单流程（带重试逻辑）
    is_filled = execute_nado_order_with_retry(nado_page, symbol, size, price_offset, "long", max_retries=3)
    
    # 如果订单成交，执行Variational做空操作
    if is_filled:
        print("\n步骤8: 执行Variational做空操作...")
        execute_variational_short(pages, configs)
    else:
        print("\n订单未成交，跳过Variational操作")
    
    print("=" * 50)


def method2(pages, configs):
    """做空Nado做多Variational"""
    if not configs:
        print("错误: 未找到配置")
        return
    
    if not pages or 'nado' not in pages:
        print("错误: 未找到nado页面")
        return
    
    nado_page = pages['nado']
    config = configs[0]
    symbol = config['symbol']
    size = config.get('size', '0.0001')
    price_offset = float(config.get('price_offset', '-5'))
    
    print(f"\n做空Nado做多Variational - {symbol}")
    print("=" * 50)
    
    is_filled = execute_nado_order_with_retry(nado_page, symbol, size, price_offset, "short", max_retries=999)
    
    if is_filled:
        execute_variational_long(pages, configs)
    else:
        print("  ⚠️ 订单未成交，跳过Variational操作")
    
    print("=" * 50)


def method3(pages, configs):
    """测试API获取perp价格"""
    if not configs:
        print("错误: 未找到配置")
        return
    
    config = configs[0]
    symbol = config['symbol']
    
    print(f"\n测试API获取 {symbol} perp价格")
    print("=" * 50)
    
    prices = get_price_from_api(symbol, product_type="perp")
    
    if prices:
        print(f"\n✅ 成功获取价格:")
        if 'bid' in prices:
            bid_actual = prices['bid'] / 100.0
            print(f"  bid: ${bid_actual:,.2f} (整数: {prices['bid']})")
        if 'ask' in prices:
            ask_actual = prices['ask'] / 100.0
            print(f"  ask: ${ask_actual:,.2f} (整数: {prices['ask']})")
        if 'mid' in prices:
            mid_actual = prices['mid'] / 100.0
            print(f"  mid: ${mid_actual:,.2f} (整数: {prices['mid']})")
    else:
        print(f"\n❌ 获取价格失败")
    
    print("=" * 50)


def get_nado_position(page, symbol):
    """
    获取Nado持仓信息
    
    Args:
        page: Playwright页面对象
        symbol: 交易对符号
    
    Returns:
        str: 持仓信息，如果获取失败返回None
    """
    try:
        # 查找持仓按钮，优先查找text-negative（做空）或text-positive（做多）
        selectors = [
            'button.text-negative',
            'button.text-positive',
            'button:has-text("BTC")',
            'button:has-text("ETH")'
        ]
        
        for selector in selectors:
            position_button = page.query_selector(selector)
            if position_button:
                position_text = position_button.inner_text().strip()
                if position_text and (symbol.upper() in position_text.upper() or 'BTC' in position_text or 'ETH' in position_text):
                    return position_text
        
        return None
    except Exception as e:
        print(f"获取持仓信息时出错: {e}")
        return None


def method4(pages, configs):
    """获取Nado持仓"""
    if not configs:
        print("错误: 未找到配置")
        return
    
    if not pages or 'nado' not in pages:
        print("错误: 未找到nado页面")
        return
    
    nado_page = pages['nado']
    config = configs[0]
    symbol = config['symbol']
    
    print(f"\n获取 {symbol} Nado持仓")
    print("=" * 50)
    
    position = get_nado_position(nado_page, symbol)
    
    if position:
        print(f"\n✅ 持仓信息: {position}")
    else:
        print(f"\n❌ 未找到持仓信息")
    
    print("=" * 50)


def main():
    # 从CSV文件读取配置
    configs = load_config()
    if not configs:
        print("错误: 未找到配置，请检查 config.csv 文件")
        sys.exit(1)
    
    # 先打开所有窗口
    with sync_playwright() as playwright:
        pages = {}
        for config in configs:
            url_1 = get_url(config['symbol'], "variational")
            url_2 = get_url(config['symbol'], "nado")
            variational_page = open_page(playwright, config['variational_env_id'], url_1)
            nado_page = open_page(playwright, config['nado_env_id'], url_2)
            
            if variational_page:
                pages['variational'] = variational_page
            if nado_page:
                pages['nado'] = nado_page
        
        # 窗口打开后，显示菜单
        try:
            while True:
                show_menu()
                choice = input("请选择 (1-4): ").strip()
                
                if choice == "1":
                    method1(pages, configs)
                elif choice == "2":
                    method2(pages, configs)
                else:
                    print("无效选择，请重新输入")
        except KeyboardInterrupt:
            print("\n\n退出脚本")
            sys.exit(0)


if __name__ == "__main__":
    main()
