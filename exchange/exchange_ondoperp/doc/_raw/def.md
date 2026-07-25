> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Liquidations and Insurance

## **Overview**

Liquidation occurs when your margin balance falls below your total maintenance margin requirement. Ondo Perps uses cross margin, meaning all of your positions share a single collateral pool. A loss on one position affects the health of your entire account.

The liquidation system is designed to close positions at the best available price on the order book before resorting to more aggressive mechanisms. Each stage of the process prioritizes retaining as much of your remaining capital as possible.

***

## **Margin and Liquidation Trigger**

### **Maintenance Margin**

Each market has its own maintenance margin rate, tiered by position size. Larger positions require proportionally more margin. Example rates: 2.5% for liquid markets, 5% for less liquid ones.

The formula for a single position:

`maintenance_margin = position_notional * maintenance_margin_rate - maintenance_amount`

The `maintenance_amount` is a smoothing term that prevents sudden jumps when a position crosses from one size tier to the next. Your total maintenance margin is the sum across all open positions.

### **Liquidation Trigger**

Liquidation triggers when:

`margin_balance < total_maintenance_margin`

Where `margin_balance = wallet_balance + unrealized_pnl`.

***

## **Liquidation Price**

The liquidation price is the mark price at which your margin balance would fall below the maintenance margin requirement. For a long position, it is below your entry price. For a short, it is above.

### **Formula**

`liq_price = (margin_balance + maintenance_amount - other_positions_maintenance - side_notional) / (position_quantity * (maintenance_margin_rate +/- 1))`

Where:

| **Variable**                  | **Definition**                                              |
| :---------------------------- | :---------------------------------------------------------- |
| `margin_balance`              | wallet balance + unrealized PnL across all positions        |
| `maintenance_amount`          | tier smoothing coefficient for this position's market       |
| `other_positions_maintenance` | total maintenance margin from all other open positions      |
| `side_notional`               | position notional (positive for longs, negative for shorts) |
| `position_quantity`           | size of the position                                        |
| `maintenance_margin_rate`     | rate for this position's size tier                          |
| `+/-`                         | minus 1 for longs, plus 1 for shorts                        |

Because Ondo Perps uses cross margin, your liquidation price on any position depends on your entire account: all other positions, their unrealized PnL, and total maintenance requirements.

A negative liquidation price (possible for well-collateralized longs) is displayed as zero.

***

## **Worked Example**

A trader deposits \$1,000 USDC and opens a 10x long on NVDA at \$130, buying 76.92 shares (\$10,000 notional).

| **Metric**              | **Value** |
| :---------------------- | :-------- |
| Position notional       | \$10,000  |
| Leverage                | 10x       |
| Initial margin (10%)    | \$1,000   |
| Maintenance margin (5%) | \$500     |
| Margin ratio at entry   | 50%       |

### **NVDA drops to \$126.50**

Unrealized loss: 76.92 x (\$130 - \$126.50) = \~\$269

| **Metric**         | **Value** |
| :----------------- | :-------- |
| Margin balance     | \$731     |
| Maintenance margin | \$487     |
| Margin ratio       | 66.6%     |

Not yet in liquidation, but margin ratio is rising.

### **NVDA drops to \$123.50**

Unrealized loss: 76.92 x (\$130 - \$123.50) = \~\$500

| **Metric**         | **Value** |
| :----------------- | :-------- |
| Margin balance     | \$500     |
| Maintenance margin | \$475     |
| Margin ratio       | 95%       |

Close to liquidation. Depositing USDC or reducing the position would lower the margin ratio.

### **NVDA drops to \$123.00**

Unrealized loss: 76.92 x (\$130 - \$123.00) = \~\$538

| **Metric**         | **Value** |
| :----------------- | :-------- |
| Margin balance     | \$462     |
| Maintenance margin | \$473     |
| Margin ratio       | 102%      |

Margin balance has fallen below maintenance margin. **Liquidation is triggered.** The system freezes the account, cancels all resting orders, and begins partially liquidating the NVDA position.

***

## **Liquidation Process**

When liquidation triggers, the system follows a multi-stage process. Each stage is more aggressive than the last, and the system stops as soon as the account is brought back above maintenance margin.

### **Stage 1: Order Cancellation**

All resting orders are immediately cancelled and the account is frozen (no new orders). Resting orders reserve margin but do not affect your liquidation price, so cancelling them may free enough margin to prevent position liquidation.

### **Stage 2: Liquidation via Order Book**

The system sends limit orders to the order book to close your positions, starting with the most liquid market. Positions above \$1,000 in notional value are liquidated partially, approximately 10% of the position at a time, with 5-second intervals between each chunk. This gives the book time to absorb the size and reduces market impact.

Positions at or below \$1,000 notional are liquidated in full.

A **1.5% liquidation fee** is charged on the filled notional value and sent to the insurance fund.

### **Stage 3: Insurance Fund Assistance**

If the position has not been fully closed after approximately 1 minute of retries, the insurance fund activates. It widens the acceptable liquidation price up to **5% worse than the current mark price**, making it easier for the order to fill against available book liquidity.

The insurance fund also activates immediately if the mark price crosses the **bankruptcy price** (the price at which your margin balance would equal zero), regardless of how much time has passed.

### **Stage 4: Auto-Deleveraging (ADL)**

If approximately 2 minutes have passed and the insurance fund balance is effectively exhausted (below \$100), the system triggers auto-deleveraging as a last resort. See the ADL section below for details.

### **Escalation Timeline**

| **Time**        | **What Happens**                                                                    |
| :-------------- | :---------------------------------------------------------------------------------- |
| 0 seconds       | All resting orders cancelled, account frozen, first liquidation attempt on the book |
| Every 5 seconds | Retry with a new limit order if previous attempt did not fully fill                 |
| 1 minute        | Insurance fund activates, widening the limit price up to 5% worse than mark         |
| 2 minutes       | ADL activates if the insurance fund is exhausted                                    |

***

## **Insurance Fund**

The insurance fund is a dedicated pool of capital that backstops the liquidation system.

**How it's funded:** Every liquidation charges a 1.5% fee on filled notional value. This fee is transferred to the insurance fund.

**When it's used:** After 1 minute of failed liquidation attempts (or immediately at bankruptcy), the insurance fund subsidizes wider limit prices so liquidation orders can fill against deeper book liquidity. There is a per-event cap on how much the fund will spend on a single liquidation.

**What it protects:** The fund absorbs losses when a liquidated account goes negative (losses exceed collateral). Without it, those losses would fall on other traders.

***

## **Auto-Deleveraging (ADL)**

ADL is the system's final safeguard for platform solvency. It is triggered only when normal liquidation and the insurance fund have failed to close a position.

### **When ADL Triggers**

ADL activates under two conditions:

1. **Bankruptcy:** The mark price crosses the bankruptcy price (the position is underwater beyond its collateral), regardless of time elapsed.
2. **Insurance exhaustion:** More than 2 minutes have passed since liquidation started, and the insurance fund balance is below \$100.

### **How Counterparties Are Selected**

The system identifies all traders holding positions in the same market on the opposite side of the liquidated position. These traders are ranked by a combination of their profitability and leverage:

`rank = pnl_percentage * effective_leverage` (for profitable positions)

`rank = pnl_percentage / effective_leverage` (for unprofitable positions)

Where:

* `pnl_percentage = unrealized_pnl / position_notional`
* `effective_leverage = position_notional / margin_balance`

Traders with the highest rank (most profitable and most leveraged) are deleveraged first. Their positions are closed at the bankruptcy price against the liquidated account.

Each counterparty's fill size is constrained so they remain above maintenance margin after the ADL fill.

***

## **Mark Price**

Liquidations use **mark price**, not the last traded price or a single book price. Mark price is designed to resist manipulation and provide a stable reference for margin calculations.

Mark price is the **median of three components**:

1. **Oracle price:** External price feeds from centralized exchanges.
2. **Oracle price + drift:** The oracle price adjusted by an exponentially weighted moving average of how much the on-platform orderbook mid-price diverges from the oracle (smoothed over \~150 seconds).
3. **Book composite:** The median of the best bid, best ask, and last trade on the Ondo Perps book.

Taking the median of these three values means no single component can drive the mark price on its own. Mark price movement is also rate-limited per update to prevent sudden spikes.

During weekends or when underlying markets are closed, the system switches to internal price discovery using orderbook activity, with bounded movement limits.

***

## **Cross Margin**

Ondo Perps uses cross margin exclusively. All positions in your account share a single collateral pool.

**What this means for liquidation:**

* A loss on any position reduces the margin available for all other positions
* Your liquidation price on one position depends on your entire account state
* When liquidation triggers, all resting orders are cancelled and all positions become eligible for forced closure
* Closing a profitable position frees margin that can protect your losing positions

Ondo Perps does not support isolated margin. This is a deliberate design choice: cross margin is more capital-efficient for most traders, as gains on one position automatically offset losses on another without requiring manual rebalancing.

***

## **Avoiding Liquidation**

If your margin ratio is rising toward 100%, you have several options:

* **Deposit more USDC or tokenized stock:** Increases your margin balance directly.
* **Close or reduce positions:** lowers your maintenance margin requirement.
* **Set stop-loss orders:** Automatically exits positions before the mark price reaches your liquidation price.
* **Close profitable positions:** In cross margin, this frees margin for your remaining positions.

Monitor your margin ratio and liquidation price. During high volatility, mark price can move quickly, and the displayed liquidation price is an estimate that can shift as your unrealized PnL and other positions change. Ondo Perps uses a multi-layered liquidation process to protect both traders and the platform during periods of market volatility, ensuring positions are closed fairly while maintaining platform stability.

Liquidation is triggered when a trader's Margin Balance falls below the Maintenance Margin Requirement. It is important to note that liquidation only affects funds deposited into the margin account, it never touches wallet funds.

Two key price levels govern the liquidation process:

| **Term**          | **Definition**                                                                                                            |
| :---------------- | :------------------------------------------------------------------------------------------------------------------------ |
| Liquidation Price | The mark price at which a position begins entering liquidation. Calculated when Margin Balance equals Maintenance Margin. |
| Bankruptcy Price  | The mark price at which a trader's losses equal their deposited collateral. Calculated when Margin Balance equals zero.   |

Liquidation is initiated at the liquidation price rather than the bankruptcy price to account for slippage when executing the liquidation order. In cross-margin mode, both prices fluctuate with the mark price across all open positions.

**Liquidation Process**

Liquidation proceeds in layers, starting with the most liquid markets and working toward the least liquid:

*Step 1 -- Order Cancellation:* All resting orders are cancelled to free up margin.

*Step 2 -- Standard Liquidation:* The exchange attempts to close the position via a limit IOC order at bankruptcy price. If sufficient liquidity exists, the position is closed and a 1.5% liquidation fee is charged on the order quote size, which is deposited into the Insurance Fund. Liquidation stops as soon as enough margin has been recovered.

*Example: A trader is long 10 shares of NVDA at \$875.00, opened with \$4,375 at 20x leverage. The position is liquidated at \$810.00. The liquidation fee would be 1.5% x \$8,100 = \$121.50.*

*Step 3 -- Third-Party Liquidation:* If the position cannot be closed at bankruptcy price due to insufficient liquidity, the exchange offers the position to third-party liquidation providers at bankruptcy price or better, maximizing margin recovery for the trader.

*Step 4 -- Insurance Fund:* If no third-party liquidation provider steps in but liquidity exists below bankruptcy price, the Insurance Fund covers the shortfall, ensuring the trader's margin account does not go negative.

**Insurance Fund**

The Insurance Fund is maintained through the 1.5% liquidation fee collected on all forced liquidations. It serves as a safety net in extreme scenarios where a trader's losses exceed their deposited collateral, covering the shortfall and ensuring the platform remains solvent.

The Insurance Fund is invoked when a limit IOC order at bankruptcy price cannot be filled. This typically occurs when:

* Market volatility causes sudden, sharp price movements
* A trader's margin level drops below 100%
* The standard liquidation process cannot execute quickly enough to prevent negative equity
