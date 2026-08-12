# strategy_vs：双所价差对比（回测/实盘同一策略核心）

策略核心在 `vs_core.VSStrategy`，只依赖两条腿报价/持仓，不绑交易所。
- 腿 A：信号腿（挂 maker 限价，吃价差）
- 腿 B：对冲腿（净敞口偏离 0 时市价对冲）

## 回测（基于 `data/` 下已下载 OHLCV）

```bash
python -m strategys.strategy_vs.vs_backtest -c strategys/strategy_vs/config_vs_example.yaml
```

说明：
- 两腿数据按 `date` inner join；可用 `backtest.timerange` 裁剪交集
- 撮合：限价单用 `low<=price<=high` 判断可成交，成交价取 `min(price, close)`/`max(price, close)`（保守近似，不代表盘口排队）
- `spread_bps` 用于从 close 近似 bid/ask；`use_bidask_for_spread=false` 则直接比 close
- 腿 B 对冲用市价（按 close）

## 实盘（先 dry-run）

```bash
python -m strategys.strategy_vs.vs_live -c strategys/strategy_vs/config_vs_example.yaml --dry-run
```

- 交易所连接在 `exchanges:`，密钥放 `.generated/{exchange}.json`
- 腿映射在 `live.legs`（指向 `exchanges` 下的键）
- `--dry-run` 只打印动作，不下单

## 与 strategy_compara 的关系

compara 是多线程 + 各所专用 WSS，难以回测；本策略把**逻辑抽成纯函数**，行情/成交通过统一接口注入，因此同一套逻辑既能跑 CSV 回测，也能接实盘适配器。

## 阈值怎么设

| `threshold_mode` | 含义 | 适用 |
|--|--|--|
| `fixed` | 写死 `min/max_profit_pct` | 基线对照 |
| `quantile` | 滚动 lookback 分位数（默认） | **推荐起步**，对分布漂移更稳 |
| `zscore` | 滚动均值 ± Nσ | 近似正态时可用 |

自适应时仍用 `min_edge` 做成本下限；warmup 不足时回退到 fixed 兜底。
