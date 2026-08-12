# `.generated` — 各交易所 / 服务密钥

每个项目一个 JSON，策略启动时会自动合并到对应 `exchanges.<name>` 配置。

## 文件

| 文件 | 用途 |
|------|------|
| `standx.json` | StandX API Token / signing_key |
| `grvt.json` | GRVT api_key / private_key |
| `hype.json` | Hyperliquid API Wallet |
| `lighter.json` | Lighter API key pair |
| `popdex.json` | PopDEX wallet + agent |
| `arcus.json` | Arcus Ed25519 API key |
| `ondo.json` | Ondo key_id + api_secret |
| `telegram.json` | 共用 bot_token / chat_id |
| `twelvedata.json` | Twelve Data 免费 API key（估值曲线日线价格备用源） |

## 用法

```bash
cp .generated/popdex.json.example .generated/popdex.json
# 编辑填写真实值
```

`*.json` 已被 gitignore；仅 `*.example.json` 与本 README 入库。
