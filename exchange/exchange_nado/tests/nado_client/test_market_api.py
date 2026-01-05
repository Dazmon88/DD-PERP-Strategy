from unittest.mock import MagicMock

from nado_protocol.client import NadoClient
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    CancelOrdersParams,
    CancelProductOrdersParams,
    MintNlpParams,
    OrderParams,
    PlaceOrderParams,
)
from nado_protocol.utils.bytes32 import subaccount_to_bytes32


def test_mint_nlp(
    nado_client: NadoClient,
    senders: list[str],
    mock_tx_nonce: MagicMock,
    mock_execute_response: MagicMock,
):
    params = MintNlpParams(sender=senders[0], quoteAmount=10)
    res = nado_client.market.mint_nlp(params)
    params.sender = subaccount_to_bytes32(senders[0])
    params.nonce = 1
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.MINT_NLP,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.req == {
        "mint_nlp": {
            "tx": {
                "quoteAmount": "10",
                "sender": senders[0].lower(),
                "nonce": "1",
            },
            "signature": signature,
        }
    }


def test_burn_nlp(
    nado_client: NadoClient,
    senders: list[str],
    mock_execute_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    params = BurnNlpParams(sender=senders[0], productId=1, nlpAmount=10)
    res = nado_client.market.burn_nlp(params)
    params.sender = subaccount_to_bytes32(senders[0])
    params.nonce = 1
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.BURN_NLP,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.req == {
        "burn_nlp": {
            "tx": {
                "nlpAmount": "10",
                "sender": senders[0].lower(),
                "nonce": "1",
            },
            "signature": signature,
        }
    }


def test_place_order(
    nado_client: NadoClient,
    senders: list[str],
    mock_place_order_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    order = OrderParams(
        sender=senders[0], priceX18=1000, amount=1, expiration=1, nonce=1, appendix=0
    )
    params = PlaceOrderParams(product_id=1, order=order)
    res = nado_client.market.place_order(params)
    order.sender = subaccount_to_bytes32(senders[0])
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.PLACE_ORDER,
        order.dict(),
        nado_client.context.engine_client.order_verifying_contract(1),
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.data.digest == "0x123"
    assert res.req == {
        "place_order": {
            "product_id": 1,
            "order": {
                "sender": senders[0].lower(),
                "priceX18": str(1000),
                "amount": str(1),
                "expiration": str(1),
                "appendix": str(0),
                "nonce": str(1),
            },
            "signature": signature,
        }
    }


def test_cancel_orders(
    nado_client: NadoClient,
    senders: list[str],
    mock_cancel_orders_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    mock_cancel_orders_response()
    params = CancelOrdersParams(
        sender=senders[0],
        productIds=[1],
        digests=["0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"],
        nonce=2,
    )
    res = nado_client.market.cancel_orders(params)
    params.sender = subaccount_to_bytes32(senders[0])
    nado_client.context.engine_client.sign(
        NadoExecuteType.CANCEL_ORDERS,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    cancelled_order = res.data.cancelled_orders.pop()
    assert cancelled_order.product_id == 1
    assert cancelled_order.amount == str(-10000000000000000)
    assert cancelled_order.nonce == str(1)


def test_cancel_product_orders(
    nado_client: NadoClient,
    senders: list[str],
    mock_cancel_orders_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    mock_cancel_orders_response()
    params = CancelProductOrdersParams(
        sender=senders[0],
        productIds=[1],
        nonce=2,
    )

    res = nado_client.market.cancel_product_orders(params)
    params.sender = subaccount_to_bytes32(senders[0])
    nado_client.context.engine_client.sign(
        NadoExecuteType.CANCEL_PRODUCT_ORDERS,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    cancelled_order = res.data.cancelled_orders.pop()
    assert cancelled_order.product_id == 1
    assert cancelled_order.amount == str(-10000000000000000)
    assert cancelled_order.nonce == str(1)


def test_place_twap_order(
    nado_client_with_trigger: NadoClient,
    mock_place_trigger_order_response: MagicMock,
):
    mock_place_trigger_order_response()
    res = nado_client_with_trigger.market.place_twap_order(
        product_id=1,
        price_x18="50000000000000000000000",
        total_amount_x18="5000000000000000000",
        times=10,
        slippage_frac=0.005,
        interval_seconds=3600,
    )
    assert res.status == "success"


def test_place_price_trigger_order(
    nado_client_with_trigger: NadoClient,
    mock_place_trigger_order_response: MagicMock,
):
    mock_place_trigger_order_response()
    res = nado_client_with_trigger.market.place_price_trigger_order(
        product_id=1,
        price_x18="45000000000000000000000",
        amount_x18="-1000000000000000000",
        trigger_price_x18="46000000000000000000000",
        trigger_type="last_price_below",
        reduce_only=True,
    )
    assert res.status == "success"
