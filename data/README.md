# OHLCV 数据目录

由 `python -m tools.download_data` 写入。

## 布局

```text
data/
  arcus/BTC_USD-5m.csv
  popdex/BTCUSDT-5m.csv
  hype/BTC-5m.csv
  ondo/XAU_USD.P-5m.csv
```

## 列

`date,open,high,low,close,volume`（UTC）

## 示例

```bash
# 长区间（默认 sleep=0.35 + 429 重试；已有文件则增量续传）
python -m tools.download_data -e arcus -p BTC-USD -t 5m --timerange 20240615-20260701

# Ondo Perps（公开 history，无需 API Key；5m 约可回看 ~5 周）
python -m tools.download_data -e ondo -p BTC-USD.P -t 5m --days 14
python -m tools.download_data -e ondoperp -p XAU-USD.P -t 5m --days 7

# 限流严重时可加大间隔
python -m tools.download_data -e arcus -p BTC-USD -t 5m --days 30 --sleep 0.8 --retries 8

# PopDEX 细周期留存很短（BTCUSDT 5m 约从 2026-07-04 起）；两年区间会空
python -m tools.download_data -e popdex -p BTCUSDT -t 5m --days 30 --erase
```

## 行为

- **`--sleep`**：分页请求间隔（默认 0.35s）
- **`--retries` / `--retry-base-sleep`**：遇 HTTP 429 指数退避重试
- **增量续传**：默认从本地 CSV 最后一根之后继续；`--erase` 全量重拉
