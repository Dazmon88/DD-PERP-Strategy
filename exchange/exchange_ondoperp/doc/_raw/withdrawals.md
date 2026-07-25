> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Withdrawals

You can withdraw any deposited asset as long as your remaining portfolio satisfies margin requirements after the withdrawal.

**Withdrawal formulas:**

* **USDC:** You can withdraw up to the lesser of your withdrawable margin and your USDC balance.
* **Non-USDC:** You can withdraw up to the lesser of your withdrawable margin divided by the asset's post-haircut price, and your token balance.
  Withdrawable margin accounts for all open positions and the amount required to keep positions above maintenance margin.

**Key rules:**

* If your full deposit is required to back open positions, no withdrawal is permitted.
* Mark price is used to determine withdrawal eligibility in real time.
* Assets are withdrawn to the same chain used to deposit.
* You withdraw the assets you deposited. You cannot deposit \$100 of SPYon and withdraw \$100 of USDC.

**If a withdrawal is blocked**, the UI explains why and suggests what you can do to unlock it (e.g., close a position or deposit additional USDC).
