// BTC 50单滑动窗口网格自动下单系统 - 带风控冷却机制（2025最新）
class BTCAutoTrading {
    // ========== 基础交易配置 ==========
    static TRADING_CONFIG = {
        START_PRICE: 80000,
        END_PRICE: 100000,
        MIN_ORDER_INTERVAL: 5000,     // 下单最小间隔10秒（防风控）
        ORDER_COOLDOWN: 5000,          // 单个订单成功后冷却3秒
        MONITOR_INTERVAL: 5000,       // 主循环检查间隔（建议8~15秒）
        MAX_PROCESSED_ORDERS: 100,
        POSITION_CHECK_DELAY: 2000,
        MAX_POSITION_CHECKS: 60,
        UI_OPERATION_DELAY: 500,
        PRICE_UPDATE_DELAY: 1500,
        ORDER_SUBMIT_DELAY: 1500,
        CLOSE_POSITION_CYCLE: 30,
        RISK_COOLDOWN_MINUTES: 15,    // 风控冷却时间（15分钟）
        CHECK_INTERVAL_RISK: 10000    // 风控状态下检查间隔（10秒）
    };

    // ========== 网格策略核心配置（全部集中在这里调参！）==========
    static GRID_STRATEGY_CONFIG = {
        TOTAL_ORDERS: 8,               // 固定50单滑动窗口

        // 窗口宽度（核心参数！建议 0.08~0.18）
        WINDOW_PERCENT: 0.12,           // 12% → 7万时 ≈ ±4200美元范围

        // 买卖单比例（总和必须为1，可根据牛熊调整）
        SELL_RATIO: 0.5,               // 55% ≈ 27~28个卖单（适合震荡偏多）
        BUY_RATIO:  0.5,               // 45% ≈ 22~23个买单

        // 网格间距
        BASE_PRICE_INTERVAL: 30,        // 基础间距（会自动微调保证填满单数）
        SAFE_GAP: 20,                   // 比当前盘口再偏移一点，防止瞬成

        // 安全保护
        MAX_DRIFT_BUFFER: 2000,         // 超出窗口太多自动停止扩展
        MIN_VALID_PRICE: 10000,         // 防止崩盘挂到地板价
        MAX_MULTIPLIER: 20,         // 动态开仓大小的比例最大开仓倍数

        // --- 策略配置 ---
        RSI_MIN: 30,                   // RSI 下限
        RSI_MAX: 70,                    // RSI 上限
        ADX_TREND_THRESHOLD: 25,                   // ADX 下限
        ADX_STRONG_TREND: 30                   // ADX 下限
    };

    // ========== 页面元素选择器 ==========
    static SELECTORS = {
        ASK_PRICE: 'span[data-testid="ask-price-display"]',
        BID_PRICE: 'span[data-testid="bid-price-display"]',
        QUANTITY_INPUT: 'input[data-testid="quantity-input"]',
        PRICE_INPUT: 'input[data-testid="limit-price-input"]',
        SUBMIT_BUTTON: 'button[data-testid="submit-button"]',
        ORDERS_TABLE_ROW: '[data-testid="orders-table-row"]',
        RED_ELEMENTS: '.text-red',
        GREEN_ELEMENTS: '.text-green',
        TEXT_CURRENT: '[class*="text-current"]'
    };

    // ========== 文本与类名匹配 ==========
    static TEXT_MATCH = {
        PENDING_ORDERS: ['未成交订单', 'Pending Orders', 'Open Orders'],
        LIMIT_BUTTON: ['限价', 'limit'],
        BUY_BUTTON: ['买', 'Buy'],
        SELL_BUTTON: ['卖', 'Sell']
    };

    static CLASS_MATCH = {
        LIMIT_BUTTON: ['p-0', 'text-center'],
        BUY_BUTTON: 'bg-green',
        SELL_BUTTON: 'bg-red'
    };

    constructor() {
        this.orderManager = new BTCOrderManager();
        this.isMonitoring = false;
        this.monitorInterval = null;
        this.tradingEnabled = false;
        this.processedOrders = new Set();
        this.lastOrderTime = 0;
        this.cycleCount = 0;
        this.isPrepared = false;
        this.riskCoolingDown = false;  // 风控冷却状态
        this.riskCoolDownEndTime = 0;  // 冷却结束时间戳
        this.riskTriggeredReason = ''; // 风控触发原因

        this.minOrderInterval = BTCAutoTrading.TRADING_CONFIG.MIN_ORDER_INTERVAL;
    }

    // ==================== 准备交易环境 ====================
    async prepareTradingEnvironment() {
        try {
            // 1. 点击"未成交订单"
            const pendingTab = this.findPendingOrdersTab();
            if (pendingTab) {
                pendingTab.click();
                await this.delay(BTCAutoTrading.TRADING_CONFIG.UI_OPERATION_DELAY);
            }

            // 2. 点击"限价"
            await this.clickLimitButton();
            await this.delay(BTCAutoTrading.TRADING_CONFIG.UI_OPERATION_DELAY * 2);

            // 3. 等待仓位设置
            await this.checkAndWaitForPositionSize();

            this.isPrepared = true;
            return true;
        } catch (err) {
            console.error('交易环境准备失败:', err);
            return false;
        }
    }

    async getCurrentPrice() {
        const askEl = document.querySelector('span[data-testid="ask-price-display"]');
        const bidEl = document.querySelector('span[data-testid="bid-price-display"]');
        
        if (!askEl || !bidEl) return null;
        
        const askPrice = parseFloat(askEl.textContent.replace(/[$,]/g, ''));
        const bidPrice = parseFloat(bidEl.textContent.replace(/[$,]/g, ''));
        
        return (askPrice + bidPrice) / 2;
    }

    findPendingOrdersTab() {
        return Array.from(document.querySelectorAll('span')).find(el =>
            BTCAutoTrading.TEXT_MATCH.PENDING_ORDERS.some(t => el.textContent.includes(t))
        );
    }

    async clickLimitButton() {
        const buttons = Array.from(document.querySelectorAll('button'));
        const limitBtn = buttons.find(btn =>
            BTCAutoTrading.TEXT_MATCH.LIMIT_BUTTON.some(t =>
                btn.textContent.toLowerCase().includes(t.toLowerCase())
            )
        ) || buttons.find(btn =>
            BTCAutoTrading.CLASS_MATCH.LIMIT_BUTTON.every(c => btn.className.includes(c))
        );

        if (limitBtn) {
            limitBtn.click();
            await this.delay(BTCAutoTrading.TRADING_CONFIG.UI_OPERATION_DELAY);
            return true;
        }
        console.log('未找到限价按钮，继续...');
        return false;
    }

    async checkAndWaitForPositionSize() {
        let checks = 0;
        while (checks < BTCAutoTrading.TRADING_CONFIG.MAX_POSITION_CHECKS) {
            const input = document.querySelector(BTCAutoTrading.SELECTORS.QUANTITY_INPUT);
            if (input && parseFloat(input.value) > 0) {
                console.log(`仓位已设置: ${input.value}`);
                return true;
            }
            checks++;
            console.error('请先手动设置仓位数量！');
            await this.delay(BTCAutoTrading.TRADING_CONFIG.POSITION_CHECK_DELAY);
        }
        console.error('超时：请先手动设置仓位数量！');
        this.showWarningMessage('请先在数量框输入开仓大小！');
        return false;
    }

    async getTradeInfo() {
        // 获取仓位
        let position = '0';  // 默认设为0
        const xpath = "//*[contains(text(), '仓位') or contains(text(), 'Position')]";
        const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        
        for (let i = 0; i < result.snapshotLength; i++) {
            const node = result.snapshotItem(i);
            const btcEl = node.parentElement.querySelector('.text-blackwhite');
            if (btcEl && btcEl.textContent.includes('BTC')) {
                position = btcEl.textContent.trim().replace(/[^\d.-]/g, '');
                break;
            }
        }
        
        // 获取开仓大小
        const input = document.querySelector('input[data-testid="quantity-input"]');
        const orderSizeText = input ? (input.value || input.placeholder || '0') : '0';
        const orderSize = parseFloat(orderSizeText.replace(/[^\d.]/g, '')) ; // 默认值
        
        // 转换为数字
        const positionBTC = parseFloat(position) || 0;
        
        console.log(`当前仓位: ${positionBTC.toFixed(4)} BTC`);
        console.log(`开仓大小: ${orderSize}`);
        return {positionBTC, orderSize};  // 返回数字类型
    }

    // ==================== 风控冷却相关方法 ====================
    
    /**
     * 触发风控冷却
     * @param {string} reason - 风控触发原因
     */
    async triggerRiskCooldown(reason) {
        this.riskCoolingDown = true;
        this.riskTriggeredReason = reason;
        
        // 设置冷却结束时间
        const cooldownMs = BTCAutoTrading.TRADING_CONFIG.RISK_COOLDOWN_MINUTES * 60 * 1000;
        this.riskCoolDownEndTime = Date.now() + cooldownMs;
        
        const endTime = new Date(this.riskCoolDownEndTime).toLocaleTimeString();
        console.log(`%c⚠️ 触发风控冷却：${reason}`, "color: red; font-weight: bold; font-size: 14px;");
        console.log(`%c冷却时间：15分钟，恢复时间：${endTime}`, "color: orange;");
        
        try {
            // 1. 先取消所有订单（等待完成）
            console.log('开始平仓...');
            await this.simpleClosePosition();
            console.log('✅ 平仓操作完成');
            
            // 2. 等待1秒，让界面稳定
            await this.delay(500);
            
            // 3. 再平仓（等待完成）
            console.log('开始取消所有订单...');
            await this.cancelAllOrder();
            console.log('✅ 所有订单取消完成');
            console.log(`%c✅ 风控处理完成，进入冷却期`, "color: #4CAF50; font-weight: bold;");
            
        } catch (error) {
            console.error(`%c❌ 风控处理失败: ${error.message}`, "color: red; font-weight: bold;");
            // 即使失败，也要保持冷却状态
        }
    }
    
    /**
     * 检查风控冷却状态
     * @returns {boolean} 是否在冷却中
     */
    checkRiskCooldown() {
        if (!this.riskCoolingDown) return false;
        
        const now = Date.now();
        if (now >= this.riskCoolDownEndTime) {
            // 冷却结束
            this.riskCoolingDown = false;
            this.riskTriggeredReason = '';
            console.log(`%c✅ 风控冷却已结束，恢复交易`, "color: green; font-weight: bold;");
            return false;
        }
        
        return true;
    }
    
    /**
     * 手动重置风控冷却
     */
    resetRiskCooldown() {
        this.riskCoolingDown = false;
        this.riskCoolDownEndTime = 0;
        this.riskTriggeredReason = '';
        console.log(`%c✅ 风控冷却已手动重置`, "color: green; font-weight: bold;");
    }
    
    /**
     * 获取风控冷却状态信息
     */
    getRiskCooldownStatus() {
        if (!this.riskCoolingDown) {
            return {
                inCooldown: false,
                message: '风控冷却未激活'
            };
        }
        
        const remainingMs = this.riskCoolDownEndTime - Date.now();
        const remainingMinutes = Math.floor(remainingMs / (60 * 1000));
        const remainingSeconds = Math.floor((remainingMs % (60 * 1000)) / 1000);
        const endTime = new Date(this.riskCoolDownEndTime).toLocaleTimeString();
        
        return {
            inCooldown: true,
            reason: this.riskTriggeredReason,
            remainingMinutes,
            remainingSeconds,
            endTime,
            message: `风控冷却中 - ${this.riskTriggeredReason}，剩余: ${remainingMinutes}分${remainingSeconds}秒，预计恢复: ${endTime}`
        };
    }

    // ==================== 主控方法 ====================
    async startAutoTrading(interval = BTCAutoTrading.TRADING_CONFIG.MONITOR_INTERVAL) {
        if (this.isMonitoring) return console.log('已在运行');

        const ready = await this.prepareTradingEnvironment();
        if (!ready) return console.error('环境准备失败，无法启动');

        this.isMonitoring = true;
        this.tradingEnabled = true;
        this.cycleCount = 0;
        console.log('BTC 50单网格自动交易已启动');
        console.log('脚本免费开源，作者推特@ddazmon');
        console.log('用谁的邀请码不是用，欢迎兄弟们使用邀请码，点返金额原路返回：');
        console.log('OMNINU3G7KVK');
        console.log('OMNIBGZ4ETT9');

        // 改用递归的setTimeout确保不重叠
        const executeWithInterval = async () => {
            if (!this.isMonitoring) return;
            
            const startTime = Date.now();
            await this.executeTradingCycle();
            const endTime = Date.now();
            const executionTime = endTime - startTime;
            
            // 根据是否在风控冷却中调整间隔
            let nextDelay;
            if (this.riskCoolingDown) {
                // 风控冷却时使用较长的检查间隔
                nextDelay = Math.max(BTCAutoTrading.TRADING_CONFIG.CHECK_INTERVAL_RISK - executionTime, 1000);
            } else {
                // 正常交易时使用原间隔
                nextDelay = Math.max(interval - executionTime, 1000);
            }

             // 1. 清理所有缓存
            console.log('清理所有缓存');
            if (window.console && console.clear) {
              console.clear(); // 清空控制台
            }
            
            // 2. 触发垃圾回收（非标准，但Chrome支持）
            if (window.gc) {
              window.gc();
            }
            
            if (this.isMonitoring) {
                setTimeout(executeWithInterval, nextDelay);
            }
        };
        
        // 立即开始第一个周期
        executeWithInterval();
    }

    stopAutoTrading() {
        this.isMonitoring = false;
        this.tradingEnabled = false;
        clearInterval(this.monitorInterval);
        this.monitorInterval = null;
        console.log('自动交易已停止');
    }

    // ==================== 核心交易周期 ====================
    async executeTradingCycle() {
        if (!this.tradingEnabled) return;
        this.cycleCount++;
        console.log(`\n[${new Date().toLocaleTimeString()}] 第${this.cycleCount}次循环`);

        // 1. 检查风控冷却状态
        if (this.checkRiskCooldown()) {
            await this.simpleClosePosition();
            await this.delay(500);
            await this.cancelAllOrder();
            return; // 在冷却中，跳过整个交易周期
        }

        // 2. RSI 检查逻辑
        try {
            const indicators = await this.getIndicatorsFromChart();
            
            if (indicators && typeof indicators.rsi === 'number' && typeof indicators.adx === 'number') {
                const { rsi, adx } = indicators;
                const { RSI_MIN, RSI_MAX, ADX_TREND_THRESHOLD, ADX_STRONG_TREND } = BTCAutoTrading.GRID_STRATEGY_CONFIG;
                
                console.log(`%c当前指标 - RSI: ${rsi.toFixed(2)}, ADX: ${adx.toFixed(2)}`, 
                           "color: #ff9800; font-weight: bold; font-size: 14px;");
                
                // 情况1: 强趋势市场 - 触发风控冷却
                if (adx > ADX_STRONG_TREND) {
                    const reason = `强趋势市场 (ADX: ${adx.toFixed(2)} > ${ADX_STRONG_TREND})`;
                    console.log(`%c[风控触发] ${reason}`, "color: red; font-weight: bold;");
                    
                    // 触发15分钟冷却
                    this.triggerRiskCooldown(reason);
                    return; // 立即返回，不再执行后续交易
                }
                
                // 情况2: 中等趋势市场 - 谨慎操作
                if (adx > ADX_TREND_THRESHOLD) {
                    console.log(`%c[警告] ADX(${adx.toFixed(2)}) > ${ADX_TREND_THRESHOLD}，市场存在趋势。`, 
                               "color: orange;");
                    
                    // 在趋势市场中，需要更严格的RSI控制
                    const TREND_RSI_TOLERANCE = 5; // 收紧RSI容忍度
                    
                    // 如果RSI显示极端超买/超卖，触发风控冷却
                    if (rsi < (RSI_MIN - TREND_RSI_TOLERANCE) || rsi > (RSI_MAX + TREND_RSI_TOLERANCE)) {
                        const reason = `趋势市场中RSI(${rsi.toFixed(2)})过于极端`;
                        console.log(`%c[风控触发] ${reason}`, "color: red; font-weight: bold;");
                        
                        // 触发15分钟冷却
                        this.triggerRiskCooldown(reason);
                        return; // 立即返回，不再执行后续交易
                    }
                    
                    console.log(`%c[谨慎允许] 趋势市场但RSI在可控范围内，执行谨慎网格策略。`, 
                               "color: #ff9800;");
                    // 可以继续执行网格，但可能需要调整参数（如减少仓位）
                }
                // 情况3: 震荡市场 - 最适合网格交易
                else {
                    console.log(`%c[理想] ADX(${adx.toFixed(2)}) < ${ADX_TREND_THRESHOLD}，市场处于震荡行情，适合网格策略。`, 
                               "color: #4CAF50;");
                    
                    // 检查RSI是否在震荡区间内
                    if (rsi < RSI_MIN || rsi > RSI_MAX) {
                        const reason = `RSI(${rsi.toFixed(2)})不在${RSI_MIN}-${RSI_MAX}震荡区间`;
                        console.log(`%c[风控触发] ${reason}`, "color: red; font-weight: bold;");
                        
                        // 触发15分钟冷却
                        this.triggerRiskCooldown(reason);
                        return; // 立即返回，不再执行后续交易
                    }
                    
                    console.log(`%c[允许] 震荡市场且RSI在区间内，执行标准网格策略。`, 
                               "color: green; font-weight: bold;");
                }
            } else {
                console.warn("未能获取完整的指标数据");
                // 无法获取指标时，保守起见触发风控冷却
                const reason = "无法获取完整指标数据";
                console.log(`%c[风控触发] ${reason}`, "color: red; font-weight: bold;");
                this.triggerRiskCooldown(reason);
                return;
            }
        } catch (e) {
            console.error("读取图表指标失败:", e);
            // 发生错误时，触发风控冷却
            const reason = `指标读取失败: ${e.message}`;
            this.triggerRiskCooldown(reason);
            return;
        }

        // 3. 环境准备和交易执行（只有通过风控检查才会执行到这里）
        const ready = await this.prepareTradingEnvironment();
        if (!ready) {
            console.error('环境异常');
            return;
        }
        
        try {
            const marketData = await this.getCompleteMarketData();
            if (!marketData.askPrice || !marketData.bidPrice) {
                console.log('无法读取价格，跳过');
                return;
            }

            const result = await this.calculateTargetPrices(marketData);
            console.log('计算订单结果：', result);

            // 新增：自动撤销最远的旧单
            if (result.cancelOrders && result.cancelOrders.length > 0) {
                console.log(`开始撤销 ${result.cancelOrders.length} 个远单...`);
                for (const order of result.cancelOrders) {
                    // 检查是否需要跳过撤单（如果价格接近当前价格）
                    const currentPrice = await this.getCurrentPrice();
                    if (currentPrice && order.price) {
                        // 修复这里：使用 order.price 而不是 price
                        const targetNum = Number(String(order.price).replace(/[^0-9.]/g, ''));
                        if (targetNum) {
                            const cfg = BTCAutoTrading.GRID_STRATEGY_CONFIG;  // 添加这行定义 cfg
                            const priceDiff = Math.abs(targetNum - currentPrice);
                            const isNearCurrentPrice = priceDiff <= cfg.BASE_PRICE_INTERVAL * (cfg.MAX_MULTIPLIER/4);
                            
                            if (isNearCurrentPrice) {
                                console.log(`跳过撤单：价格接近当前价格 (差值: ${priceDiff.toFixed(1)})`);
                                continue;  // 跳过这个订单，不撤单
                            }
                        }
                    }
                    await this.orderManager.cancelByPrice(order.price);
                    await this.delay(2000);
                }
            }
            
            // 4. 重要：撤单后等待并重新获取订单状态
            const updatedMarketData = await this.getCompleteMarketData();
            
            // 5. 基于新状态重新计算要下的订单
            const updatedResult = await this.calculateTargetPrices(updatedMarketData);

            // 6. 执行下单
            if (updatedResult.buyPrices.length > 0 || updatedResult.sellPrices.length > 0) {
                await this.executeSafeBatchOrders(
                    updatedResult.buyPrices, 
                    updatedResult.sellPrices, 
                    updatedMarketData
                );
            }

        } catch (err) {
            console.error('周期执行异常:', err);
            // 执行异常时触发风控冷却
            const reason = `执行异常: ${err.message}`;
            this.triggerRiskCooldown(reason);
        }
    }

    async cancelAllOrder() {
        console.log('准备关闭所有挂单');
        const ready = await this.prepareTradingEnvironment();
        if (!ready) return console.error('环境准备失败，无法启动');

        const marketData = await this.getCompleteMarketData();
        if (!marketData.askPrice || !marketData.bidPrice) {
            console.log('无法读取价格，跳过');
            return;
        }
        const { askPrice, bidPrice, existingSellOrders = [], existingBuyOrders = [] } = marketData;

        console.log('关闭所有卖单');
        if (existingSellOrders && existingSellOrders.length > 0) {
            console.log(`开始撤销 ${existingSellOrders.length} 个卖单...`);
            for (const order of existingSellOrders) {
                await this.orderManager.cancelByPrice(order);
                await this.delay(500);
            }
        }
        console.log('关闭所有买单');
        if (existingBuyOrders && existingBuyOrders.length > 0) {
            console.log(`开始撤销 ${existingBuyOrders.length} 个买单...`);
            for (const order of existingBuyOrders) {
                await this.orderManager.cancelByPrice(order);
                await this.delay(500);
            }
        }
    }

    async simpleClosePosition() {
        console.log('开始关闭仓位操作...');
        
        try {
            // 步骤1：点击仓位元素
            const clicked = await this.clickPositionElement();
            if (!clicked) {
                console.log('没有持仓或找不到仓位元素');
                return false;
            }
            
            // 步骤2：点击关闭按钮
            const closed = await this.clickCloseButton();
            if (!closed) {
                console.log('没有需要关闭的仓位');
                return true; // 没有仓位也算成功
            }
            
            // 步骤3：点击卖出平仓按钮
            const sold = await this.clickSellCloseButton();
            if (!sold) {
                throw new Error('平仓失败');
            }
            
            console.log('✅ 平仓操作完成！');
            return true;
            
        } catch (error) {
            console.error('平仓操作失败:', error);
            return false;
        }
    }

    async clickPositionElement() {
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    return node.textContent.trim() === '仓位' ? 
                        NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }
            }
        );
        
        const positionNode = walker.nextNode();
        if (positionNode && positionNode.parentElement) {
            console.log('点击仓位元素...');
            positionNode.parentElement.click();
            await this.delay(1000); // 等待界面响应
            return true;
        }
        return false;
    }

    async clickCloseButton() {
        // 等待弹窗/界面更新
        await this.delay(1000);
        
        const closeBtns = document.querySelectorAll('button');
        const closeBtn = Array.from(closeBtns).find(btn => 
            btn.textContent.trim() === '关闭' || 
            btn.textContent.includes('关闭')
        );
        
        if (closeBtn) {
            console.log('点击关闭按钮...');
            closeBtn.click();
            await this.delay(1500); // 等待确认弹窗
            return true;
        }
        
        console.log('未找到关闭按钮，可能没有持仓');
        return false;
    }

    async clickSellCloseButton() {
        // 查找"卖出平仓"按钮
        const sellBtns = document.querySelectorAll('button');
        const sellBtn = Array.from(sellBtns).find(btn => 
            btn.textContent.includes('卖出平仓') || 
            btn.textContent.includes('平仓')
        );
        
        if (sellBtn) {
            console.log('点击卖出平仓按钮...');
            sellBtn.click();
            await this.delay(2000); // 等待操作完成
            return true;
        }
        
        throw new Error('找不到卖出平仓按钮');
    }

    // ==================== RSI 读取模块 ====================
    async getIndicatorsFromChart() {
        const iframe = document.querySelector('iframe');
        if (!iframe) {
            console.warn('未找到 TradingView iframe');
            return null;
        }

        try {
            const doc = iframe.contentDocument;
            if (!doc) return null;
        } catch (e) {
            console.error('无法访问 iframe 内容，可能是跨域限制:', e);
            return null;
        }

        return new Promise((resolve) => {
            const doc = iframe.contentDocument;
            const valueElements = doc.querySelectorAll('div[class*="valueValue"]');
            
            if (valueElements.length === 0) {
                resolve(null);
                return;
            }

            let result = { currentPrice: null, ema9: null, ema21: null, rsi: null, adx: null };

            valueElements.forEach(element => {
                const valueText = element.textContent.trim();
                const color = window.getComputedStyle(element).color;
                const parent = element.parentElement;
                const titleEl = parent?.querySelector('div[class*="valueTitle"]');
                const title = titleEl ? titleEl.textContent.trim() : '';

                const val = parseFloat(valueText.replace(/,/g, ''));

                if (title === 'C' || title === '收盘') {
                    result.currentPrice = val;
                } else if (color.includes('33, 150, 243')) {
                    result.ema9 = val;
                } else if (color.includes('255, 235, 59')) {
                    result.ema21 = val;
                } else if (color.includes('126, 87, 194') || title === 'RSI') {
                    result.rsi = val;
                } else if (color.includes('255, 82, 82') || title === 'ADX') {
                    result.adx = val;
                }
            });
            resolve(result);
        });
    }

    // ==================== 获取市场数据 ====================
    async getCompleteMarketData() {
        const askEl = document.querySelector(BTCAutoTrading.SELECTORS.ASK_PRICE);
        const bidEl = document.querySelector(BTCAutoTrading.SELECTORS.BID_PRICE);

        if (!askEl || !bidEl) return { askPrice: null, bidPrice: null, existingSellOrders: [], existingBuyOrders: [] };

        const askPrice = parseFloat(askEl.textContent.replace(/[$,]/g, ''));
        const bidPrice = parseFloat(bidEl.textContent.replace(/[$,]/g, ''));

        await this.delay(BTCAutoTrading.TRADING_CONFIG.PRICE_UPDATE_DELAY);

        const rows = document.querySelectorAll(BTCAutoTrading.SELECTORS.ORDERS_TABLE_ROW);
        const existingSell = new Set();
        const existingBuy = new Set();

        rows.forEach(row => {
            const isSell = row.querySelectorAll(BTCAutoTrading.SELECTORS.RED_ELEMENTS).length > 0;
            const isBuy = row.querySelectorAll(BTCAutoTrading.SELECTORS.GREEN_ELEMENTS).length > 0;
            if (!isSell && !isBuy) return;

            const priceTexts = Array.from(row.querySelectorAll(BTCAutoTrading.SELECTORS.TEXT_CURRENT))
                .map(el => el.textContent.trim())
                .filter(t => t.includes('$') && !t.includes('Q'));
            if (priceTexts.length === 0) return;

            const price = parseFloat(priceTexts[0].replace(/[$,]/g, ''));
            if (price > 0) {
                if (isSell) existingSell.add(price);
                if (isBuy) existingBuy.add(price);
            }
        });

        return {
            askPrice,
            bidPrice,
            existingSellOrders: Array.from(existingSell).sort((a, b) => a - b),
            existingBuyOrders: Array.from(existingBuy).sort((a, b) => b - a)
        };
    }

    // ==================== 计算目标价格 ================
    async calculateTargetPrices(marketData) {
        const { askPrice, bidPrice, existingSellOrders = [], existingBuyOrders = [] } = marketData;
        const cfg = BTCAutoTrading.GRID_STRATEGY_CONFIG;

        const midPrice = (askPrice + bidPrice) / 2;
        const windowSize = midPrice * cfg.WINDOW_PERCENT;
        const halfWindow = windowSize / 2;
        const interval = cfg.BASE_PRICE_INTERVAL;

        const tradeInfo = await this.getTradeInfo();
        const positionBTC = tradeInfo.positionBTC || 0;
        const orderSize = tradeInfo.orderSize || 0;
        const MAX_MULTIPLIER = cfg.MAX_MULTIPLIER;
        
        const safeOrderSize = Math.max(orderSize, 0.000001);
        const positionMultiplier = Math.abs(positionBTC) / safeOrderSize;
        
        const baseSellRatio = cfg.SELL_RATIO;
        const baseBuyRatio = 1 - baseSellRatio;
        
        let finalSellRatio = baseSellRatio;
        let finalBuyRatio = baseBuyRatio;
        let isAtLimit = false;
        
        console.log(`当前持仓: ${positionBTC.toFixed(4)} BTC | 相对于开仓大小的倍数: ${positionMultiplier.toFixed(1)}x`);
        
        if (positionMultiplier >= MAX_MULTIPLIER) {
            isAtLimit = true;
            if (positionBTC > 0) {
                console.log(`⚠️ 多单已达上限(${MAX_MULTIPLIER}x)，停止开多单`);
                finalBuyRatio = 0;
                finalSellRatio = 1;
            } else if (positionBTC < 0) {
                console.log(`⚠️ 空单已达上限(${MAX_MULTIPLIER}x)，停止开空单`);
                finalBuyRatio = 1;
                finalSellRatio = 0;
            }
        } else if (positionMultiplier > 0) {
            const reductionRatio = positionMultiplier / MAX_MULTIPLIER;
            
            if (positionBTC > 0) {
                const buyReduction = reductionRatio * baseBuyRatio;
                finalBuyRatio = Math.max(0, baseBuyRatio - buyReduction);
                finalSellRatio = 1 - finalBuyRatio;
                console.log(`调整后比例: 卖单 ${(finalSellRatio*100).toFixed(0)}% / 买单 ${(finalBuyRatio*100).toFixed(0)}%`);
            } else if (positionBTC < 0) {
                const sellReduction = reductionRatio * baseSellRatio;
                finalSellRatio = Math.max(0, baseSellRatio - sellReduction);
                finalBuyRatio = 1 - finalSellRatio;
                console.log(`调整后比例: 卖单 ${(finalSellRatio*100).toFixed(0)}% / 买单 ${(finalBuyRatio*100).toFixed(0)}%`);
            }
        }
        
        if (!isAtLimit) {
            finalBuyRatio = Math.max(0.1, Math.min(0.9, finalBuyRatio));
            finalSellRatio = Math.max(0.1, Math.min(0.9, finalSellRatio));
        }

        console.log(`最终比例: 卖单 ${(finalSellRatio*100).toFixed(0)}% / 买单 ${(finalBuyRatio*100).toFixed(0)}%`);
        
        const sellCount = Math.round(cfg.TOTAL_ORDERS * finalSellRatio);
        const buyCount = cfg.TOTAL_ORDERS - sellCount;

        const sellStart = Math.ceil((askPrice + cfg.SAFE_GAP) / interval) * interval;
        const idealSellPrices = [];
        for (let i = 0; i < sellCount; i++) {
            const p = sellStart + i * interval;
            if (p > midPrice + halfWindow + cfg.MAX_DRIFT_BUFFER) break;
            idealSellPrices.push(p);
        }

        const buyEnd = Math.floor((bidPrice - cfg.SAFE_GAP) / interval) * interval;
        const idealBuyPrices = [];
        for (let i = 0; i < buyCount; i++) {
            const p = buyEnd - i * interval;
            if (p < midPrice - halfWindow - cfg.MAX_DRIFT_BUFFER) break;
            if (p < cfg.MIN_VALID_PRICE) break;
            idealBuyPrices.push(p);
        }

        const idealPricesSet = new Set([...idealSellPrices, ...idealBuyPrices]);

        const newSellPrices = idealSellPrices.filter(p => !existingSellOrders.includes(p));
        const newBuyPrices  = idealBuyPrices.filter(p => !existingBuyOrders.includes(p));

        const currentTotal = existingSellOrders.length + existingBuyOrders.length;
        const ordersToCancel = [];

        if (currentTotal > cfg.TOTAL_ORDERS || existingSellOrders.length > sellCount || existingBuyOrders.length > buyCount) {
            const farSellOrders = existingSellOrders
                .filter(p => !idealPricesSet.has(p))
                .sort((a, b) => b - a);

            const farBuyOrders = existingBuyOrders
                .filter(p => !idealPricesSet.has(p))
                .sort((a, b) => a - b);

            const allFar = [
                ...farSellOrders.map(p => ({ type: 'sell', price: p })),
                ...farBuyOrders.map(p => ({ type: 'buy', price: p }))
            ];

            allFar.sort((a, b) => Math.abs(b.price - midPrice) - Math.abs(a.price - midPrice));

            const excess = currentTotal - cfg.TOTAL_ORDERS;
            for (let i = 0; i < Math.max(excess, allFar.length); i++) {
                if (ordersToCancel.length >= 10) break;
                ordersToCancel.push(allFar[i]);
            }
        }

        console.log(`中间价 $${midPrice.toFixed(1)} | 窗口 ±${halfWindow.toFixed(0)}`);
        console.log(`当前订单: ${existingSellOrders.length}卖 + ${existingBuyOrders.length}买 = ${currentTotal}`);
        console.log(`目标订单: ${idealSellPrices.length}卖 + ${idealBuyPrices.length}买`);
        console.log(`需下单: ${newSellPrices.length}卖 + ${newBuyPrices.length}买`);
        if (ordersToCancel.length > 0) {
            console.log(`需撤销: ${ordersToCancel.length}单 →`, ordersToCancel.map(o => `${o.type}-${o.price}`).join(', '));
        } else {
            console.log(`无需撤销订单`);
        }

        return {
            sellPrices: newSellPrices,
            buyPrices:  newBuyPrices,
            cancelOrders: ordersToCancel
        };
    }

    // ==================== 安全批量下单 ====================
    async executeSafeBatchOrders(buyPrices, sellPrices, marketData) {
        const orders = [
            ...buyPrices.map(p => ({ type: 'buy', price: p })),
            ...sellPrices.map(p => ({ type: 'sell', price: p }))
        ];

        console.log(`新单:`, orders);
        for (const order of orders) {
            const success = order.type === 'buy'
                ? await this.orderManager.placeLimitBuy(order.price)
                : await this.orderManager.placeLimitSell(order.price);

            if (success) {
                this.lastOrderTime = Date.now();
                await this.delay(BTCAutoTrading.TRADING_CONFIG.ORDER_COOLDOWN);
            }
        }
        console.log('本轮下单完成');
    }

    // ==================== 工具方法 ====================
    clearOrderHistory() {
        this.processedOrders.clear();
        this.lastOrderTime = 0;
        this.cycleCount = 0;
        console.log('订单记录已清空');
    }

    getStatus() {
        const riskStatus = this.getRiskCooldownStatus();
        
        return {
            isMonitoring: this.isMonitoring,
            cycleCount: this.cycleCount,
            processedCount: this.processedOrders.size,
            lastOrderTime: this.lastOrderTime ? new Date(this.lastOrderTime).toLocaleTimeString() : '无',
            nextClosePositionCycle: BTCAutoTrading.TRADING_CONFIG.CLOSE_POSITION_CYCLE - (this.cycleCount % BTCAutoTrading.TRADING_CONFIG.CLOSE_POSITION_CYCLE),
            riskCooldown: riskStatus
        };
    }

    showWarningMessage(msg) {
        alert(`警告：${msg}`);
        console.warn(`警告：${msg}`);
    }

    delay(ms) {
        return new Promise(r => setTimeout(r, ms));
    }
}

// ==================== 下单管理器 ====================
class BTCOrderManager {
    static CONFIG = { UI_OPERATION_DELAY: 500, INPUT_DELAY: 300, ORDER_SUBMIT_DELAY: 1000 };

    async placeLimitBuy(price) {
        return await this.placeOrder(price, 'buy');
    }

    async placeLimitSell(price) {
        return await this.placeOrder(price, 'sell');
    }

    async placeOrder(price, type) {
        console.warn(`placeOrder：`,price, type);
        try {
            const button = type === 'buy' ? this.findBuyButton() : this.findSellButton();
            if (!button) return false;
            button.click();

            await this.delay(BTCOrderManager.CONFIG.UI_OPERATION_DELAY);

            const priceInput = document.querySelector('input[data-testid="limit-price-input"]');
            if (!priceInput) return false;

            priceInput.value = price;
            priceInput.dispatchEvent(new Event('input', { bubbles: true }));

            await this.delay(BTCOrderManager.CONFIG.INPUT_DELAY);

            const submit = document.querySelector('button[data-testid="submit-button"]');
            if (!submit || submit.disabled) return false;
            submit.click();

            return true;
        } catch (err) {
            console.error('下单异常:', err);
            return false;
        }
    }

    findBuyButton() { return this.findDirectionButton('buy'); }
    findSellButton() { return this.findDirectionButton('sell'); }

    findDirectionButton(dir) {
        const isBuy = dir === 'buy';
        if (isBuy) {
            const askPriceElement = document.querySelector('span[data-testid="ask-price-display"]');
            if (askPriceElement) {
                const buyButton = askPriceElement.closest('button');
                if (buyButton && buyButton.textContent.includes('买')) {
                    return buyButton;
                }
            }
        } else {
            const bidPriceElement = document.querySelector('span[data-testid="bid-price-display"]');
            if (bidPriceElement) {
                const sellButton = bidPriceElement.closest('button');
                if (sellButton && sellButton.textContent.includes('卖')) {
                    return sellButton;
                }
            }
        }
        return null;
    }

    async getCurrentPrice() {
        const askEl = document.querySelector('span[data-testid="ask-price-display"]');
        const bidEl = document.querySelector('span[data-testid="bid-price-display"]');
        
        if (!askEl || !bidEl) return null;
        
        const askPrice = parseFloat(askEl.textContent.replace(/[$,]/g, ''));
        const bidPrice = parseFloat(bidEl.textContent.replace(/[$,]/g, ''));
        
        return (askPrice + bidPrice) / 2;
    }

    async cancelByPrice(price) {
        console.log(`准备取消 $${price}`);
        
        const prices = Array.isArray(price) ? price : [price];
        
        for (let target of prices) {
            const targetNum = Number(String(target).replace(/[^0-9.]/g, ''));
            if (!targetNum) continue;

            const allPriceSpans = document.querySelectorAll('div.justify-self-end > span.text-current');

            let found = false;
            for (const span of allPriceSpans) {
                const text = span.textContent.trim();
                const priceInPage = Number(text.replace(/[$,]/g, ''));
                
                if (priceInPage === targetNum) {
                    const row = span.closest('[data-testid="orders-table-row"]');
                    const cancelBtn = row?.querySelector('button[title="取消订单"]');
                    
                    if (cancelBtn) {
                        cancelBtn.scrollIntoView({ block: 'center' });
                        cancelBtn.click();

                        await new Promise(resolve => {
                            let attempts = 0;
                            const timer = setInterval(() => {
                                attempts++;
                                
                                const confirmBtn = 
                                    [...document.querySelectorAll('button')].find(btn => 
                                        btn.textContent.trim() === '确认' && 
                                        btn.classList.contains('bg-red')
                                    ) ;

                                if (confirmBtn && confirmBtn.offsetParent !== null) {
                                    clearInterval(timer);
                                    setTimeout(() => {
                                        confirmBtn.click();
                                        console.log(`已确认取消 $${targetNum.toLocaleString()}`);
                                        resolve();
                                    }, 1000);
                                }

                                if (attempts > 50) {
                                    clearInterval(timer);
                                    console.warn('确认按钮超时，可能弹窗被拦截或已自动关闭');
                                    resolve();
                                }
                            }, 1000);
                        });

                        found = true;
                        break;
                    }
                }
            }

            if (!found) {
                console.warn(`未找到 $${targetNum.toLocaleString()} 的挂单（或已被取消）`);
            }

            await new Promise(r => setTimeout(r, 1000));
        }
    }

    delay(ms) { return new Promise(r => setTimeout(r, ms)); }
}

// ==================== 全局实例 ====================
const btcAutoTrader = new BTCAutoTrading();

// ==================== 快捷指令 ====================
btcAutoTrader.startAutoTrading(5000);    // 启动交易
// btcAutoTrader.stopAutoTrading();         // 停止交易
// btcAutoTrader.getStatus();               // 查看状态（含风控冷却信息）
// btcAutoTrader.clearOrderHistory();       // 清空记录
// btcAutoTrader.cancelAllOrder();          // 关闭所有挂单
// btcAutoTrader.resetRiskCooldown();       // 手动重置风控冷却