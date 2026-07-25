> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Overview

Ondo Tokenized Stock Collateral lets you use your tokenized equities as margin for perpetual futures trading on Ondo Perps, without selling them.

Instead of converting your tokenized equities into USDC to trade, you can deposit them directly into your account as collateral. The exchange values your deposited assets in real time and credits them toward your available margin, so you can open leveraged positions while keeping your equity exposure.

Your deposited assets and USDC balance live in a single unified account. There is no separate spot wallet. Collateral is part of your margin account.

**Supported assets at launch:** QQQon and SPYon, (Ethereum-based Ondo Global Markets tokens).

## **What Are the Benefits of Tokenized Stock Collateral?**

* **Capital efficiency:** Put your idle tokenized equities to work as margin instead of leaving them sitting idle in your wallet.
* **Maintain equity exposure:** Trade perps without selling your equity positions. Your deposited tokens stay in your account unless converted through Auto-Exchange or liquidation.
* **Access leverage:** Your tokenized equities contribute to your available margin, giving you the ability to open leveraged perpetual positions.
* **Real-time portfolio visibility:** See your total account equity, per-asset margin contribution, and overall margin health updated continuously as prices move.

## **How Does Tokenized Stock Collateral Work?**

When you deposit a tokenized equity, the token quantity is held fixed in your account. Its value is marked to market continuously using the asset's real-time mark price.

The exchange applies a **haircut** (discount) to your deposited asset's market value when calculating how much margin you receive. After the haircut, your credited margin functions identically to a USDC balance for margin purposes.

Each asset also has a **credited margin cap** of \$100,000. If your post-haircut collateral value exceeds the cap, the excess does not contribute additional margin.

**Important:** Your margin health fluctuates as the asset price moves, even if you have no open positions. Because your collateral is a volatile asset (not stablecoins), your account equity changes with the market.

Upon deposit, your tokenized equity assets are transferred to and held by the exchange. You retain beneficial ownership and may withdraw subject to margin health requirements. The exchange has the right to convert deposited assets to USDC in the event of Auto-Exchange or liquidation.

## **Key Formulas**

| Formula                     | Calculation                                                     |
| :-------------------------- | :-------------------------------------------------------------- |
| Credited Margin (per asset) | `min(quantity x mark price x 0.90, $100,000)`                   |
| Non-USDC Margin Value       | sum of all credited margins                                     |
| Margin Balance              | USDC balance + Non-USDC Margin Value + unrealized PnL + funding |
| USDC Debt                   | margin balance - Non-USDC Margin Value                          |
| LTV                         | `abs(USDC Debt) / Non-USDC Margin Value`                        |
| Allowed USDC Debt           | `min(Non-USDC Margin Value x 0.30)`                             |
