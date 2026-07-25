# Ondo Perps 文档整理

> 官方文档索引：https://docs.ondoperps.xyz/llms.txt  
> 网站：https://ondoperps.xyz · App：https://app.ondoperps.xyz  
> 本目录基于官方文档全文抓取整理（见 `_raw/`，共 132 页 + OpenAPI），便于本仓库对接与策略研发。

---

## 1. 产品是什么

**Ondo Perps** 是面向 **股权 / 指数 / 商品** 的永续合约平台（USD 结算），由 Ondo Finance 技术驱动，与代币化股票基础设施（Ondo Global Markets）同源。

| 维度 | 说明 |
|------|------|
| 标的 | 股票永续（AAPL、NVDA…）、指数（US500、US100）、商品（XAU、XAG、WTI）等，市场名以 `.P` 结尾 |
| 杠杆 | 最高约 20x（按市场不同，如 MU 仅 5x） |
| 抵押品 | USDC + 代币化股票（如 QQQon / SPYon，有 haircut 与计入上限） |
| 交易时段 | 宣称 24/7；美股盘外/周末有独立 mark / funding 规则 |
| 合规 | 美国、巴拿马等禁止辖区不可用 |
| 阶段 | **Public Beta**：单市场持仓上限约 **$500,000**；新 API Key 创建默认关闭，需邮件申请 |

核心卖点：允许用 **代币化股票作保证金**，做市商可在同一场所做 spot+perp 对冲，避免「稳定币双倍占用」导致的簿深度不足。

---

## 2. 架构（对接机器人时最重要）

Ondo 是 **链下撮合 + 链上充提托管**，**不是** PopDEX 那种「Agent 签名 → 链上预编译下单」。

```
用户钱包
  ├─ SIWE 登录 / API Key ──► REST / WSS（业务：下单、撤单、仓位）
  └─ 链上转账到充值地址 ──► Chain-Core ──► Exchange-Engine 记账

Exchange-Engine（链下，SGX 飞地）
  · 撮合 / 保证金 / 强平 / 订单簿
Attestor Network
  · 校验飞地二进制、密钥分片
Chain-Core（链上）
  · 只处理充提，不知道内部账户结构
```

对策略机器人的含义：

- 下单成功 = REST `2xx` + 返回 `orderId`（可再订 WSS `ordersPerps`）
- **无需** `eth_sendRawTransaction` / Agent / nonce
- 本仓库对接应做成类似 StandX/Hype 的 `ondo_protocol` + `BasePerpAdapter`，而不是 PopDEX 链上路径

---

## 3. 环境与端点

| 环境 | REST | WebSocket |
|------|------|-----------|
| Production | `https://api.ondoperps.xyz` | `wss://api.ondoperps.xyz/ws` |
| Sandbox | Builder 指南中的 sandbox 域名（如 `app.ondoperps-sandbox.xyz`） | 对应 sandbox WSS |

健康检查：

- `GET /hello`
- `GET /status`

OpenAPI 离线副本（本目录）：

- `_raw/api-reference__rest-spec.json`
- `_raw/api-reference__ws-spec.json`
- `_raw/api-reference__openapi.json`
- `_raw/gm-be-api-spec.json`

---

## 4. 鉴权

支持两种方式（多数交易接口两者皆可）：

### 4.1 API Key（推荐给机器人）

1. 网页登录 → API Keys → 创建（**Public Beta 新 Key 可能需邮件开通**）
2. 务必保存 **secret**（只返回一次）；建议配置 IP 白名单（最多 16 个 IPv4）

REST 请求头（以官方「API Key Authentication」为准）：

| Header | 含义 |
|--------|------|
| `ONDO-KEY-ID` | Key ID（含 `ondoKeyId_` 前缀） |
| `ONDO-TIMESTAMP` | Unix 毫秒；与服务器相差须在 **±30 秒** |
| `ONDO-SIGN` | HMAC-SHA256(secret, `timestamp + METHOD + requestPath + body`) 的 hex |

其中 `requestPath` = 完整 path + query（不含 host）；`METHOD` 大写；`body` 为原始 body 字符串（GET 通常为空）。

常见错误码：`api_key_not_found` / `timestamp_too_far` / `signature_mismatch` / `ip_not_permitted` / `key_doesnt_have_scope`。

### 4.2 SIWE → JWT（人类 / Builder）

1. `POST /v1/auth/erc-4361/login/get_challenge`
2. 钱包签名挑战
3. `POST /v1/auth/erc-4361/login/complete_challenge` → JWT
4. 后续 `Authorization: Bearer <JWT>`
5. `GET /v1/auth/invalidate_jwt` 可作废

提现地址簿另有一套 SIWE address book challenge。

### 4.3 WebSocket 登录

连接：`wss://api.ondoperps.xyz/ws`

- JWT：`{"op":"login","args":{"token":"<JWT>"}}`
- API Key：`{"op":"login","args":{"key","time","sign"}}`  
  签名：`HMAC-SHA256(secret, "ondo_perps_ws_login" + time)`（以官方 login 文档为准）

心跳：`{"op":"ping"}` → `{"type":"pong"}`；空闲约 **180s** 断开。  
限速：约 25 req/s（burst 50）；消息最大约 32KB。

---

## 5. 市场与费率（概念层）

### 5.1 市场命名

全部为 **USD 结算永续**，名称形如 `AAPL-USD.P`。

| 类别 | 示例 | 典型最大杠杆 |
|------|------|--------------|
| 股权 | AAPL / NVDA / TSLA / META / SPCX… | 多为 10x；AAPL 等可达 20x；MU 5x |
| 指数 | US500-USD.P、US100-USD.P | 20x |
| 商品 | XAU / XAG / WTI | 20x |
| ETF | DRAM-USD.P | 10x |

Public Beta 默认 **每账户每市场** 持仓名义上限约 **$500,000**。  
下单前应用 `GET /v1/markets` 读取 `baseIncrement` / `quoteIncrement` 对齐数量与价格。

### 5.2 手续费

官方 `fees.md`（促销期）：

| 类型 | 促销费率（约） | 基础费率（划线） |
|------|----------------|------------------|
| Maker | 0.01%（1bp） | 0.02% |
| Taker | 0.025%（2.5bps） | 0.05% |

另有 14 日成交量阶梯、Builder/Referral；强平费约 **1.5%** 名义进入保险基金（可因保证金不足下调）。

> `markets.md` 另有一组 0.015% / 0.035% 表，与 `fees.md` 促销表述不完全一致；**以 fees 页与账户实际成交为准**。

### 5.3 资金费率

- **每小时**结算（UTC 整点），纯多空对赌，协议不抽成
- Premium 约每分钟采样，区间内平均；含 interest 与平滑因子；单小时费率硬顶约 **±1%/hour**
- 盘外/周末：oracle / mark 规则见 `weekend-trading.md`、`weekend-mechanics.md`

---

## 6. REST API 速查（按策略需求）

Base：`https://api.ondoperps.xyz`

### 6.1 行情（多数可公共访问）

| Method | Path | 用途 |
|--------|------|------|
| GET | `/v1/markets` | 市场元数据、精度 |
| GET | `/v1/perps/contracts` | 合约与行情摘要 |
| GET | `/v1/perps/depth` | 订单簿快照 |
| GET | `/v1/perps/mark_prices` | Mark |
| GET | `/v1/perps/trades` | 公共成交 |
| GET | `/v1/perps/candles` | K 线 |
| GET | `/v1/perps/funding_rates` | 当前区间资金费率估计 |
| GET | `/v1/perps/funding_rate_history` | 历史资金费率 |
| GET | `/v1/perps/open_interest` | OI |
| GET | `/v1/perps/volume` | 24h 量 |
| GET | `/v1/perps/history` / `/v1/perps/symbol_info` | TradingView UDF |

### 6.2 账户 / 保证金 / 仓位（需鉴权）

| Method | Path | 用途 |
|--------|------|------|
| GET | `/v1/account` | 账户信息 |
| GET | `/v1/perps/balance` | 保证金余额摘要 |
| GET | `/v1/perps/positions` | 持仓 |
| GET/POST | `/v1/perps/leverage` | 查/设杠杆 |
| GET | `/v1/perps/max_order_size` | 最大可下单量 |
| GET | `/v1/perps/orders_summaries` | 挂单与仓位保证金摘要 |
| GET | `/v1/counts/orders` | 各市场挂单数量 |
| GET | `/v1/perps/liquidation_history` | 强平历史 |
| GET | `/v1/portfolio/summary` | 组合摘要 |
| GET | `/v1/funding_fees` 相关 | 资金费流水（见 funding 组） |

### 6.3 订单（网格核心）

| Method | Path | 用途 |
|--------|------|------|
| POST | `/v1/perps/orders` | 创建限价/市价单 |
| POST | `/v1/perps/orders/batch` | 批量下单（1–20） |
| GET | `/v1/perps/orders` | 订单列表（分页） |
| GET | `/v1/perps/orders/{orderID}` | 单笔查询；可用 `client:{clientOrderID}` |
| DELETE | `/v1/perps/orders/{orderID}` | 单笔撤单 |
| DELETE | `/v1/perps/orders/batch?orderIDs=` | 批量撤；ID 可用 `client:...` |
| DELETE | `/v1/perps/orders` | 全撤（可按 market） |
| GET | `/v1/perps/fills` | 成交 |
| GET | `/v1/perps/orders/{orderID}/fills` | 某订单成交 |

**创建订单 body（`AddOrderReq`）要点：**

```json
{
  "market": "AAPL-USD.P",
  "side": "buy",
  "type": "limit",
  "price": "227.50",
  "size": "10.00",
  "clientOrderId": "grid-buy-01",
  "timeInForce": "GTC",
  "postOnly": true,
  "reduceOnly": false
}
```

| 字段 | 说明 |
|------|------|
| `side` | `buy` / `sell`（必填） |
| `market` | 如 `AAPL-USD.P`（必填） |
| `type` | `limit`（默认）/ `market` |
| `price` | 限价；对齐 `quoteIncrement`；市价省略 |
| `size` | 基础货币数量；对齐 `baseIncrement` |
| `quoteSize` | 仅市价买单可用（按报价货币） |
| `timeInForce` | `GTC` / `IOC`；市价不可设 |
| `postOnly` | `true` 若会立即成交则 `400 post_only_has_match` |
| `reduceOnly` | 仅减仓 |
| `clientOrderId` | ≤64，字母数字/`_`/`-` |
| `takeProfit` / `stopLoss` | 可挂在下单 payload 上 |

成功响应 `result` 含 **`orderId`（字符串）**、`status`（如 `open`）、`filledSize` 等。  
`orderId` 为十六进制风格字符串，**不要假设为 int**。

常见下单错误码（节选）：`insufficient_margin`、`post_only_has_match`、`order_price_outside_safe_bounds`、`too_many_open_orders`、`trading_disabled`、`net_position_too_large`、`clientOrderID_collision`。

### 6.4 止损 / TWAP / 沙盒 / 钱包

| 能力 | 路径摘要 |
|------|----------|
| 仓位级 TP/SL | `GET/POST/DELETE /v1/perps/stop_order` |
| TWAP | `/v1/perps/twap/order` 创建/查询/取消；时长 5min–24h |
| Sandbox 充提 | `POST /v1/sandbox_deposit`、`/v1/sandbox_withdrawal` |
| 充值地址 | `POST /v1/provision_address`、`POST /v1/wallet/deposit_address/list` |
| 提现 | `POST /v1/withdraw` + address book / limits |

---

## 7. WebSocket 频道

连接后：公共频道可直接 `subscribe`；私有频道须先 `login`。

### 7.1 公共

| Channel | 用途 |
|---------|------|
| `topOfBooksPerps` | 最优买卖 |
| `depthBooksPerps` | 深度 |
| `tradesPerps` | 成交 |
| `markPricesPerps` | Mark |
| `fundingRatesPerps` | 资金费率 |
| `kLinePerps` | K 线 |
| `liquidationAnnouncementsPerps` | 强平公告 |

### 7.2 私有

| Channel | 用途 |
|---------|------|
| `ordersPerps` | 订单更新（网格确认挂单极有用） |
| `fillsPerps` | 成交 |
| `positionsPerps` | 仓位 |
| `balancePerps` | 余额 |
| `ordersSummariesPerps` | 挂单摘要 |
| `fundingPaymentsPerps` | 资金费支付 |
| `liquidationPerps` | 强平事件 |
| `marginTransfersPerps` | 保证金划转 |
| `cancelAllOrdersAfterPerps` | Dead Man’s Switch |
| `deposits` / `withdrawals` | 充提 |

服务端推送形态：`{"type":"update","channel":"...","data":...}`。

---

## 8. 交易与风控概念（文档要点）

| 主题 | 文档 | 摘要 |
|------|------|------|
| 代币化抵押 | `overview.md` / `collateral-*.md` | 市值 × haircut 计入保证金；有 credited cap（如 $100k）；抵押品波动会改变保证金健康 |
| 杠杆 | `leverage.md` | 按市场设置；降杠杆可能因保证金不足失败 |
| 强平 / 保险 | `def.md` | 维持保证金、保险基金；强平费 |
| ADL | `auto-deleveraging.md` | 保险不足时自动减仓 |
| Mark 保护 | `mark-price-protection.md` | 限制异常 mark |
| 定价 | `pricing-derivations.md` / `premium-index.md` | 外部定价与溢价指数 |
| 结算 | `settlement.md` | 盈亏与结算机制 |
| 周末 | `weekend-trading.md` | 盘外交易与定价差异 |
| 订单类型 | `order-types.md` | Market / Limit / TP-SL / TWAP |
| 首次下单 UI | `placing-your-first-order.md` | 面向人机界面 |

---

## 9. Builder 集成（可选）

见 `_raw/api-reference__integration_guide.md`：

1. 连接钱包 → SIWE → JWT  
2. 接受 TOS → 充值（生产链上；沙盒可用 sandbox deposit）  
3. 每笔订单可带 **builderCode**，路由成交收增量手续费  

机器人若只自用交易，**API Key 路径更简单**，无需 Builder 流程。

---

## 10. 与本仓库适配建议

对接 `grid_mm.py` / `BasePerpAdapter` 时建议：

| 适配器方法 | Ondo 映射 |
|------------|-----------|
| `connect` | 校验 `/hello` 或 `/v1/account` + API Key 签名 |
| `get_ticker` | `contracts` / `mark_prices` / `top of book` |
| `get_open_orders` | `GET /v1/perps/orders`（过滤 open） |
| `place_order` | `POST /v1/perps/orders`，网格建议 `postOnly=true`、`timeInForce=GTC` |
| `cancel_order` / `cancel_orders_by_ids` | `DELETE .../{id}` 或 batch（支持 `client:`） |
| `cancel_all_orders` | `DELETE /v1/perps/orders` |
| `get_positions` / `get_balance` | `/v1/perps/positions`、`/v1/perps/balance` |

注意：

1. **市场是 RWA `.P`，不是 BTCUSDT**；网格价位参数要按股票价格数量级配置  
2. **`orderId` 为字符串**；与 PopDEX 一样不要 `int()` 强转丢失  
3. Public Beta 限制多，先确认 API Key 权限与持仓上限  
4. 协议层已落地：`exchange/exchange_ondoperp/ondoperp_protocol/`（对齐 `popdex_protocol`）；适配器 `adapters/ondo_adapter.py` 可后续接入

---

## 11. 本目录结构

```
exchange/exchange_ondoperp/doc/
├── README.md                 # 本整理文档
├── llms.txt                  # 官方文档索引镜像
├── _fetch_manifest.json      # 抓取清单
└── _raw/                     # 官方页面原文（*.md / *.json）
    ├── about.md
    ├── architecture.md
    ├── markets.md
    ├── api-reference__orders__create-order.md
    ├── api-reference__rest-spec.json
    ├── api-reference__ws-spec.json
    └── ...（共 132 个文件）
```

重新抓取示例：

```bash
# 依赖 requests；从 llms.txt 并行拉取全部链接到 _raw/
python -c "print('见仓库历史抓取脚本或自行按 llms.txt 下载')"
```

官方原文更新时，以 https://docs.ondoperps.xyz/llms.txt 为准，可覆盖 `_raw/` 后修订本 README。

---

## 12. 联系方式（官方）

- 支持：support@ondoperps.xyz  
- Builder：builders@ondoperps.xyz  
- 详见 `_raw/contact.md`、`_raw/public-beta.md`

---

*整理日期：基于 docs.ondoperps.xyz 全量镜像；若与线上冲突，以官网为准。*
