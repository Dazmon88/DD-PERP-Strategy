> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Settlement

## **Auto-Exchange**

Auto-Exchange (AE) sells some of your deposited collateral to pay off your USDC Debt. When your debt grows too large relative to your collateral, AE converts enough of your tokenized equities into USDC to bring your USDC Debt to zero.

**What does "clearing your debt" actually mean for your USDC balance?** It depends on what's driving the debt:

* If your debt comes entirely from realized losses and fees (negative USDC balance, no uPnL), AE brings your USDC balance back to zero.
* If unrealized losses on open positions are contributing to your debt, AE brings your USDC balance *positive* enough to offset those unrealized losses. Your positions stay open, so the uPnL is still there. The positive USDC balance counteracts it, bringing your net debt to zero.

This is important: after AE, you may see a positive USDC balance even though you didn't deposit USDC. That positive balance is not "free money," it's offsetting the unrealized losses on your still-open positions.

Your positions stay open. You keep trading. You just have less collateral afterward.

### **When Does Auto-Exchange Trigger?**

AE fires when your **LTV reaches 30%.**

When triggered, AE sells enough collateral to **clear your entire USDC Debt** (bring your USDC Debt to zero, which may mean a positive USDC balance if you have unrealized losses).

### **What Happens During Auto-Exchange?**

1. The amount of collateral needed to cover your full debt is calculated.
2. If you hold multiple collateral assets, the asset with the highest held notional value is sold first.
3. Your collateral balance decreases and your USDC Debt returns to zero.
   1. Collateral is sold to cover your negative USDC balance.
   2. Collateral is sold to balance out your unrealized losses (pushing USDC balance positive to offset uPnL).
4. Your open positions stay open, AE does not close your positions.
5. New orders and withdrawals are prevented until Auto-Exchange completes.

From your perspective, this is near-instant: collateral goes down, USDC goes up, positions are unaffected.

### **Can I Trigger Auto-Exchange Manually?**

Yes. You can initiate AE from the UI whenever your USDC Debt exceeds the minimum threshold. Before you confirm, the UI shows you the notional value of your assets to be sold and estimated USDC you will receive.

This is useful if you want to proactively clear your debt, for example before a weekend when you prefer to reduce exposure.

### **How USDC Debt and Auto-Exchange Work Together**

USDC Debt and Auto-Exchange are two halves of the same system. USDC Debt lets you keep trading when your USDC runs out. Auto-Exchange makes sure that debt never gets too large. Here is the full cycle:

1. **You deposit collateral:** You deposit tokenized equities (e.g., \$100,000 of SPYon) and receive \$90,000 of credited margin after the 10% haircut. Your USDC Debt is \$0, LTV is 0%.
2. **You trade and incur costs:** You open positions, pay fees, and receive or pay funding. Losses come out of your USDC balance.
3. **Your USDC balance goes negative:** You now have USDC Debt. Your deposited equities back this debt, so you can keep trading as long as the debt stays within limits.
4. **Your LTV rises:** Continued losses increase your debt. If your collateral token's price also drops, your LTV rises even faster because the same debt is measured against a smaller collateral base.
5. **LTV hits 30%:** Auto-Exchange fires.
6. **AE clears your debt:** Enough of your collateral is sold to bring your USDC Debt to zero. If you have unrealized losses on open positions, your USDC balance goes positive to offset them. Your remaining collateral stays in your account. Your positions stay open. LTV returns to 0%.
7. **The cycle can repeat:** If you keep trading and accumulate new debt, the same thresholds apply. Each time AE fires, you have less collateral but zero debt.

### **Auto-Exchange Example**

**Starting state:** \$100,000 of SPYon deposited. Credited margin: \$90,000 (10% haircut). USDC balance: -\$5,000 (from accumulated trading fees and a realized loss).

**Step 1:** Your open positions move against you, accumulating -\$22,000 in unrealized PnL. Combined with your existing negative USDC balance:

```text theme={null}
margin balance     = (-$5,000) + $90,000 + (-$22,000) = $63,000
USDC Debt          = $63,000 - $90,000                 = -$27,000
LTV                = $27,000 / $90,000                  = 30%
```

AE triggers at 30% LTV. Note that the \$27,000 debt comes from two sources: \$5,000 in realized costs (negative USDC balance) and \$22,000 in unrealized losses.

**Step 2:** AE sells \$27,000 of SPYon at market value, converting it to USDC.

**After AE:**

|                 | Value                                           |
| :-------------- | :---------------------------------------------- |
| SPYon remaining | \$73,000 market value, \$65,700 credited margin |
| USDC balance    | +\$22,000                                       |
| Unrealized PnL  | -\$22,000 (positions still open)                |
| USDC Debt       | \$0                                             |
| LTV             | 0%                                              |
| Positions       | Remain open                                     |

**Why is USDC balance positive, not zero?** Your positions are still open with -\$22,000 uPnL. AE needs your USDC balance to be positive enough to offset that. The \$27,000 from selling collateral first covered the -\$5,000 USDC hole, then pushed the balance to +\$22,000 to counteract the unrealized losses. Net debt: zero.

```text theme={null}
margin balance     = $22,000 + $65,700 + (-$22,000) = $65,700
USDC Debt          = $65,700 - $65,700               = $0
LTV                = 0%
```

### **When Does Auto-Exchange Not Trigger?**

* Closing a position with a realized loss does not trigger AE unless the resulting debt pushes your LTV past 30%.
* Partial position closes follow the same rule, AE only fires if a threshold is crossed.
* Closing all positions does not automatically trigger AE, it only fires if the thresholds are crossed.
