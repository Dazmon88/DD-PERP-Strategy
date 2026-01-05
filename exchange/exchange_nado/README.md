# Nado Protocol Python SDK

This is the Python SDK for the [Nado Protocol API](TODO).

See [SDK docs](https://nadohq.github.io/nado-python-sdk/index.html) to get started.

## Requirements

- Python 3.9 or above

## Installation

You can install the SDK via pip:

```bash
pip install nado-protocol
```

## Basic usage

### Import the necessary utilities:

```python
from nado_protocol.client import create_nado_client, NadoClientMode
from nado_protocol.contracts.types import DepositCollateralParams
from nado_protocol.engine_client.types.execute import (
    OrderParams,
    PlaceOrderParams,
    SubaccountParams
)
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.math import to_pow_10, to_x18
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.order import build_appendix
```

### Create the NadoClient providing your private key:

```python
print("setting up nado client...")
private_key = "xxx"
client = create_nado_client(NadoClientMode.DEVNET, private_key)
```

### Perform basic operations:

```python
# Depositing collaterals
print("approving allowance...")
approve_allowance_tx_hash = client.spot.approve_allowance(0, to_pow_10(100000, 6))
print("approve allowance tx hash:", approve_allowance_tx_hash)

print("querying my allowance...")
token_allowance = client.spot.get_token_allowance(0, client.context.signer.address)
print("token allowance:", token_allowance)

print("depositing collateral...")
deposit_tx_hash = client.spot.deposit(
   DepositCollateralParams(
      subaccount_name="default", product_id=0, amount=to_pow_10(100000, 6)
   )
)
print("deposit collateral tx hash:", deposit_tx_hash)

# Placing orders
print("placing order...")
owner = client.context.engine_client.signer.address
product_id = 1
order = OrderParams(
   sender=SubaccountParams(
      subaccount_owner=owner,
      subaccount_name="default",
   ),
   priceX18=to_x18(20000),
   amount=to_pow_10(1, 17),
   expiration=get_expiration_timestamp(40),
   nonce=gen_order_nonce(),
   appendix=build_appendix(order_type=OrderType.POST_ONLY)
)
res = client.market.place_order({"product_id": product_id, "order": order})
print("order result:", res.json(indent=2))
```

## TWAP and Trigger Orders

The SDK provides comprehensive support for Time-Weighted Average Price (TWAP) orders and price trigger orders through the Trigger Client.

### TWAP Orders

TWAP orders allow you to execute large trades over time with controlled slippage:

```python
from nado_protocol.trigger_client import TriggerClient
from nado_protocol.trigger_client.types import TriggerClientOpts
from nado_protocol.utils.math import to_x18
from nado_protocol.utils.expiration import get_expiration_timestamp

# Create trigger client
trigger_client = TriggerClient(
    opts=TriggerClientOpts(url=TRIGGER_BACKEND_URL, signer=private_key)
)

# Place a TWAP order to buy 5 BTC over 2 hours
twap_result = trigger_client.place_twap_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(50_000)),        # Max $50k per execution
    total_amount_x18=str(to_x18(5)),      # Buy 5 BTC total
    expiration=get_expiration_timestamp(60 * 24),  # 24 hours
    nonce=client.order_nonce(),
    times=10,                             # Split into 10 executions
    slippage_frac=0.005,                  # 0.5% slippage tolerance
    interval_seconds=720,                 # 12 minutes between executions
)
```

### TWAP with Custom Amounts

For more sophisticated strategies, you can specify custom amounts for each execution:

```python
# Decreasing size strategy: 2 BTC, 1.5 BTC, 1 BTC, 0.5 BTC
custom_amounts = [
    str(to_x18(2)),      # 2 BTC
    str(to_x18(1.5)),    # 1.5 BTC  
    str(to_x18(1)),      # 1 BTC
    str(to_x18(0.5)),    # 0.5 BTC
]

custom_twap_result = trigger_client.place_twap_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(51_000)),
    total_amount_x18=str(to_x18(5)),      # 5 BTC total
    expiration=get_expiration_timestamp(60 * 12),
    nonce=client.order_nonce(),
    times=4,                              # 4 executions
    slippage_frac=0.01,                   # 1% slippage
    interval_seconds=1800,                # 30 minutes
    custom_amounts_x18=custom_amounts,
)
```

### Price Trigger Orders

Create conditional orders that execute when price conditions are met:

```python
# Stop-loss order (sell when price drops below $45k)
stop_loss = trigger_client.place_price_trigger_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(44_000)),        # Sell at $44k
    amount_x18=str(-to_x18(1)),           # Sell 1 BTC (negative for sell)
    expiration=get_expiration_timestamp(60 * 24 * 7),  # 1 week
    nonce=client.order_nonce(),
    trigger_price_x18=str(to_x18(45_000)), # Trigger below $45k
    trigger_type="last_price_below",
    reduce_only=True,                     # Only reduce position
)

# Take-profit order (sell when price rises above $55k)
take_profit = trigger_client.place_price_trigger_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(56_000)),        # Sell at $56k
    amount_x18=str(-to_x18(1)),           # Sell 1 BTC
    expiration=get_expiration_timestamp(60 * 24 * 7),
    nonce=client.order_nonce(),
    trigger_price_x18=str(to_x18(55_000)), # Trigger above $55k
    trigger_type="last_price_above",
    reduce_only=True,
)
```

### Supported Trigger Types

The SDK supports six types of price triggers:

- `"last_price_above"`: Trigger when last traded price goes above threshold
- `"last_price_below"`: Trigger when last traded price goes below threshold  
- `"oracle_price_above"`: Trigger when oracle price goes above threshold
- `"oracle_price_below"`: Trigger when oracle price goes below threshold
- `"mid_price_above"`: Trigger when mid price goes above threshold
- `"mid_price_below"`: Trigger when mid price goes below threshold

### Complete Trading Strategy Example

Here's how to set up a complete trading strategy with stop-loss, take-profit, and DCA:

```python
# 1. Stop-loss protection
stop_loss = trigger_client.place_price_trigger_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(44_000)),
    amount_x18=str(-to_x18(2)),           # Close 2 BTC position
    expiration=get_expiration_timestamp(60 * 24 * 30),
    nonce=client.order_nonce(),
    trigger_price_x18=str(to_x18(45_000)),
    trigger_type="last_price_below",
    reduce_only=True,
)

# 2. Take-profit target
take_profit = trigger_client.place_price_trigger_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(58_000)),
    amount_x18=str(-to_x18(2)),           # Close 2 BTC position
    expiration=get_expiration_timestamp(60 * 24 * 30),
    nonce=client.order_nonce(),
    trigger_price_x18=str(to_x18(57_000)),
    trigger_type="last_price_above", 
    reduce_only=True,
)

# 3. DCA accumulation strategy
dca_strategy = trigger_client.place_twap_order(
    product_id=1,
    sender=client.signer.address,
    price_x18=str(to_x18(52_000)),        # Max $52k per buy
    total_amount_x18=str(to_x18(10)),     # Buy 10 BTC over time
    expiration=get_expiration_timestamp(60 * 24 * 7),
    nonce=client.order_nonce(),
    times=20,                             # 20 executions
    slippage_frac=0.005,                  # 0.5% slippage
    interval_seconds=1800,                # 30 minutes
)
```

See [Getting Started](https://nadohq.github.io/nado-python-sdk/getting-started.html) for more.

## Running locally

1. Clone [github repo](https://github.com/nadohq/nado-python-sdk)

2. Install poetry

```

$ curl -sSL https://install.python-poetry.org | python3 -

```

3. Setup a virtual environment and activate it

```

$ python3 -m venv venv
$ source ./venv/bin/activate

```

4. Install dependencies via `poetry install`
5. Setup an `.env` file and set the following envvars

```shell
CLIENT_MODE='devnet'
SIGNER_PRIVATE_KEY="0x..."
LINKED_SIGNER_PRIVATE_KEY="0x..." # not required
```

### Run tests

```
$ poetry run test
```

### Run sanity checks

- `poetry run client-sanity`: runs sanity checks for the top-level client.
- `poetry run engine-sanity`: runs sanity checks for the `engine-client`.
- `poetry run indexer-sanity`: runs sanity checks for the `indexer-client`.
- `poetry run trigger-sanity`: runs sanity checks for the `trigger-client` including TWAP and price trigger examples.
- `poetry run contracts-sanity`: runs sanity checks for the contracts module.

### Build Docs

To build the docs locally run:

```
$ poetry run sphinx-build docs/source docs/build
```
