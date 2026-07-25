> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Leverage

## Cross Margin

Ondo Perps uses cross margin. All your positions share a single collateral pool, meaning your entire margin balance supports every open position across every market.

There is no isolated margin mode. This is a design choice: cross margin maximizes capital efficiency by letting gains in one position offset losses in another. You do not need to allocate margin to individual positions or move funds between them.

The trade-off is that a large loss in one position can affect your entire account. Your liquidation risk is based on your total account health, not any single position.

***

## Leverage

Leverage determines how much margin is required to open a position. Higher leverage means less margin required, but a tighter distance to liquidation.

You can set leverage per market to any integer from 1x up to the market maximum. The maximum depends on the asset:

| **Asset Class** | **Markets**                                                                                  | **Max Leverage** | **Initial Margin Rate** | **Maintenance Margin Rate** |
| :-------------- | :------------------------------------------------------------------------------------------- | :--------------- | :---------------------- | :-------------------------- |
| Indices         | US100, US500                                                                                 | 20x              | 5.0%                    | 2.5%                        |
| Commodities     | XAG (Silver), XAU (Gold), WTI (Oil)                                                          | 20x              | 5.0%                    | 2.5%                        |
| ETFs            | DRAM                                                                                         | 10x              | 10.0%                   | 5.0%                        |
| Equities        | AAPL                                                                                         | 20x              | 5.0%                    | 2.5%                        |
| Equities        | AMD, AMZN, COIN, CRCL, GOOGL, HOOD, INTC, META, MSFT, MSTR, MU, NFLX, NVDA, ORCL, PLTR, TSLA | 10x              | 10.0%                   | 5.0%                        |

If you set leverage lower than the market maximum, your initial margin rate increases accordingly. For example, setting AAPL to 10x means your initial margin rate is 10% instead of 5%.

Lowering leverage on an existing position requires enough available margin to cover the higher margin requirement. You cannot lower leverage if it would put your account below the initial margin threshold.

***

## Initial Margin

Initial margin is the collateral required to open a position:

`initial_margin = (price x quantity) / leverage`

This is the same as: `initial_margin = notional_position_value x initial_margin_rate`

Where `initial_margin_rate = 1 / leverage`.

**Example:** Opening a \$10,000 position in AAPL at 20x leverage requires \$500 in initial margin (\$10,000 / 20).

When you have multiple positions and resting orders, your total used margin is calculated per market as:

`used_margin = max(buy_side_margin, sell_side_margin) + open_losses`

Buy and sell positions partially offset each other, so your used margin is the larger of the two sides, not the sum. Your account-wide used margin is the total across all markets.

***

## Maintenance Margin

Maintenance margin is the minimum collateral required to keep a position open. If your margin balance falls to the maintenance margin level, your position enters liquidation.

`maintenance_margin = notional_position_value x maintenance_margin_rate - maintenance_amount`

The maintenance margin rate is always half the initial margin rate at maximum leverage:

* 20x markets: 2.5% maintenance margin rate
* 10x markets: 5.0% maintenance margin rate

### Margin Tiers

Ondo Perps supports tiered margin brackets. As position size grows, higher tiers may apply with different margin rates. The `maintenance_amount` in the formula is a smoothing coefficient that prevents abrupt jumps at tier boundaries, ensuring your maintenance margin changes continuously as your position size changes.

Currently, each market has a single tier with a \$1,000,000 position bracket. For most traders, this means a flat maintenance margin rate applies to your entire position.

**Example:** A \$10,000 AAPL position at 20x leverage has a maintenance margin of \$250 (\$10,000 x 2.5%).

***

## Margin Balance and Margin Ratio

### Margin Balance

Your margin balance represents your total account equity:

`margin_balance = wallet_balance + unrealized_pnl`

Where wallet balance includes your deposits, realized PnL, and funding payments.

### Available Margin

Available margin is what you can use to open new positions or withdraw:

`available_margin = margin_balance - total_initial_margin`

### Margin Ratio

Margin ratio shows how close your account is to liquidation:

`margin_ratio = maintenance_margin / margin_balance`

* **0%**: No open positions or fully collateralized
* **Below 100%**: Account is healthy
* **100%**: Liquidation is triggered

***

## Collateral

### Accepted Collateral Types

Ondo Perps accepts the following collateral types:

| **Collateral** | **Haircut**             | **Notes**          |
| :------------- | :---------------------- | :----------------- |
| USDC           | None (valued at \$1.00) | Primary collateral |
