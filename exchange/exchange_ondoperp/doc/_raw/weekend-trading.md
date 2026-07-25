> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Weekend and Extended Hours Trading

## Oracle Price

The oracle price serves two critical functions:

* As the **reference price for funding rate** calculations.
* As a direct **input to the mark price** calculation.

Ondo Perps lists perpetuals on real-world assets whose underlying markets close on weekends and holidays. The exchange operates 24/7, but external price feeds go dark from Friday's equity close to Sunday evening (U.S. ET). To maintain continuous pricing, the system prioritizes external pricing when available and switches to an internal mechanism when it is not.

### External Pricing

During regular market hours, the oracle price is derived from external price feeds (Pyth, Stork, and other institutional data providers) that consume live market data for the underlying assets. The externally-derived fair price is used directly as the oracle price.

When external markets close at 4:00 PM ET on Friday, these feeds effectively freeze. The last traded price is broadcast on repeat, but no genuine price discovery occurs through external feeds until markets reopen.

### Internal Pricing

When external pricing becomes unavailable, the oracle switches to an **internal pricing session** that derives a continuously updating price from on-platform order book activity.

The internal oracle initializes from the last available external price at Friday's close. From that anchor, it tracks the exchange's own price discovery by measuring how far the order book has drifted from the current internal price.

This drift is captured by the **impact price difference (IPD)**:

```text theme={null}
IPD = max(Pb - S, 0) - max(S - Pa, 0)
```

Where:

* `S` is the previous internal oracle price
* `Pb` is the impact price on the bid (buy) side of the order book
* `Pa` is the impact price on the ask (sell) side of the order book

If the order book is skewed with more buying pressure, IPD is positive and the oracle moves up. If selling pressure dominates, IPD is negative and the oracle moves down. If the book is balanced around the current price, IPD is near zero and the oracle holds steady.

The IPD is then smoothed using a **continuous-time exponentially weighted moving average (EWMA)**:

```text theme={null}
S_t = β_t · S_{t⁻} + (1 - β_t) · x_t
β_t = exp(-Δt* / τ)
x_t = S_{t⁻} + IPD_t
```

Where:

* `S_t` is the new oracle price at time `t`
* `S_{t⁻}` is the previous oracle price
* `τ` is the time constant (1 hour)
* `Δt*` is the elapsed time since the last update (in seconds)

The continuous-time form means the EWMA decays correctly regardless of how frequently updates arrive, handling sparse weekend updates without accumulating staleness error.

### Session Transitions

When external markets close, the internal pricing session begins automatically, initializing from the last external price. When external data resumes (either from equity futures reopening Sunday evening or Monday's cash session), the oracle snaps back to the externally-derived price on the next update.

***

## Mark Price

The mark price is the price used for margining, liquidations, stop/limit triggers, and unrealized P\&L. It is intentionally separate from the oracle price to provide manipulation resistance: no single price input can simultaneously distort both funding rates and liquidation triggers.

### Three-Component Median

The mark price is computed as the **median of three components**:

| **Component**                                    | **Description**                                                                                                                                                                                                                                             |
| :----------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Oracle price**                                 | The current oracle price, whether externally-derived during market hours or internally-derived during the weekend session.                                                                                                                                  |
| **Oracle price + 150s EMA of basis**             | The oracle price plus a 150-second continuous-time EWMA of the difference between the perpetual's mid-price and the oracle price. This captures the current premium or discount of the perp relative to the oracle and smooths it over a 2.5-minute window. |
| **Median of best bid, best ask, and last trade** | The exchange's own top-of-book reference: the median of the best bid, best ask, and the most recent fill price.                                                                                                                                             |

The mark price is the **median** of (1), (2), and (3). Taking the median rather than averaging means a single outlier component, such as a temporarily spiked last trade during thin weekend liquidity, cannot move the mark price beyond what the second-closest component allows.

### Clamping

Mark price updates are clamped to **\~50 basis points** of the current mark price per update cycle. This prevents a single large oracle jump from instantly moving the mark price by the full amount. Instead, the mark price steps toward the new level over successive updates.

This is particularly important at the Sunday re-open, when the external price snaps back from the internal weekend price and may carry a gap.

### What Each Price Drives

The **mark price** drives:

* Unrealized P\&L calculation
* Margin ratio and available margin
* Liquidation and ADL triggers
* Stop-loss and take-profit order execution

The **oracle price** separately drives:

* Funding rate calculation
* Reference price for discovery bounds

This separation ensures that a spike or manipulation in one component cannot simultaneously distort both the funding rate and the liquidation price.

***

## Discovery Bounds

When external markets close, Ondo Perps traders continue to buy, sell, and speculate on an asset's fair price. To provide a safe venue for this extended-hours price discovery, the mark price is constrained within a defined range around the Friday closing price.

### How Discovery Bounds Work

The discovery range is determined by the market's maximum leverage:

```text theme={null}
Upper bound = Friday close price × (1 + 1 / max_leverage)
Lower bound = Friday close price × (1 - 1 / max_leverage)
```

**Example:** If TSLAon closed at \$200 on Friday and the market's max leverage is 20x:

```text theme={null}
Upper bound = $200 × 1.05 = $210
Lower bound = $200 × 0.95 = $190
Tradeable range: $190 – $210 (±5%)
```

The internal oracle price and mark price can move freely within this range based on genuine order book activity. Once the oracle reaches the upper or lower bound, no further price discovery occurs in that direction. Trading may continue within the established range, but the oracle is capped at the bound.

### Order Protection

The discovery bounds also serve as a valid trading region. Any order that would execute at a price outside the bounds is rejected. This prevents traders from buying above or selling below prices that have deviated too far from the last external anchor.

### When Bounds Reset

The bounds are released when external pricing resumes. The oracle snaps back to the live externally-derived price, and the discovery bounds no longer apply until the next extended session begins.

### Risk Management

Traders should size positions and set stop-losses with the full discovery range in mind. For a 20x leverage market, the oracle can move up to \~5% from Friday's close during the weekend. If your liquidation price lies outside the active discovery bounds, your position cannot be liquidated from price movement alone while those bounds are in effect.

***

## Funding Rate

Funding rates on perpetuals keep the perp price anchored to the oracle price. When the perp trades at a premium to oracle, longs pay shorts. When it trades at a discount, shorts pay longs. The funding rate is calculated using the oracle price as its reference.

### Weekend Funding

During extended sessions, the oracle price is derived from the internal pricing mechanism (see Oracle Price above) rather than external feeds. Funding continues to accrue normally using this internally-derived oracle as its reference, so the funding rate remains meaningful even when external markets are closed.

If the internal pricing mechanism lacks sufficient order book data, the premium index is zeroed out rather than calculated from stale or manipulable inputs. This ensures funding payments are never driven by unreliable price signals.

### Dampening Multiplier

Tokenized equity perpetuals carry structural differences from crypto perpetuals. Traditional assets have lower baseline volatility and a known carry cost. To reflect this, Ondo Perps applies a **0.5x dampening multiplier** to the funding rate formula for equity perp markets.

This reduces the baseline annualized funding rate from approximately 11% to approximately 5.5%, which:

* Better reflects the carry cost of holding exposure to traditional assets
* Reduces the feedback loop between funding payments and internal price discovery during weekends, where thin liquidity can amplify funding-driven price moves
