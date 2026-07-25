> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Weekend Mechanics

Weekends are defined as Friday 8:00 PM ET through Sunday 8:00 PM ET. US market holidays are treated the same as weekends.

### **Weekend Pricing**

Ondo Perps provides live pricing for tokenized equity collateral through the weekend. Your collateral is marked to market continuously, including on weekends and market holidays.

There is no price freeze, no queue, and no Monday reconciliation step. All user-facing surfaces reflect continuous weekend pricing.

### **Weekend Liquidations**

Both your perp positions and your collateral mark to market in real time over the weekend. Liquidations trigger based on real-time perp PnL against real-time collateral marks.

### **Closed-Market Settlement Fee**

If Auto-Exchange fires during weekend or holidays, a closed-market settlement fee applies. This fee compensates the exchange for price risk during periods when the underlying equity market is closed and on-chain liquidity is thinner.

* The fee is funded from your own collateral (not a separate USDC charge). The exchange sells slightly more collateral to cover the fee alongside your debt
* The fee will be displayed on the autoexchange details

**Example:** I If AE fires over a weekend to cover \$1,000 in USDC Debt, the exchange sells \$1,025 worth of collateral: \$1,000 to clear your debt and \$25 as the settlement fee (eg 2.5% as an example.)
