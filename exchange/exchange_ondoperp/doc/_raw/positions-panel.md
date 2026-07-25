> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Positions Panel

## Account Activity Panel

The bottom panel of the trade page provides a full view of your account activity across seven tabs.

### Positions

Displays all currently open positions. Each row shows:

| **Field**       | **Description**                                |
| :-------------- | :--------------------------------------------- |
| Contract        | Market and direction (e.g. Short 20x)          |
| Position        | Long or short                                  |
| Size            | Quantity held                                  |
| Value           | Current notional value in USD                  |
| Entry Price     | Average price at which the position was opened |
| Mark Price      | Current mark price                             |
| Est. Liq. Price | Estimated liquidation price                    |
| uPnL            | Unrealized profit or loss                      |
| TP/SL           | Take profit and stop loss levels, if set       |
| Net Funding     | Cumulative funding payments received or paid   |
| Collateral      | Collateral type backing the position           |

To manage a position, use the action controls on the right. **Market Close** immediately closes the position at the current market price. **Manage** opens a dropdown with: Take Profit / Stop Loss, Market Close, Limit Close, View Position Details, and Share PnL. To close all open positions at once, use the **Close All Positions** button at the top right of the panel.

***

### Orders

Displays order history with **All**, **Open**, and **Filled** filter tabs. Each row shows the market, side, order date, order type, order price, filled amount, and status. Cancel individual open orders via **Cancel Order**, or all at once via **Cancel All**. The **Manage** dropdown on each row offers options to view order details or cancel the order.

***

### Fills

A chronological record of all executed fills. Each row shows the market, direction (e.g. Open Short, Close Long), fill date, type (Taker/Maker), fill price, fill amount, fill cost, fee, and closed PnL where applicable.

***

### Funding History

A record of all funding payments applied to your positions. Each row shows the market, date, position size, mark price at time of payment, payment amount, and funding rate.

***

### TWAP

Displays active and historical TWAP orders. Active orders show the market, side, start time, running time, filled/order size, average price, reduce only status, and current status.

***

### Deposits

A record of all deposits into your account, showing the asset, date, quantity, and status.

***

### Withdrawals

A record of all withdrawals from your account, showing the asset, date, quantity, and status.
