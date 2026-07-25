> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Take Profit / Stop Loss 

Take profit and stop loss (TP/SL) orders automatically close a position when the mark price hits a specified level. They are reduce-only, meaning they can only close an existing position and never open or flip position direction.

TP and SL are linked as OCO (one cancels the other). When one triggers and fills, the other is automatically cancelled. If the position is fully closed for any reason, all attached TP/SL orders cancel automatically.

**Two Ways to Set TP/SL**

*At Order Placement:* Add TP/SL directly on the order form when entering a trade. These apply only to the size of that specific order, allowing multiple partial TP/SL legs to coexist on the same position across successive entries.

*Via Risk Management Module:* Set or adjust TP/SL from the Risk Management Module in the positions table at any time after a position is open. This applies to the full position, with a limit of one TP and one SL per market.

**Order States**

| **State** | **Description**                                                 |
| :-------- | :-------------------------------------------------------------- |
| Open      | Active and waiting for trigger                                  |
| Triggered | Price condition met                                             |
| Filled    | Order executed                                                  |
| Rejected  | Order was non-reducing at trigger and was rejected              |
| Cancelled | Manually cancelled, or cancelled by the paired order triggering |

**Execution behavior**

Stop orders execute as market orders against the live order book. Before executing, the system calculates the maximum quantity it can safely fill without pushing the account into liquidation. This check accounts for the fact that a stop-loss closes a position at realized prices that may be worse than the mark price used to estimate available margin: as the order eats through price levels beyond the mark price, realized losses can exceed the margin cushion and trigger liquidation.

If the calculated maximum is zero because the account is already under liquidation or the available margin is fully consumed by unrealized losses, the order does not execute and is cancelled.

When liquidity is limited or the spread is wide, the maximum safe size may be less than the full position size. In that case the order executes for a reduced quantity. The position is partially closed and the remaining stop order is cancelled; there is no retry or re-queue.

A stop order is also cancelled without executing if:

* The account enters liquidation between the trigger and execution.
* The position is neutral at trigger time.
* The position direction has flipped since the order was placed.

**Limitations**

* Triggered as market orders only, stop-limit variants are not currently supported.
* Risk Management Module TP/SL covers the full position only. Cancel and replace to update.
* Once visible in Open Orders, TP/SL orders are cancel-only and cannot be edited.
* Partial legs set at order placement are fixed at creation size and do not auto-resize as the position changes.
