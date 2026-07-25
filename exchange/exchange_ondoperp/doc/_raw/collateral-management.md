> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Collateral Management

When your trading costs exceed your USDC balance, your balance goes negative. This happens naturally as you trade: fees, funding payments, and realized losses are all settled in USDC. If you don't have enough USDC to cover them, the shortfall carries as a negative balance.

This negative balance is your **USDC Debt**. Your deposited tokenized equities back it, so you can keep trading without topping up USDC after every loss.

```text theme={null}
USDC Debt = margin balance - Non-USDC Margin Value
```

When this number is negative, you have debt. When it is zero or positive, you have no debt.

### **LTV (Loan-to-Value)**

LTV tells you how much of your collateral's credited value is consumed by debt:

```text theme={null}
LTV = abs(USDC Debt) / Non-USDC Margin Value
```

* **LTV 0%:** No debt
* **LTV 10%:** Your debt equals 10% of your credited collateral
* **LTV 30%:** Auto-Exchange triggers to clear your debt

Think of LTV as a health gauge. As your debt grows or your collateral value drops, LTV rises. At 30%, Auto-Exchange steps in.

### **Maximum Allowed Debt**

Your maximum allowed debt is 30% of your LTV:

```text theme={null}
Allowed USDC Debt = min(Non-USDC Margin Value x 30%)
```

Whichever limit you hit first. For example, if your Non-USDC Margin Value is \$90,000, the LTV limit allows \$27,000 of debt (30% x \$90,000), so your limit is \$27,000. If your Non-USDC Margin Value is \$120,000, the LTV limit allows \$36,000.

### **What Creates USDC Debt**

These reduce your USDC balance and create debt:

* **Trading fees:** Charged on each trade
* **Funding payments:** Charged on open positions
* **Realized losses:** Settled when you close a losing trade

### **What Raises Your LTV**

These do not change your debt, but they push your LTV higher, bringing you closer to the 30% Auto-Exchange threshold:

* **Your collateral price drops:** Your Non-USDC Margin Value decreases, so the same debt represents a larger share of your collateral.
* **Unrealized losses on open positions:** These reduce your overall margin balance, widening the gap between your margin balance and your collateral value.

You can have no new realized losses and still see your LTV rise if your collateral price drops or your open positions move against you.

### **If Your Debt Gets Too Large**

If your LTV reaches 30%, Auto-Exchange triggers and sells enough of your collateral to clear your debt entirely. See the next section for how this works.
