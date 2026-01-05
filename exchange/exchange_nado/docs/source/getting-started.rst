.. _getting-started:

Getting started
===============

Introduction
------------

This SDK offers methods to perform all operations on Nado such as trading, managing your collaterals, etc. 

Basic usage
-----------

Before you start, import the necessary utilities:

.. code-block:: python

    import time
    from nado_protocol.client import create_nado_client
    from nado_protocol.engine_client.types.execute import (
        OrderParams,
        PlaceOrderParams,
        WithdrawCollateralParams,
        CancelOrdersParams
    )
    from nado_protocol.contracts.types import DepositCollateralParams
    from nado_protocol.utils.bytes32 import subaccount_to_bytes32, subaccount_to_hex
    from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
    from nado_protocol.utils.math import to_pow_10, to_x18
    from nado_protocol.utils.nonce import gen_order_nonce
    from nado_protocol.utils.subaccount import SubaccountParams
    from nado_protocol.utils.order import build_appendix

The following sections outline the main functionalities:

Making a deposit
----------------
.. note::
    
    Remember to always keep your signer's private key securely stored and never expose it to the public.

The primary entry point of the SDK is via `create_nado_client`, which allows you to create an instance of `NadoClient`.
See  :doc:`api-reference` for more details.

.. code-block:: python

    >>> private_key = "xxx"
    >>> print("setting up nado client...")
    >>> client = create_nado_client("devnet", private_key)
    >>> # You must first approve allowance for the amount you want to deposit.
    >>> print("approving allowance...")
    >>> approve_allowance_tx_hash = client.spot.approve_allowance(0, to_pow_10(100000, 6))
    >>> print("approve allowance tx hash:", approve_allowance_tx_hash)
    >>> # Now, you can make the actual deposit.
    >>> print("depositing collateral...")
    >>> deposit_tx_hash = client.spot.deposit(
            DepositCollateralParams(
                subaccount_name="default", product_id=0, amount=to_pow_10(100000, 6)
            )
        )
    >>> print("deposit collateral tx hash:", deposit_tx_hash)

Placing an order
----------------

Places an order via `execute:place_order <TODO>`_.

.. code-block:: python

    >>> owner = client.context.engine_client.signer.address
    >>> print("placing order...")
    >>> product_id = 1
    >>> order = OrderParams(
            sender=SubaccountParams(
                subaccount_owner=owner,
                subaccount_name="default",
            ),
            priceX18=to_x18(20000),
            amount=to_pow_10(1, 17),
            expiration=get_expiration_timestamp(40),
            nonce=gen_order_nonce(),
            appendix=build_appendix(OrderType.POST_ONLY)
        )
    >>> res = client.market.place_order(PlaceOrderParams(product_id=1, order=order))
    >>> print("order result:", res.json(indent=2))

Viewing open orders
-------------------

Queries your open orders via `query:subaccount_orders <TODO>`_.

.. code-block:: python

    >>> sender = subaccount_to_hex(order.sender)
    >>> print("querying open orders...")
    >>> open_orders = client.market.get_subaccount_open_orders(1, sender)
    >>> print("open orders:", open_orders.json(indent=2))

Retrieving an order digest
--------------------------

.. note::
    
    The order digest is necessary to perform order cancellation via `client.market.cancel_orders`

.. code-block:: python

    >>> order.sender = subaccount_to_bytes32(order.sender)
    >>> order_digest = client.context.engine_client.get_order_digest(order, product_id)
    >>> print("order digest:", order_digest)

Cancelling an order
-------------------

Cancels open orders via `execute:cancel_orders <TODO>`_.

.. code-block:: python

    >>> print("cancelling order...")
    >>> res = client.market.cancel_orders(
            CancelOrdersParams(productIds=[product_id], digests=[order_digest], sender=sender)
        )
    >>> print("cancel order result:", res.json(indent=2))

Withdrawing collateral
----------------------

Withdraw spot collaterals from Nado via `execute:withdraw_collateral <TODO>`_.

.. code-block:: python

    >>> print("withdrawing collateral...")
    >>> withdraw_collateral_params = WithdrawCollateralParams(
            productId=0, amount=to_pow_10(10000, 6), sender=sender
        )
    >>> res = client.spot.withdraw(withdraw_collateral_params)
    >>> print("withdraw result:", res.json(indent=2))