> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Profit & Loss

## PnL Calculation

**Entry Price** When opening or increasing a position, the entry price is calculated as a size-weighted average of all opening trades:

`Entry Price = (Previous Entry Price x Previous Size + Trade Price x Trade Size) / New Position Size`

When partially or fully closing a position, the entry price remains unchanged.

**Unrealized PnL** The potential profit or loss on an open position if closed at the current mark price:

`Unrealized PnL = (Mark Price - Entry Price) x Position Size`

For long positions, uPnL is positive when mark price is above entry price. For short positions, uPnL is positive when mark price is below entry price.

**Realized PnL** Captured when closing a position, in full or in part:

`Realized PnL = (Exit Price - Entry Price) x Closed Size`

Funding payments are applied to realized PnL at each hourly settlement. Trading fees are deducted separately.

**Total PnL** `Total PnL = Realized PnL + Unrealized PnL`

*Example: A trader opens a long NVDA-PERP position of 10 shares at \$875.00. If the mark price moves to \$900.00, uPnL = (900 - 875) x 10 = \$250.00. If the trader closes the full position at \$900.00, realized PnL = \$250.00 minus applicable fees.*
