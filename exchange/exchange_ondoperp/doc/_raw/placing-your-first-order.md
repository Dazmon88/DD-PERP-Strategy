> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Placing Your First Order

Ondo Perps uses a standard perpetual futures order interface. The following walks through each step from market selection to order submission.

**1. Select a Market**

Use the market selector at the top left to choose the asset you want to trade. Each market displays the current mark price, 24h change, 24h volume, open interest, and funding rate.

**2. Choose a Side**

Select **Long** to open a position that profits if the asset price rises, or **Short** to open a position that profits if the asset price falls.

**3. Select an Order Type**

* **Market**: Executes immediately at the best available price
* **Limit**: Executes at your specified price or better; rests in the order book until filled or cancelled
* **TWAP**: Splits a large order into smaller pieces executed over a defined time window, reducing market impact

**4. Set Leverage**

Tap the leverage control (e.g. "Cross 10x") in the top right of the order panel to adjust your leverage. Ondo Perps currently supports cross margin mode, meaning your full account balance is available to back open positions. Higher leverage increases both potential returns and liquidation risk.

**5. Enter an Amount**

Enter your order size in USD notional value. To switch to asset units (e.g. number of NVDA shares), tap the toggle icon next to the amount field.

**6. Configure Optional Parameters**

* **Reduce Only**: Restricts the order to reducing an existing position; it will not open or increase a position
* **Take Profit / Stop Loss**: Set a target price to automatically close your position at a gain (TP) or limit your loss (SL)

**7. Review the Order Summary**

Before submitting, review the order details displayed below the entry form:

* **Order Value**: Total notional value of the position
* **Est. Price**: Estimated fill price
* **Net Position**: Your resulting position after the order fills
* **Est. Liq. Price:** The mark price at which your position would be liquidated
* **Fee:** Trading fee applied to the order (0.035%)
* **Est. Slippage:** Estimated price impact for market orders

**8. Place the Order**

Once you've reviewed the summary, click **Enter Order Amount** to confirm and submit. Filled orders will appear under the **Fills** tab at the bottom of the screen. Open positions are tracked under **Positions**.

**First Trade Walkthrough**

1. Deposit USDC via the **Deposit** button in the top right corner
2. Navigate to the market you want to trade using the market selector
3. Select **Long** or **Short**
4. Set your leverage using the leverage control
5. Enter your order amount in USD or asset units
6. Select your order type: Market for immediate execution, Limit to specify a price, or TWAP to execute over a defined window
7. Optionally set a Take Profit or Stop Loss
8. Review the estimated liquidation price, fee, and slippage
9. Click **Enter Order Amount** to submit
