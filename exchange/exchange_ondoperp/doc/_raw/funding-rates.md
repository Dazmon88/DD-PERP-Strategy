> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Funding Rates

## Overview

Funding rates keep perpetual contract prices aligned with the underlying oracle price. They are periodic payments between long and short holders: when the contract trades above the oracle price, longs pay shorts. When it trades below, shorts pay longs. This creates an economic incentive for traders to take positions that push the contract price back toward the oracle.

Funding on Ondo Perps is **purely peer-to-peer**. The protocol takes no cut. Every dollar debited from one side is credited to the other. The Insurance Fund is not involved in funding settlement.

## Funding Interval

Funding is paid **every hour**, 24 times per day. Intervals align to UTC hour boundaries (0:00, 1:00, 2:00, ... 23:00 UTC). The rate is applied on the first tick after each hour boundary.

## Scaling Factors

All production markets share these defaults:

| **Parameter**     | **Value**                | **What it means**                                               |
| :---------------- | :----------------------- | :-------------------------------------------------------------- |
| Funding interval  | 1 hour                   | How often funding settles                                       |
| Premium sampling  | Every minute             | 60 samples averaged per interval                                |
| Smoothing divisor | 8                        | A sustained premium pays out over \~8 hours, not in one shock   |
| Interest rate     | 0.03%/day (\~10.95% APR) | Baseline cost of carry when premium is zero                     |
| Rate cap          | +/-1%/hour               | Hard ceiling, derived from margin safety constraint (see below) |

## Funding Rate Formula

The funding rate combines two components: the **average premium index** (how far the perp is from the oracle) and a fixed **interest rate** (the assumed cost of borrowing USDC to hold a position).

**Step 1: Average the premium**

The 60 per-minute premium index samples from the hour are averaged, then divided by 8:

```text theme={null}
Average Premium = mean(premium index samples) / 8
```

Dividing by 8 means only 1/8th of the premium is transferred per hourly interval. It takes 8 hours of sustained premium to transfer the full amount. This follows the industry-standard design of computing an 8-hour funding rate and paying it in hourly installments. This produces a smoother per-hour cash flow than venues that pay the full 8-hour rate every 8 hours.

**Step 2: Combine with interest rate**

```text theme={null}
Interest = 0.0003 / 24 = 0.0000125 per hour
Funding Rate = Average Premium + clamp(Interest - Average Premium, Interest - Damping Range)
```

The interest rate is fixed at **0.03% per day** (equivalent to 0.01% per 8 hours, or \~10.95% APR). This represents the assumed cost difference between holding the underlying asset (0% rate) and borrowing USDC.

The damping range creates a small dead zone: when the average premium is close to the interest rate, the funding rate collapses to the interest rate rather than oscillating.

**Step 3: Cap**

```text theme={null}
Funding Rate = clamp(Funding Rate, -1%, +1%)
```

The funding rate is capped at **1% per hour** in either direction.

This cap is not arbitrary. The platform enforces an invariant at configuration time:

```text theme={null}
fundingRateCap ≤ 0.75 × (initialMarginRate − maintenanceMarginRate)
```

The gap between initial margin and maintenance margin is the liquidation buffer, the cushion a max-leverage position has before liquidation triggers. The cap is set to at most 75% of that buffer, so even a worst-case funding hour only consumes three-quarters of the cushion. The remaining 25% gives you time to react (add margin, reduce size) before the next funding tick.

In practice, the configured 1% cap sits well below the constraint for every tier:

| **Tier**     | **Initial Margin** | **Maintenance Margin** | **Buffer** | **0.75 x Buffer** | **Configured Cap** |
| :----------- | :----------------- | :--------------------- | :--------- | :---------------- | :----------------- |
| 20x leverage | 5%                 | 2.5%                   | 2.5%       | 1.875%            | 1%                 |
| 10x leverage | 10%                | 5%                     | 5%         | 3.75%             | 1%                 |

A single hour of max funding cannot, by itself, liquidate a margin-compliant position.

## Interest Rate Across Time Periods

| **Period**  | **Interest Rate** |
| :---------- | :---------------- |
| Per hour    | 0.00125%          |
| Per 8 hours | 0.01%             |
| Per day     | 0.03%             |
| Annualized  | \~10.95% APR      |

When the perpetual contract trades exactly at the oracle price (zero premium), the funding rate equals the interest rate: longs pay shorts 0.00125% per hour. This reflects the cost of carry of a USDC-funded long position in the underlying.

## Funding Payment

Each hour, every open position receives or pays a funding fee:

```text theme={null}
Funding Payment = Position Size × Oracle Price × Funding Rate
```

The oracle price (not the exchange mid-price) is used to convert position size to notional value. If the funding rate is positive, longs are debited and shorts are credited. If the funding rate is negative, the reverse applies.

The payment is applied directly to your wallet balance and reflected immediately in your margin balance.

## Worked Example

TSLA is trading at a premium to the oracle. You are **long 100 TSLA** with an oracle price of **\$250**.

**Premium index calculation:**

The orderbook impact prices for a \$1,000 simulated order are:

* Impact Bid = \$251.50
* Impact Ask = \$252.00
* Oracle Price = \$250.00

```text theme={null}
Premium Index = (max($251.50 - $250, 0) - max($250 - $252, 0)) / $250
             = ($1.50 - $0) / $250
             = 0.006 (0.6%)
```

This sample is positive, meaning the perp is trading above the oracle.

**Funding rate calculation:**

Assume the average premium index over the hour is 0.48% (other samples were lower). Divide by 8:

```text theme={null}
Average Premium = 0.0048 / 8 = 0.0006
```

Combine with the hourly interest rate:

```text theme={null}
Interest = 0.0000125
Funding Rate ≈ 0.0006 + clamp(0.0000125 - 0.0006, -0.0000625, +0.0000625)
             = 0.0006 + (-0.0000625)
             = 0.0005375 (0.05375%)
```

This is within the +/-1% cap, so no clamping.

**Funding payment:**

```text theme={null}
Funding Payment = 100 × $250 × 0.0005375 = $13.44
```

As a long holder with a positive funding rate, you **pay \$13.44** this hour. This amount is debited from your wallet balance. Short holders of equivalent size collectively receive the same amount.

## More Examples

All examples assume production scaling factors and a long \$1,000 notional position.

**Market at rest (zero premium)**

The perp trades right on the oracle for an hour, so the average premium is zero. Zero falls inside the +/-0.00625% damping band around the 0.00125%/hr interest rate, so damping fires and the funding rate equals the interest rate:

```text theme={null}
Funding Rate = 0.00125%/hr
Payment = 0.0000125 × $1,000 = $0.0125/hr
```

Longs pay shorts about a cent per hour per \$1,000 of notional. This is the "cost of carry" baseline.

**Extreme premium hitting the cap (10% sustained)**

The perp trades 10% above the oracle for a full hour. The premium component is 10% / 8 = 1.25%/hr, well above the 1% cap:

```text theme={null}
Uncapped Rate ≈ 1.245%/hr
Funding Rate = clamp(1.245%, -1%, +1%) = 1%/hr
Payment = 0.01 × $1,000 = $10/hr
```

This is the worst case. Even so, because the 1% cap sits below the maintenance margin buffer (see Step 3 above), this cannot liquidate a margin-compliant position in a single hour.

## Data Quality

The funding rate depends on 60 premium samples per hour. If too many samples are missing, the rate could be distorted. To guard against this, the platform checks for gaps between consecutive samples: if the largest gap within the hour exceeds **6 minutes**, funding for that hour is set to zero. No payment is exchanged, and the system logs a warning.

This means a brief oracle interruption (under 6 minutes) is tolerated, but a sustained data gap causes funding to pause rather than publish a rate based on incomplete information.

## Closed Underlying Market

When the underlying market is closed and there is no external oracle price, premium samples for those minutes are calculated using an internal price derived from the exchange's orderbook data. Funding rates are still paid but can be much larger as a consequence of the price discovery mechanism.

## Learn More

<CardGroup cols={2}>
  <Card title="Premium index" icon="ruler" href="/premium-index">
    The premium-index formula, impact prices, and how mark-vs-book is measured.
  </Card>

  <Card title="Mark price protection" icon="shield-check" href="/mark-price-protection">
    Where the mark price comes from and how it's aggregated.
  </Card>

  <Card title="Fees" icon="receipt" href="/fees">
    Maker, taker, liquidation fees, and how funding differs from a fee.
  </Card>

  <Card title="Liquidations and insurance" icon="droplet" href="/def">
    The full liquidation waterfall and how the funding-rate cap interacts with maintenance margin.
  </Card>
</CardGroup>
