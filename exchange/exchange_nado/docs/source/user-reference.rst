User reference
==============

Core client
-----------
You must initialize the Nado client via the `create_nado_client` util for proper setup:

.. note::

    You can instantiate the client by providing either a private key, or an instance of `LocalAccount`.

.. code-block:: python
    
    >>> from eth_account import Account
    >>> from eth_account.signers.local import LocalAccount
    >>> from nado_protocol.client import create_nado_client
    >>> client_from_private_key = create_nado_client("devnet", "xxx")
    >>> signer: LocalAccount = Account.from_key("xxx")
    >>> client_from_signer = create_nado_client("devnet", signer)

See :mod:`nado_protocol.client.create_nado_client()` for details.

.. note::

    **Your private key is only used to sign transactions locally.** You can optionally interact with the EIP-712 utilities directly (see :ref:`eip-712`) to construct the required signatures for each of Nado's executes. 

The core Nado client is sub-divided into the following APIs:

Market API
----------
The Market API allows you to manage and execute orders on the Nado Protocol. Here, you can explore:

- `Placing an order <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.engine_client.types import OrderParams, PlaceOrderParams
    >>> from nado_protocol.utils.order import build_appendix
    >>> from nado_protocol.utils.expiration import OrderType
    >>> appendix = build_appendix(order_type=OrderType.IOC, reduce_only=True)
    >>> order = OrderParams(..., appendix=appendix)
    >>> client.market.place_order(PlaceOrderParams(order=order, ...))

- `Canceling an order <TODO>`_:

.. code-block:: python

    >>> from nado-protocol.engine_client.types import CancelOrdersParams
    >>> client.market.cancel_orders(CancelOrdersParams(...))

- `Cancelling all orders <TODO>`_:

.. code-block:: Python

    >>> from nado-protocol.engine_client.types import CancelProductOrdersParams
    >>> client.market.cancel_product_orders(CancelProductOrdersParams(...))

- `Minting LP <TODO>`_:

    >>> from nado-protocol.engine_client.types import MintNlpParams
    >>> client.market.mint_nlp(MintNlpParams(...))

- `Burning LP <TODO>`_:

    >>> from nado-protocol.engine_client.types import BurnNlpParams
    >>> client.market.burn_nlp(BurnNlpParams(...))

You also have available the following queries:

- `Retrieves all market states from the off-chain engine <TODO>`_:

.. code-block:: python

    >>> client.market.get_all_engine_markets()

- `Retrieves liquidity per price tick from the engine <TODO>`_:

.. code-block:: python

    >>> client.market.get_market_liquidity()

- `Retrieves the latest off-chain orderbook price for a specific product <TODO>`_:

.. code-block:: python

    >>> client.market.get_latest_market_price(1)

- `Retrieves subaccount open orders <TODO>`_:

.. code-block:: python

    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> client.market.get_subaccount_open_orders(1, sender)

-  `Retrieves subaccount historical orders <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.indexer_client.types import IndexerSubaccountHistoricalOrdersParams
    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> params = IndexerSubaccountHistoricalOrdersParams(subaccount=sender)
    >>> client.market.get_subaccount_historical_orders(params)

- `Retrieves historical orders by digest <TODO>`_:

.. code-block:: python

    >>> digests = ["0xf4f7a8767faf0c7f72251a1f9e5da590f708fd9842bf8fcdeacbaa0237958fff"]
    >>> client.market.get_historical_orders_by_digest(digests)

- `Retrieves the max amount of LP mintable possible for a subaccount <TODO>`_:

.. code-block:: python

    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> client.market.get_max_nlp_mintable(1, sender)

- `Retrieves candlesticks for a product <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.indexer_client.types import IndexerCandlesticksParams, IndexerCandlesticksGranularity
    >>> params = IndexerCandlesticksParams(product_id=1, granularity=IndexerCandlesticksGranularity.FIVE_MINUTES)
    >>> client.market.get_candlesticks(params)

- `Retrieves the latest funding rate for a specific perp product <TODO>`_:

.. code-block:: python

    >>> client.market.get_perp_funding_rate(2)

- `Retrieves the latest oracle prices for provided products <TODO>`_:

.. code-block:: python

    >>> client.market.get_oracle_prices([1, 2, 3, 4])

- `Retrieves token rewards for a wallet <TODO>`_:

.. code-block:: python

    >>> wallet = "0xf8d240d9514c9a4715d66268d7af3b53d6196425"
    >>> client.market.get_token_rewards(wallet)

.. note::

    See :mod:`nado_protocol.client.apis.MarketAPI` to explore all available operations.

Spot API
--------
The Spot API allows you to manage your spot collaterals. Here, you can explore:

- `Making a deposit <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.utils.math import to_pow_10
    >>> from nado_protocol.contracts.types import DepositCollateralParams
    >>> deposit_tx_hash = client.spot.deposit(
            DepositCollateralParams(
                subaccount_name="default", product_id=0, amount=to_pow_10(100000, 6)
            )
        )

See :mod:`nado_protocol.client.apis.SpotExecuteAPI.deposit()` for details.

- `Withdrawing collateral <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.engine_client.types import WithdrawCollateralParams
    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> withdraw_collateral_params = WithdrawCollateralParams(
            productId=0, amount=to_pow_10(10000, 6), sender=sender
        )
    >>> client.spot.withdraw(withdraw_collateral_params)

.. note::

    See :mod:`nado_protocol.client.apis.SpotAPI` to explore all available operations.

Perp API
--------
The Perp API for actions and queries specific to Perps. Here, you can explore:

- `Retrieves the latest index and mark price for a specific perp product <TODO>`_:

.. code-block:: python

    >>> client.perp.get_prices(2)

.. note::

    See :mod:`nado_protocol.client.apis.PerpAPI` to explore all available operations.

Subaccount API
--------------
The Subaccount API allows you to manage your subaccounts. Here, you can explore:

- `Link a signer to a subaccount <TODO>`_:

.. code-block:: python

    >>> from nado_protocol.engine_client.types import LinkSignerParams
    >>> params = LinkSignerParams(signer="0xeae27ae6412147ed6d5692fd91709dad6dbfc34264656661756c740000000000")
    >>> client.subaccount.link_signer(params)

- `Retrieves the sate of a subaccount in the off-chain engine <TODO>`_:

.. code-block:: python

    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> client.subaccount.get_engine_subaccount_summary(sender)


- `Retrieves subaccount fee rates <TODO>`_:

.. code-block:: python

    >>> sender = "0xe526299d13c956ed6b9b3e03086a152c6396947364656661756c740000000000"
    >>> client.subaccount.get_subaccount_fee_rates(sender)

.. note::

    See :mod:`nado_protocol.client.apis.SubaccountAPI` to explore all available operations.

Engine Client
-------------
The Engine Client provides low-level functionalities that are integral to interacting with the Nado Protocol, including:

- Signing transactions: 

.. code-block:: python

    >>> client.context.engine_client.sign(...)

- Getting the signer address: 

.. code-block:: python

    >>> client.context.engine_client.signer.address

- Getting an order digest: 

.. code-block:: python

    >>> client.context.engine_client.get_order_digest()

.. note::

    See :mod:`nado_protocol.engine_client` to explore all available operations.

Indexer Client
--------------
The Indexer Client provides functionalities for interacting with the Nado Protocol indexer. This can be particularly useful for fetching historical data. Here you can explore:

.. code-block:: python

    >>> # Retrieves subaccount historical matches.
    >>> client.context.indexer_client.get_matches(...)
    >>> # Retrieves linked signer rate limits
    >>> client.context.indexer_client.get_linked_signer_rate_limits(...)

.. note::

    See :mod:`nado_protocol.indexer_client` to explore all available operations.

Nado Contracts
----------------

A utility module to interact directly with Nado contracts. You can interface with this module via the client's context (see :mod:`nado_protocol.client.NadoClientContext`). 

.. code-block:: python

    >>> # approving allowance
    >>> client.context.contracts.approve_allowance(...)
    >>> # executing a contract function, retrieves the OffchainBook for product_id 1
    >>> client.context.contract.endpoint.functions.getBook(1).call()

.. note::

    See :mod:`nado_protocol.contracts.NadoContracts` to explore all available operations.

Nado utils
----------------

A set of utility helpers. See :mod:`nado_protocol.utils`.

The utils module includes powerful order appendix functionality for advanced trading features like isolated positions, TWAP orders, and custom execution types. See :doc:`order-appendix` for comprehensive documentation.

See  :doc:`api-reference` for detailed information about each module. 
