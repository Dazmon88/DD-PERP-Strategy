> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Premium Index

The premium index measures how far the perpetual contract price has diverged from the oracle price. This divergence drives the funding rate: when the perp trades at a premium, longs pay shorts, incentivizing the price back toward the oracle. When it trades at a discount, shorts pay longs. The premium index is the mechanism that keeps perpetual futures prices anchored to their underlying assets.

The formula:

```text theme={null}
Premium Index = (max(Impact Bid - Oracle Price, 0) - max(Oracle Price - Impact Ask, 0)) / Oracle Price
```

## Impact Prices

The impact bid and ask prices are the volume-weighted average execution prices for a simulated order of a standard size against the order book:

* **Impact Bid Price:** Average fill price for a simulated sell order of the Impact Price Quote Size
* **Impact Ask Price:** Average fill price for a simulated buy order of the Impact Price Quote Size

## Impact Price Quote Size

The Impact Price Quote Size is **\$1,000 (notional) for all markets**. There is no per-market differentiation. This applies uniformly across all production markets (equities, indices, commodities, and ETFs).

## Interpretation

| **Condition**                          | **Premium Index** |
| :------------------------------------- | :---------------- |
| Oracle price within the bid-ask spread | Zero              |
| Perp trading above oracle (premium)    | Positive          |
| Perp trading below oracle (discount)   | Negative          |

The premium index is sampled every minute (60 samples per funding interval) and averaged over the hour to compute the funding rate.

## Learn More

<CardGroup cols={2}>
  <Card title="Funding rates" icon="hand-coins" href="/funding-rates">
    How the premium index combines with the interest rate to produce the hourly funding rate.
  </Card>

  <Card title="Mark price protection" icon="shield-check" href="/mark-price-protection">
    The external oracle price the premium index is measured against.
  </Card>
</CardGroup>
