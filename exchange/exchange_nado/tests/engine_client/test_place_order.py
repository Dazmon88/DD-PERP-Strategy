import json
from unittest.mock import MagicMock

from eth_account import Account
from eth_account.signers.local import LocalAccount
from nado_protocol.contracts.eip712.sign import (
    build_eip712_typed_data,
    sign_eip712_typed_data,
)
from nado_protocol.engine_client import EngineClient
from nado_protocol.contracts.types import NadoExecuteType

from nado_protocol.engine_client.types.execute import (
    OrderParams,
    PlaceOrderParams,
    PlaceOrderRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import (
    bytes32_to_hex,
    hex_to_bytes32,
    subaccount_to_bytes32,
)
import pytest
from nado_protocol.utils.exceptions import ExecuteFailedException

from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.order import (
    gen_order_verifying_contract,
    build_appendix,
    OrderAppendixTriggerType,
)
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.expiration import OrderType
from nado_protocol.utils.math import to_x18


def test_place_order_params(senders: list[str], owners: list[str], order_params: dict):
    product_id = 1
    sender = hex_to_bytes32(senders[0])
    params_from_dict = PlaceOrderParams(
        **{
            "product_id": product_id,
            "order": {
                "sender": senders[0],
                "priceX18": order_params["priceX18"],
                "amount": order_params["amount"],
                "appendix": order_params["appendix"],
                "expiration": order_params["expiration"],
            },
        }
    )
    params_from_obj = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=senders[0],
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
    )
    bytes32_sender = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=hex_to_bytes32(senders[0]),
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
    )
    subaccount_params_sender = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=SubaccountParams(
                subaccount_owner=owners[0], subaccount_name="default"
            ),
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
    )

    assert (
        params_from_dict
        == params_from_obj
        == bytes32_sender
        == subaccount_params_sender
    )

    assert params_from_dict.product_id == product_id
    assert params_from_dict.order.sender == sender
    assert params_from_dict.order.amount == order_params["amount"]
    assert params_from_dict.order.priceX18 == order_params["priceX18"]
    assert params_from_dict.order.expiration == order_params["expiration"]
    assert params_from_dict.order.appendix == order_params["appendix"]
    assert params_from_dict.signature is None

    params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    params_from_dict.order.nonce = gen_order_nonce()
    place_order_req = PlaceOrderRequest(place_order=params_from_dict)
    assert place_order_req == to_execute_request(params_from_dict)
    assert place_order_req.dict() == {
        "place_order": {
            "product_id": product_id,
            "order": {
                "sender": senders[0].lower(),
                "priceX18": str(order_params["priceX18"]),
                "amount": str(order_params["amount"]),
                "expiration": str(order_params["expiration"]),
                "appendix": str(order_params["appendix"]),
                "nonce": str(params_from_dict.order.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }

    params_from_dict.id = 100
    place_order_req = PlaceOrderRequest(place_order=params_from_dict)
    assert place_order_req == to_execute_request(params_from_dict)
    assert place_order_req.dict() == {
        "place_order": {
            "id": 100,
            "product_id": product_id,
            "order": {
                "sender": senders[0].lower(),
                "priceX18": str(order_params["priceX18"]),
                "amount": str(order_params["amount"]),
                "expiration": str(order_params["expiration"]),
                "appendix": str(order_params["appendix"]),
                "nonce": str(params_from_dict.order.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }


def test_place_order_execute_fails_incomplete_client(
    mock_post: MagicMock,
    url: str,
    chain_id: int,
    private_keys: list[str],
    senders: list[str],
    order_params: dict,
):
    engine_client = EngineClient({"url": url})
    place_order_params = {
        "product_id": 1,
        "order": order_params,
    }

    with pytest.raises(AttributeError, match="Chain ID is not set."):
        engine_client.place_order(place_order_params)

    engine_client.chain_id = chain_id

    with pytest.raises(AttributeError, match="Signer is not set."):
        engine_client.place_order(place_order_params)

    engine_client.signer = Account.from_key(private_keys[0])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "xxx",
    }
    mock_post.return_value = mock_response

    res = engine_client.place_order(place_order_params)
    place_order_req = PlaceOrderRequest(**res.req)

    assert place_order_req.place_order.order.sender.lower() == senders[0].lower()


def test_place_order_execute_success(
    engine_client: EngineClient, mock_post: MagicMock, senders: list[str]
):
    product_id = 1
    place_order_params = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=SubaccountParams(subaccount_name="default"),
            priceX18=1000,
            amount=1000,
            expiration=1000,
            nonce=1000,
            appendix=0,
        ),
    )

    order = place_order_params.order.copy(deep=True)
    order_digest = "0x123"
    order.sender = hex_to_bytes32(senders[0])

    with pytest.raises(
        ValueError,
        match="Missing `product_id` to sign place_order execute",
    ):
        engine_client._sign(NadoExecuteType.PLACE_ORDER, order.dict())

    expected_signature = engine_client._sign(
        NadoExecuteType.PLACE_ORDER,
        order.dict(),
        product_id=place_order_params.product_id,
    )
    computed_signature = sign_eip712_typed_data(
        typed_data=build_eip712_typed_data(
            NadoExecuteType.PLACE_ORDER,
            order.dict(),
            gen_order_verifying_contract(1),
            engine_client.chain_id,
        ),
        signer=engine_client._opts.linked_signer,
    )

    assert expected_signature == computed_signature

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": expected_signature,
        "data": {"digest": order_digest},
    }
    mock_post.return_value = mock_response

    res = engine_client.place_order(place_order_params)
    place_order_req = PlaceOrderRequest(**res.req)

    assert place_order_req.place_order.signature == res.signature == expected_signature
    assert place_order_req.place_order.order.sender.lower() == senders[0].lower()
    assert res.status == "success"
    assert res.error is None
    assert res.data.digest == order_digest

    mock_response.status_code = 200
    json_response = {
        "status": "failure",
        "error_code": 1000,
        "error": "Too Many Requests!",
    }
    mock_response.json.return_value = json_response
    mock_post.return_value.text = json.dumps(json_response)

    with pytest.raises(ExecuteFailedException, match=json.dumps(json_response)):
        engine_client.place_order(place_order_params)

    # deactivate linked signer
    engine_client.linked_signer = None

    expected_signature = sign_eip712_typed_data(
        typed_data=build_eip712_typed_data(
            NadoExecuteType.PLACE_ORDER,
            order.dict(),
            gen_order_verifying_contract(1),
            engine_client.chain_id,
        ),
        signer=engine_client._opts.signer,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": expected_signature,
    }
    mock_post.return_value = mock_response

    res = engine_client.place_order(place_order_params)
    place_order_req = PlaceOrderRequest(**res.req)

    assert place_order_req.place_order.signature == expected_signature


def test_place_order_execute_provide_full_params(
    mock_post: MagicMock, url: str, chain_id: int, private_keys: list[str]
):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "xxx",
    }
    mock_post.return_value = mock_response

    engine_client = EngineClient({"url": url})
    signer: LocalAccount = Account.from_key(private_keys[0])
    sender = subaccount_to_bytes32(signer.address, "default")
    product_id = 1
    order_params = {
        "priceX18": 10000,
        "amount": 10000,
        "sender": sender,
        "nonce": gen_order_nonce(),
        "appendix": 0,
        "expiration": 10000,
    }
    signature = engine_client.sign(
        NadoExecuteType.PLACE_ORDER,
        order_params,
        gen_order_verifying_contract(product_id),
        chain_id,
        signer,
    )
    order_params["sender"] = bytes32_to_hex(order_params["sender"])
    res = engine_client.place_order(
        {"product_id": product_id, "order": order_params, "signature": signature}
    )
    req = PlaceOrderRequest(**res.req)

    assert req.place_order.signature == signature
    assert req.place_order.order.amount == str(order_params["amount"])
    assert req.place_order.order.priceX18 == str(order_params["priceX18"])
    assert req.place_order.order.sender == order_params["sender"]
    assert req.place_order.order.nonce == str(order_params["nonce"])
    assert req.place_order.order.expiration == str(order_params["expiration"])
    assert req.place_order.order.appendix == str(order_params["appendix"])


def test_place_order_with_basic_appendix(senders: list[str], owners: list[str]):
    """Test placing order with basic appendix functionality."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Test with IOC order type
    ioc_appendix = build_appendix(OrderType.IOC)
    params = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-10000000000000000,
            expiration=4611687701117784255,
            appendix=ioc_appendix,
        ),
    )

    assert params.order.appendix == ioc_appendix

    # Test with reduce-only flag
    reduce_only_appendix = build_appendix(OrderType.POST_ONLY, reduce_only=True)
    params_reduce = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-10000000000000000,
            expiration=4611687701117784255,
            appendix=reduce_only_appendix,
        ),
    )

    assert params_reduce.order.appendix == reduce_only_appendix


def test_place_order_with_isolated_position_appendix(senders: list[str]):
    """Test placing order with isolated position appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])
    margin = 1000000  # 1M units margin

    isolated_appendix = build_appendix(
        OrderType.POST_ONLY, isolated=True, reduce_only=False, isolated_margin=margin
    )

    params = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=10000000000000000,  # Long position
            expiration=4611687701117784255,
            appendix=isolated_appendix,
        ),
    )

    assert params.order.appendix == isolated_appendix


def test_place_order_with_twap_appendix(senders: list[str]):
    """Test placing order with TWAP appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Test regular TWAP
    twap_appendix = build_appendix(
        OrderType.DEFAULT,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=10,
        twap_slippage_frac=0.005,  # 0.5% slippage
    )

    params = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=10000000000000000,
            expiration=4611687701117784255,
            appendix=twap_appendix,
        ),
    )

    assert params.order.appendix == twap_appendix

    # Test TWAP with custom amounts
    twap_custom_appendix = build_appendix(
        OrderType.DEFAULT,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
        twap_times=5,
        twap_slippage_frac=0.01,  # 1% slippage
    )

    params_custom = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-10000000000000000,  # Close position
            expiration=4611687701117784255,
            appendix=twap_custom_appendix,
        ),
    )

    assert params_custom.order.appendix == twap_custom_appendix


def test_place_order_with_price_trigger_appendix(senders: list[str]):
    """Test placing order with price trigger appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    trigger_appendix = build_appendix(
        OrderType.IOC, reduce_only=True, trigger_type=OrderAppendixTriggerType.PRICE
    )

    params = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-5000000000000000,  # Partial close
            expiration=4611687701117784255,
            appendix=trigger_appendix,
        ),
    )

    assert params.order.appendix == trigger_appendix


def test_place_order_appendix_combinations(senders: list[str]):
    """Test various valid appendix combinations."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Test all order types with reduce-only
    order_types = [OrderType.DEFAULT, OrderType.IOC, OrderType.FOK, OrderType.POST_ONLY]

    for order_type in order_types:
        appendix = build_appendix(order_type, reduce_only=True)

        params = PlaceOrderParams(
            product_id=product_id,
            order=OrderParams(
                sender=sender,
                priceX18=28898000000000000000000,
                amount=-10000000000000000,
                expiration=4611687701117784255,
                appendix=appendix,
            ),
        )

        assert params.order.appendix == appendix

    # Test isolated position with different order types
    for order_type in [OrderType.DEFAULT, OrderType.POST_ONLY]:
        isolated_appendix = build_appendix(
            order_type, isolated=True, isolated_margin=to_x18(500000)
        )

        params = PlaceOrderParams(
            product_id=product_id,
            order=OrderParams(
                sender=sender,
                priceX18=28898000000000000000000,
                amount=10000000000000000,
                expiration=4611687701117784255,
                appendix=isolated_appendix,
            ),
        )

        assert params.order.appendix == isolated_appendix
