> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Markets

## Supported Markets

All markets are USD-settled perpetual contracts denoted by the `.P` suffix in the market name. Default maximum position size is \$500,000 per symbol, per account. For details on pricing outside of U.S. market hours see Weekend and Extended Hours Trading.

### Equity Perpetuals

| **Market**  | **Asset**         | **Max Leverage** |
| :---------- | :---------------- | :--------------- |
| AAPL-USD.P  | Apple             | 20x              |
| AMD-USD.P   | AMD               | 10x              |
| AMZN-USD.P  | Amazon            | 10x              |
| COIN-USD.P  | Coinbase          | 10x              |
| CRCL-USD.P  | Circle            | 10x              |
| GOOGL-USD.P | Alphabet (Google) | 10x              |
| HOOD-USD.P  | Robinhood         | 10x              |
| INTC-USD.P  | Intel             | 10x              |
| META-USD.P  | Meta              | 10x              |
| MSFT-USD.P  | Microsoft         | 10x              |
| MSTR-USD.P  | MicroStrategy     | 10x              |
| MU-USD.P    | Micron Technology | 5x               |
| NFLX-USD.P  | Netflix           | 10x              |
| NVDA-USD.P  | NVIDIA            | 10x              |
| ORCL-USD.P  | Oracle            | 10x              |
| PLTR-USD.P  | Palantir          | 10x              |
| SPCX-USD.P  | SpaceX            | 10x              |
| TSLA-USD.P  | Tesla             | 10x              |

### Index Perpetuals

| **Market**  | **Asset**  | **Max Leverage** |
| :---------- | :--------- | :--------------- |
| US500-USD.P | S\&P 500   | 20x              |
| US100-USD.P | Nasdaq 100 | 20x              |

### Commodity Perpetuals

| **Market** | **Asset**       | **Max Leverage** |
| :--------- | :-------------- | :--------------- |
| XAU-USD.P  | Gold            | 20x              |
| XAG-USD.P  | Silver          | 20x              |
| WTI-USD.P  | Crude Oil (WTI) | 20x              |

### ETF Perpetuals

| **Market** | **Asset**            | **Max Leverage** |
| :--------- | :------------------- | :--------------- |
| DRAM-USD.P | Roundhill Memory ETF | 10x              |

## Fees

| **Fee Type** | **Rate** |
| :----------- | :------- |
| Maker        | 0.015%   |
| Taker        | 0.035%   |

## Funding

| **Parameter**       | **Value**       |
| :------------------ | :-------------- |
| Daily Interest Rate | 0.03%           |
| Funding Rate Cap    | 1% per interval |
| Funding Intervals   | 8 per day       |

## Holiday Schedule (2026-2027)

Ondo Perps markets are open 24/7 but the underlying markets will be closed on the following dates. For details on pricing outside of U.S. market hours see Weekend and Extended Hours Trading.

| **Date**   | **Holiday**                 | **Status**               |
| :--------- | :-------------------------- | :----------------------- |
| 2026-04-03 | Good Friday                 | Closed                   |
| 2026-05-25 | Memorial Day                | Closed                   |
| 2026-06-19 | Juneteenth                  | Closed                   |
| 2026-07-03 | Independence Day (observed) | Closed                   |
| 2026-09-07 | Labor Day                   | Closed                   |
| 2026-11-26 | Thanksgiving                | Closed                   |
| 2026-11-27 | Day after Thanksgiving      | Early close (1:00 PM ET) |
| 2026-12-24 | Christmas Eve               | Early close (1:00 PM ET) |
| 2026-12-25 | Christmas                   | Closed                   |
| 2027-01-01 | New Year's Day              | Closed                   |
