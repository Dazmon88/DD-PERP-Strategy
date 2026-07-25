> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Mark Price Protection

Mark price protection is a mechanism that prevents trades from occurring at a price that is very obviously incorrect compared to the mark price. This can happen for reasons such as:

* The size of a market order was entered incorrectly as too large causing it to trade through many order book levels
* The price of a limit order was entered incorrectly and now greatly overlaps with the mark price

When a limit order is submitted, its price is compared to the current mark price for that market and rejected if it lies more than 10% away.

For a buy order the price must be:

`limit-price < mark-price * 1.1`

For a sell order the price must be:

`limit-price > mark-price * 0.9`

When a market order is submitted, a simulation of its execution is performed and if a trade will occur more than 10% away from the mark price, then the order is rejected.

## Learn More

<CardGroup cols={2}>
  <Card title="External pricing derivations" icon="circle-dollar-sign" href="/pricing-derivations">
    The specific oracle sources feeding the mark price for each asset class.
  </Card>

  <Card title="Premium index" icon="ruler" href="/premium-index">
    How impact prices and the mark price combine to form the premium index.
  </Card>

  <Card title="Funding rates" icon="hand-coins" href="/funding-rates">
    How the mark price drives hourly funding settlements.
  </Card>

  <Card title="Liquidations and insurance" icon="droplet" href="/def">
    How liquidations use the mark price and the multi-layered waterfall behind them.
  </Card>
</CardGroup>
