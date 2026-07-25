> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Measuring Risk

Understanding your risk exposure is critical when trading with leverage. The following metrics are available on the platform to help you monitor and manage your positions.

| Term                           | Definition                                                                                                                                                    |
| :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Maintenance Margin Requirement | The total maintenance margin required across all open positions. Liquidation is triggered when Margin Balance falls below this value.                         |
| Margin Ratio                   | A measure of proximity to liquidation. Returns `0` with no open positions, above `0.5` indicates elevated risk, and `1` triggers liquidation.                 |
| Account Leverage               | The notional value of all open positions divided by Margin Balance. New positions cannot be opened once Account Leverage reaches the contract's Max Leverage. |
| Under Liquidation              | Indicates whether the account is currently being liquidated.                                                                                                  |
