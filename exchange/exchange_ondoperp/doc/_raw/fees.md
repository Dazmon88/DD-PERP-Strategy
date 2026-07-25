> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Fees

Ondo Perps charges flat fees across every market, with optional builder and referral programs layered on top. Every fee is denominated in USDC and assessed automatically on the relevant event, fills or liquidations.

## Trading Fees

**Promotion: For a limited time, base trading fees are discounted 50% off and are set as follows:**

| **Fee Type** | **~~Base Rate~~ Promotional Rate (50% off)** |
| :----------- | :------------------------------------------- |
| Maker        | ~~0.02% (2 bps)~~ 0.01% (1bp)                |
| Taker        | ~~0.05% (5 bps)~~ 0.025% (2.5bps)            |

Fees are calculated on the filled notional value (price x quantity) and assessed in USDC. These are the default rates, identical across all markets. Actual fees may be lower depending on your 14-day rolling trading volume (volume-based fee tiers) or individual account arrangements.

## Liquidation Fee

A **1.5% fee** is charged on the notional value of any liquidated position. This fee goes directly to the Insurance Fund. The fee is reduced if charging the full amount would push the account below maintenance margin, and is set to zero if the account's margin balance is not positive.

## Fee Distribution

Trading fees and liquidation fees flow to two separate destinations:

| **Fee Type**             | **Destination**                         |
| :----------------------- | :-------------------------------------- |
| Maker/taker trading fees | Exchange Fee Account (exchange revenue) |
| Liquidation fees (1.5%)  | Insurance Fund                          |

There is no automated split between trading revenue and the insurance fund. They are independent streams.

From the Exchange Fee Account, the protocol may pay out:

* **Referral commissions** to referrers (percentage of the trading fee)
* **Referral rebates** back to referred traders (percentage of the trading fee)
* **Builder commissions** to API integrators (incremental fee up to 10 bps, added on top of the base maker/taker fee and paid to the builder)

## Insurance Fund

The Insurance Fund is funded exclusively by liquidation fees. It serves as a backstop when liquidation cannot fill at a viable price:

* Activates after \~60 seconds of failed liquidation attempts; or
* Immediately if the mark price crosses the bankruptcy price for the position being liquidated; and
* Can widen the acceptable liquidation price up to **5% worse than the mark price.**

## Learn More

<CardGroup cols={2}>
  <Card title="Funding rates" icon="hand-coins" href="/funding-rates">
    Hourly funding mechanism, formula, scaling factors, and worked examples.
  </Card>

  <Card title="Liquidations and insurance" icon="droplet" href="/def">
    The multi-layered liquidation waterfall and how the insurance fund is funded.
  </Card>
</CardGroup>
