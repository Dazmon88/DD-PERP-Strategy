> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# External Pricing Derivations

The oracle price for every market on Ondo Perps is sourced from one or more independent external price feeds. This page describes which feeds are used for each asset class and how they're combined.

## Equity and ETF perpetuals

All equity and ETF perpetuals are priced using **direct spot prices** from two independent oracle sources, **Pyth** and **Stork**. Both provide continuous 24/5 pricing data for regular hour, post-market, overnight, and pre-market prices.

When both sources respond, the external price is the **average of Pyth and Stork**. If only one source responds, that price is used directly.

## Index perpetuals (US100, US500)

Indices do not have a direct spot market. Index perpetuals use Pyth futures feeds and convert futures prices to synthetic spot prices using the standard cost-of-carry relationship. This accounts for the risk-free rate, convenience yield, and time to expiration.

## Commodity perpetuals

Commodity perpetuals are priced differently depending on whether a liquid spot market exists for the underlying asset.

**Precious metals (Gold, Silver)** have deep, liquid spot markets, so their external price is sourced directly from spot price feeds.

**Energy commodities (WTI)** do not have spot markets as other assets do — the underlying price varies based on a range of factors, including delivery timing and geography. To derive an external price, the oracle uses an industry-standard approach that references a fixed set of designated futures contracts.

The underlying contract is rolled from the 5th to the 10th business day of each month, at predefined timestamps that correspond to internal pricing sessions. Over this window the external price transitions from the front (near) contract to the next contract:

| Business day | Front contract | Next contract |
| :----------- | :------------- | :------------ |
| 5th          | 100%           | 0%            |
| 6th          | 80%            | 20%           |
| 7th          | 60%            | 40%           |
| 8th          | 40%            | 60%           |
| 9th          | 20%            | 80%           |
| 10th         | 0%             | 100%          |

The roll schedule respects the CME holiday calendar.

## Learn more

<CardGroup cols={2}>
  <Card title="Mark price protection" icon="shield-check" href="/mark-price-protection">
    Why the platform uses an external oracle aggregate rather than the local last-traded price.
  </Card>

  <Card title="Premium index" icon="ruler" href="/premium-index">
    How the oracle price combines with local impact prices to form the premium index.
  </Card>
</CardGroup>
