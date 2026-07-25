> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Positions, Balances, and Leverage

All trading on Ondo Perps is cross-margined. Rather than isolating collateral per position, your full margin balance — comprising USDC and any deposited Ondo Global Markets tokenized assets — backs all open positions simultaneously.

| Term                | Definition                                                                                                                                                                |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Wallet Balance      | Reflects margin account transfers, realized PnL, funding fee payments and receipts, and exchange fees.                                                                    |
| Margin Balance      | The sum of Wallet Balance and Unrealized PnL. Used to calculate leverage and margin ratio.                                                                                |
| Used Margin         | The balance reserved as collateral for open positions and resting orders, summed across all markets. Calculated as `max(long used margin, short used margin)` per market. |
| Available Margin    | The balance available for placing new orders. Equal to Margin Balance minus Used Margin.                                                                                  |
| Withdrawable Margin | The balance available for withdrawal. If there are no open positions or resting orders, this equals the Margin Balance.                                                   |
