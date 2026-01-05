Order Appendix
==============

The Order Appendix is a powerful feature in the Nado Protocol that allows you to specify advanced order parameters through a compact bit-packed integer. This appendix encodes various order properties including execution types, isolated positions, TWAP parameters, and trigger types.

Overview
--------

The appendix is a 128-bit integer with the following bit layout (from MSB to LSB):

.. code-block::

    | value   | reserved | trigger | reduce only | order type| isolated | version |
    | 64 bits | 50 bits  | 2 bits  | 1 bit       | 2 bits    | 1 bit    | 8 bits  |
    | 127..64 | 63..14   | 13..12  | 11          | 10..9     | 8        | 7..0    |

Fields (from LSB to MSB):

- **Version** (bits 0-7): Protocol version for future compatibility (currently version 1)
- **Isolated** (bit 8): Whether the order is for an isolated position
- **Order Type** (bits 9-10): Execution type (DEFAULT, IOC, FOK, POST_ONLY)
- **Reduce Only** (bit 11): Whether the order can only reduce existing positions
- **Trigger Type** (bits 12-13): Type of trigger order (NONE, PRICE, TWAP, TWAP_CUSTOM_AMOUNTS)
- **Reserved** (bits 14-63): Reserved for future use
- **Value** (bits 64-127): Additional data (isolated margin or TWAP parameters)

Building an Appendix
--------------------

Use the :func:`build_appendix` function to create an appendix with the desired parameters:

.. code-block:: python

    from nado_protocol.utils.order import build_appendix
    from nado_protocol.utils.expiration import OrderType

    # Basic order with IOC execution type
    appendix = build_appendix(order_type=OrderType.IOC)

    # Reduce-only order
    appendix = build_appendix(
        order_type=OrderType.POST_ONLY,
        reduce_only=True
    )

Order Execution Types
--------------------

The appendix supports four execution types:

**DEFAULT**
    Standard limit order behavior

**IOC (Immediate or Cancel)**
    Execute immediately, cancel any unfilled portion

**FOK (Fill or Kill)**
    Execute completely or cancel the entire order

**POST_ONLY**
    Only add liquidity to the order book, never take liquidity

Example:

.. code-block:: python

    from nado_protocol.utils.order import build_appendix
    from nado_protocol.utils.expiration import OrderType

    # Create different order types
    ioc_appendix = build_appendix(order_type=OrderType.IOC)
    fok_appendix = build_appendix(order_type=OrderType.FOK)
    post_only_appendix = build_appendix(order_type=OrderType.POST_ONLY)

Isolated Positions
-----------------

Isolated positions allow you to allocate specific margin to a trade, limiting your risk:

.. code-block:: python

    from nado_protocol.utils.order import build_appendix
    from nado_protocol.utils.expiration import OrderType
    from nado_protocol.utils.math import to_x6

    # Create isolated position with 1000 USDC margin
    # Note: isolated margin uses x6 precision and is limited to 64-bit values
    isolated_appendix = build_appendix(
        isolated=True,
        isolated_margin=to_x6(1000),
        order_type=OrderType.POST_ONLY
    )

.. note::
    
    Isolated positions and TWAP orders are mutually exclusive - you cannot have both in the same order.

TWAP Orders
----------

Time-Weighted Average Price (TWAP) orders split large orders into smaller chunks executed over time:

.. code-block:: python

    from nado_protocol.utils.order import build_appendix, OrderAppendixTriggerType

    # Create TWAP order with 10 child orders and 0.5% slippage tolerance
    twap_appendix = build_appendix(
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=10,
        twap_slippage_frac=0.005
    )

    # TWAP with custom amounts and reduce-only
    twap_custom_appendix = build_appendix(
        trigger_type=OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
        twap_times=5,
        twap_slippage_frac=0.01,
        reduce_only=True
    )

Trigger Orders
-------------

Trigger orders can be configured with different trigger types:

.. code-block:: python

    from nado_protocol.utils.order import build_appendix, OrderAppendixTriggerType
    from nado_protocol.utils.expiration import OrderType

    # Price-based trigger order
    price_trigger_appendix = build_appendix(
        trigger_type=OrderAppendixTriggerType.PRICE,
        order_type=OrderType.IOC,
        reduce_only=True
    )

Extracting Appendix Information
------------------------------

You can extract information from an existing appendix:

.. code-block:: python

    from nado_protocol.utils.order import (
        order_version,
        order_execution_type,
        order_reduce_only,
        order_is_isolated,
        order_isolated_margin,
        order_is_trigger_order,
        order_trigger_type,
        order_twap_data
    )

    from nado_protocol.utils.math import to_x6

    appendix = build_appendix(
        isolated=True,
        isolated_margin=to_x6(500),
        order_type=OrderType.IOC,
        reduce_only=True
    )

    # Extract information
    version = order_version(appendix)
    execution_type = order_execution_type(appendix)
    is_reduce_only = order_reduce_only(appendix)
    is_isolated = order_is_isolated(appendix)
    margin = order_isolated_margin(appendix)
    is_trigger = order_is_trigger_order(appendix)
    trigger_type = order_trigger_type(appendix)

    print(f"Order Type: {execution_type.name}")
    print(f"Reduce Only: {is_reduce_only}")
    print(f"Isolated: {is_isolated}")
    if margin:
        print(f"Isolated Margin: {margin}")

Using Appendix with Orders
-------------------------

When placing orders, include the appendix in your order parameters:

.. code-block:: python

    from nado_protocol.engine_client.types import OrderParams, PlaceOrderParams
    from nado_protocol.utils.order import build_appendix
    from nado_protocol.utils.expiration import OrderType
    from nado_protocol.utils.subaccount import SubaccountParams
    import time

    # Create appendix for a reduce-only IOC order
    appendix = build_appendix(
        order_type=OrderType.IOC,
        reduce_only=True
    )

    # Create order with appendix
    order = OrderParams(
        sender=SubaccountParams(subaccount_owner="0x...", subaccount_name="default"),
        priceX18=28898000000000000000000,
        amount=-10000000000000000,  # Sell to close position
        expiration=int(time.time()) + 3600,  # 1 hour from now
        appendix=appendix
    )

    # Place the order
    client.market.place_order(PlaceOrderParams(product_id=1, order=order))

Complex Trading Scenarios
-------------------------

Here are examples of complex trading scenarios using appendix:

**Stop Loss Order**

.. code-block:: python

    # Stop loss: reduce-only IOC order that executes immediately when triggered
    stop_loss_appendix = build_appendix(
        order_type=OrderType.IOC,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.PRICE
    )

**Take Profit Order**

.. code-block:: python

    # Take profit: reduce-only post-only order to avoid paying taker fees
    take_profit_appendix = build_appendix(
        order_type=OrderType.POST_ONLY,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.PRICE
    )

**Breakout Strategy with Isolated Position**

.. code-block:: python

    from nado_protocol.utils.math import to_x6

    # Enter position on breakout with dedicated margin
    # Note: isolated margin uses x6 precision and is limited to 64-bit values
    breakout_appendix = build_appendix(
        isolated=True,
        isolated_margin=to_x6(5000),  # 5000 USDC dedicated margin
        order_type=OrderType.IOC
    )

**Large Order with TWAP**

.. code-block:: python

    # Split large order into 20 smaller orders with 0.1% slippage tolerance
    twap_appendix = build_appendix(
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=20,
        twap_slippage_frac=0.001
    )

Validation Rules
---------------

The appendix system enforces several validation rules:

- **Isolated + TWAP Exclusion**: An order cannot be both isolated and a TWAP order
- **TWAP Parameters**: TWAP orders require both `twap_times` and `twap_slippage_frac`
- **Isolated Margin**: `isolated_margin` can only be set when `isolated=True`
- **Margin Limits**: Isolated margin uses x6 precision and must be between 0 and 2^64 - 1

Error Handling
--------------

The appendix functions will raise `ValueError` for invalid configurations:

.. code-block:: python

    from nado_protocol.utils.math import to_x6

    # This will raise ValueError: isolated_margin can only be set when isolated=True
    try:
        build_appendix(isolated=False, isolated_margin=to_x6(1000))
    except ValueError as e:
        print(f"Error: {e}")

    # This will raise ValueError: TWAP parameters required
    try:
        build_appendix(trigger_type=OrderAppendixTriggerType.TWAP)
    except ValueError as e:
        print(f"Error: {e}")

    # This will raise ValueError: Isolated and TWAP are mutually exclusive
    try:
        build_appendix(
            isolated=True,
            isolated_margin=to_x6(1000),
            trigger_type=OrderAppendixTriggerType.TWAP,
            twap_times=5,
            twap_slippage_frac=0.01
        )
    except ValueError as e:
        print(f"Error: {e}")

API Reference
------------

For detailed API documentation, see:

- :func:`nado_protocol.utils.order.build_appendix`
- :func:`nado_protocol.utils.order.order_version`
- :func:`nado_protocol.utils.order.order_execution_type`
- :func:`nado_protocol.utils.order.order_reduce_only`
- :func:`nado_protocol.utils.order.order_is_isolated`
- :func:`nado_protocol.utils.order.order_isolated_margin`
- :func:`nado_protocol.utils.order.order_is_trigger_order`
- :func:`nado_protocol.utils.order.order_trigger_type`
- :func:`nado_protocol.utils.order.order_twap_data`
- :class:`nado_protocol.utils.order.OrderAppendixTriggerType`