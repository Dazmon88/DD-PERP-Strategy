# Ondo Perps 协议层测试 / 冒烟脚本

## 结构（对齐 popdex_protocol）

```
exchange/exchange_ondoperp/ondoperp_protocol/
  __init__.py
  perps_auth.py   # API Key HMAC + WSS login / JWT
  perp_http.py    # REST（行情 / 账户 / 下单撤单）
  perps_wss.py    # WebSocket
  orders.py       # AddOrderReq / clientOrderId 辅助
  account.py      # SIWE → JWT 辅助
```

## 依赖

```bash
pip install requests websockets
```

## 公共接口冒烟（无需密钥）

```bash
cd exchange/exchange_ondoperp/tests
python run_public.py
python run_public.py --market AAPL-USD.P --ws
```

## 交易冒烟（需 API Key）

Public Beta 下新 API Key 可能需邮件申请开通。

```bash
export ONDO_KEY_ID="ondoKeyId_..."
export ONDO_API_SECRET="ondoApiSecret_..."

python run_trade.py --dry-run
python run_trade.py --market AAPL-USD.P --side buy --price 100 --size 0.01 --post-only
```
