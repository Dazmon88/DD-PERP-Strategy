> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# TWAP

Time-weighted average price (TWAP) orders break a large order into smaller child orders executed at scheduled intervals over a specified duration, reducing market impact and slippage. By spreading execution over time, TWAP keeps the realized average price within a few basis points of the prevailing mid-price without sweeping the order book.

*Example: Rather than buying a \$500,000 NVDA position in a single order, a TWAP breaks this into 20 orders of \$25,000 each executing every 5 minutes over 100 minutes, reducing price impact on each fill and delivering a better average execution price.*

**Placing a TWAP Order**

1. Select TWAP from the order form.
2. Enter the total order size in USDC or the base asset.
3. Set the duration using the hour and minute fields.
4. Select an order interval (default: 30 seconds; options: 1 minute, 5 minutes, 15 minutes, 1 hour).
5. Optionally enable price range bands to restrict execution to an acceptable price range.
6. Optionally enable randomization to vary order sizes and timing.

**Execution Parameters**

| **Parameter**       | **Details**                                                                                                                                                        |
| :------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Duration            | 5 minutes to 7 days                                                                                                                                                |
| Interval            | Default 30 seconds. Options: 1 minute, 5 minutes, 15 minutes, 1 hour                                                                                               |
| Price Bands         | When enabled, child orders are skipped if the mark price falls outside the configured range. Skipped quantity rolls forward as carryover to the next valid tick    |
| Randomization       | When enabled, order sizes and timing are randomized across the duration, making the execution pattern less predictable while still filling the full specified size |
| Slippage Protection | Each child order is protected by a maximum 3 bps slippage guard from the mid-price at the time the TWAP order was placed                                           |

**Monitoring TWAP Orders**

TWAP orders are visible in the positions table under the TWAP column, with three tabs:

| **Tab**      | **Details**                                                                                                                                              |
| :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Active       | Running TWAP orders including market, total size, executed size, average price, running time, and start time                                             |
| History      | Completed TWAP orders with execution summaries including total executed size, average fill price, runtime, and status (Filled, Cancelled, or Terminated) |
| Fill History | All child fills across all TWAP orders with granular detail, execution price, size, fee, and PnL per child fill                                          |

TWAP orders can be cancelled directly from the TWAP modal.

**Key Rules**

* Child orders execute as market orders at each scheduled interval.
* Orders persist through system restarts, if downtime occurs during a scheduled tick, execution resumes on the next valid tick.
* Failed child orders are skipped and their quantity rolls into carryover for the next tick.
* The full margin for a TWAP order is reserved upfront at placement.
* Maximum of 20 active TWAP orders per account.

**Important Considerations**

*TP/SL interaction:* If a take profit and stop loss (TP/SL) order triggers while a TWAP is active, the TP/SL will close the existing position while the TWAP continues placing child orders as scheduled. Monitor both order types carefully when used simultaneously.

*Market hours:* TWAP orders cannot be created if execution would extend into after-hours trading windows. The duration must account for market trading hours, and any impact on order duration is displayed on the order form.

*Minimum order size:* If any child order would fall below the minimum order size, the order cannot be submitted. Increase the total order size or select a longer interval to resolve.

*Insufficient balance:* The full margin is reserved at placement. If the account runs out of funds mid-execution, the TWAP terminates.
