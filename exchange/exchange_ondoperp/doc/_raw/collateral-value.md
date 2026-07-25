> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Collateral Value

A haircut is the discount applied to your collateral's market value when calculating your credited margin.

**Example:** A 10% haircut on \$1,000 of SPYon means the exchange credits you with \$900 of margin, but holds the full \$1,000 of SPYon. The \$100 gap absorbs conversion slippage and price movement if the exchange ever needs to convert your collateral to USDC.

**Key details:**

* Collateral ratio equals 1 minus the haircut (10% haircut = 0.90 collateral ratio).
* Haircut changes resulting in increasing the haircut (decreasing the collateral ratio) require **30 days' notice.**

| Term                        | Formula                                                |
| :-------------------------- | :----------------------------------------------------- |
| Credited Margin (per asset) | `min(quantity x mark price x (1 - haircut), $100,000)` |
| Collateral Ratio            | `1 - haircut`                                          |

For details on accepted collateral see Funding Your Account.

## **How Margin Is Calculated**

Your account health is represented by a single number called **margin balance**:

```text theme={null}
margin balance = USDC balance + Non-USDC Margin Value + unrealized PnL + funding
```

Where:

* **Non-USDC Margin Value:** Total post-haircut value of all your deposited tokenized equities, `sum(quantity x price x (1 - haircut))` for each asset, capped at \$100,000 per asset.
* **USDC balance:** Your cash balance, which can be negative if you have accumulated losses or fees.
* **Unrealized PnL:** Profit or loss on your open positions.
* **Funding:** Accumulated funding payments.

Your margin balance captures everything that affects your account health in one number. It moves when asset prices change, when your positions gain or lose value, when you pay fees, and when funding payments accrue.
