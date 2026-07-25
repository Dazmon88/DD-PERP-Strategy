> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Auto-Deleveraging (ADL)

Auto-deleveraging (ADL) is the final safeguard, invoked when the Insurance Fund is depleted or when the mark price crosses the bankruptcy price. In this scenario, the exchange forcefully closes the position at bankruptcy price by filling against positions on the opposite side of the market.

Positions selected for ADL are ranked by profitability and effective leverage, the most profitable and most leveraged positions on the opposing side are deleveraged first.

**ADL Ranking**

`PnL Percentage = Unrealized PnL / Position Notional`

`Effective Leverage = Position Notional x 100 / Margin Balance`

| **Condition**       | **Ranking Formula**                             |
| :------------------ | :---------------------------------------------- |
| PnL Percentage >= 0 | `Ranking = PnL Percentage x Effective Leverage` |
| PnL Percentage \< 0 | `Ranking = PnL Percentage / Effective Leverage` |

A higher ranking indicates a higher likelihood of being selected for ADL. Traders can monitor their ADL ranking in the positions table.
