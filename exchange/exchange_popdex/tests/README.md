# PopDEX 协议层测试 / 冒烟脚本

## 结构（对齐 standx_protocol）

```
exchange/exchange_popdex/popdex_protocol/
  __init__.py
  perps_auth.py   # Agent Key + EIP-712
  perp_http.py    # REST + Web3 RPC + place_order_onchain
  perps_wss.py    # 公共 WebSocket
  orders.py       # placeOrder 编码 / Agent 免 Gas 签名
```

## 依赖

项目根目录 `requirements.txt` 已包含 `requests` / `web3` / `eth-account`。
WebSocket 需要 `websockets`（与 StandX 相同）。

```bash
pip install -r ../../../requirements.txt
pip install websockets
```

## 公共接口冒烟（无需私钥）

```bash
cd exchange/exchange_popdex/tests
python run_public.py
python run_public.py --network testnet --symbol BTCUSDT --ws
```

## 创建并授权 Trade Agent

网页目前没有导出 Agent 私钥入口。用主钱包私钥本地生成并 `approveAgent`：

```bash
export POPDEX_WALLET_KEY="0x你的主钱包私钥"   # 注意：是主钱包，不是 Agent

python create_agent.py --dry-run
python create_agent.py --save ./agent.key

# 成功后
export POPDEX_WALLET_ID="0x主钱包地址"
export POPDEX_AGENT_KEY="0x脚本输出的Agent私钥"
python run_trade.py
```
