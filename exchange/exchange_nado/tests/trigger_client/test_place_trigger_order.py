from unittest.mock import MagicMock
import json
from eth_account import Account
import pytest
from nado_protocol.contracts.eip712.sign import (
    build_eip712_typed_data,
    sign_eip712_typed_data,
)
from eth_account.signers.local import LocalAccount
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.engine_client.types.execute import OrderParams
from nado_protocol.trigger_client import TriggerClient
from nado_protocol.trigger_client.types.execute import (
    PlaceTriggerOrderParams,
    PlaceTriggerOrderRequest,
    to_trigger_execute_request,
)
from nado_protocol.trigger_client.types.models import (
    PriceTriggerData,
    PriceTrigger,
    LastPriceBelow,
    LastPriceAbove,
)
from nado_protocol.utils.bytes32 import (
    bytes32_to_hex,
    hex_to_bytes32,
    subaccount_to_bytes32,
)
from nado_protocol.utils.exceptions import ExecuteFailedException
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.order import (
    gen_order_verifying_contract,
    build_appendix,
    OrderAppendixTriggerType,
)
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.math import to_x18
from nado_protocol.utils.expiration import OrderType
from nado_protocol.trigger_client.types.models import (
    PriceTriggerData,
    TimeTrigger,
    OraclePriceAbove,
    OraclePriceBelow,
    MidPriceAbove,
    MidPriceBelow,
)
from nado_protocol.utils.order import (
    order_trigger_type,
    order_twap_data,
    order_execution_type,
)


def test_place_trigger_order_params(
    senders: list[str], owners: list[str], order_params: dict
):
    product_id = 1
    sender = hex_to_bytes32(senders[0])
    params_from_dict = PlaceTriggerOrderParams(
        **{
            "product_id": product_id,
            "order": {
                "sender": senders[0],
                "priceX18": order_params["priceX18"],
                "amount": order_params["amount"],
                "expiration": order_params["expiration"],
                "appendix": order_params["appendix"],
            },
            "trigger": {
                "price_trigger": {
                    "price_requirement": {"last_price_below": "9900000000000000000000"}
                }
            },
        }
    )
    params_from_obj = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=senders[0],
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="9900000000000000000000"
                )
            )
        ),
    )
    bytes32_sender = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=hex_to_bytes32(senders[0]),
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="9900000000000000000000"
                )
            )
        ),
    )
    subaccount_params_sender = PlaceTriggerOrderParams(
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
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="9900000000000000000000"
                )
            )
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
    assert (
        params_from_dict.trigger.price_trigger.price_requirement.last_price_below
        == "9900000000000000000000"
    )
    assert params_from_dict.signature is None

    params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    params_from_dict.order.nonce = gen_order_nonce()
    place_trigger_order_req = PlaceTriggerOrderRequest(place_order=params_from_dict)
    assert place_trigger_order_req == to_trigger_execute_request(params_from_dict)
    assert place_trigger_order_req.dict() == {
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
            "trigger": {
                "price_trigger": {
                    "price_requirement": {"last_price_below": "9900000000000000000000"}
                }
            },
        }
    }

    params_from_dict.id = 100
    place_trigger_order_req = PlaceTriggerOrderRequest(place_order=params_from_dict)
    assert place_trigger_order_req == to_trigger_execute_request(params_from_dict)
    assert place_trigger_order_req.dict() == {
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
            "trigger": {
                "price_trigger": {
                    "price_requirement": {"last_price_below": "9900000000000000000000"}
                }
            },
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
    trigger_client = TriggerClient({"url": url})
    place_trigger_order_params = {
        "product_id": 1,
        "order": order_params,
        "trigger": {
            "price_trigger": {
                "price_requirement": {"last_price_below": "9900000000000000000000"}
            }
        },
    }

    with pytest.raises(AttributeError, match="Chain ID is not set."):
        trigger_client.place_trigger_order(place_trigger_order_params)

    trigger_client.chain_id = chain_id

    with pytest.raises(AttributeError, match="Signer is not set."):
        trigger_client.place_trigger_order(place_trigger_order_params)

    trigger_client.signer = Account.from_key(private_keys[0])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "xxx",
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_trigger_order(place_trigger_order_params)
    place_trigger_order_req = PlaceTriggerOrderRequest(**res.req)

    assert (
        place_trigger_order_req.place_order.order.sender.lower() == senders[0].lower()
    )


def test_place_order_execute_success(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    product_id = 1
    place_trigger_order_params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=SubaccountParams(subaccount_name="default"),
            priceX18=1000,
            amount=1000,
            expiration=1000,
            nonce=1000,
            appendix=0,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(last_price_above=100)
            )
        ),
    )

    order = place_trigger_order_params.order.copy(deep=True)
    order.sender = hex_to_bytes32(senders[0])

    with pytest.raises(
        ValueError,
        match="Missing `product_id` to sign place_order execute",
    ):
        trigger_client._sign(NadoExecuteType.PLACE_ORDER, order.dict())

    expected_signature = trigger_client._sign(
        NadoExecuteType.PLACE_ORDER,
        order.dict(),
        product_id=place_trigger_order_params.product_id,
    )
    computed_signature = sign_eip712_typed_data(
        typed_data=build_eip712_typed_data(
            NadoExecuteType.PLACE_ORDER,
            order.dict(),
            gen_order_verifying_contract(product_id),
            trigger_client.chain_id,
        ),
        signer=trigger_client._opts.linked_signer,
    )

    assert expected_signature == computed_signature

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": expected_signature,
        "data": None,
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_trigger_order(place_trigger_order_params)
    place_trigger_order_req = PlaceTriggerOrderRequest(**res.req)

    assert (
        place_trigger_order_req.place_order.signature
        == res.signature
        == expected_signature
    )
    assert (
        place_trigger_order_req.place_order.order.sender.lower() == senders[0].lower()
    )
    assert res.status == "success"
    assert res.error is None
    assert res.data is None

    mock_response.status_code = 200
    json_response = {
        "status": "failure",
        "error_code": 1000,
        "error": "Too Many Requests!",
    }
    mock_response.json.return_value = json_response
    mock_post.return_value.text = json.dumps(json_response)

    with pytest.raises(ExecuteFailedException, match=json.dumps(json_response)):
        trigger_client.place_trigger_order(place_trigger_order_params)

    # deactivate linked signer
    trigger_client.linked_signer = None

    expected_signature = sign_eip712_typed_data(
        typed_data=build_eip712_typed_data(
            NadoExecuteType.PLACE_ORDER,
            order.dict(),
            gen_order_verifying_contract(product_id),
            trigger_client.chain_id,
        ),
        signer=trigger_client._opts.signer,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": expected_signature,
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_trigger_order(place_trigger_order_params)
    place_trigger_order_req = PlaceTriggerOrderRequest(**res.req)

    assert place_trigger_order_req.place_order.signature == expected_signature


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

    trigger_client = TriggerClient({"url": url})
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
    signature = trigger_client.sign(
        NadoExecuteType.PLACE_ORDER,
        order_params,
        gen_order_verifying_contract(product_id),
        chain_id,
        signer,
    )
    order_params["sender"] = bytes32_to_hex(order_params["sender"])
    res = trigger_client.place_trigger_order(
        {
            "product_id": product_id,
            "order": order_params,
            "signature": signature,
            "trigger": {
                "price_trigger": {"price_requirement": {"last_price_above": "100"}}
            },
        }
    )
    req = PlaceTriggerOrderRequest(**res.req)

    assert req.place_order.signature == signature
    assert req.place_order.order.amount == str(order_params["amount"])
    assert req.place_order.order.priceX18 == str(order_params["priceX18"])
    assert req.place_order.order.sender == order_params["sender"]
    assert req.place_order.order.nonce == str(order_params["nonce"])
    assert req.place_order.order.expiration == str(order_params["expiration"])
    assert req.place_order.order.appendix == str(order_params["appendix"])
    assert (
        req.place_order.trigger.price_trigger.price_requirement.last_price_above
        == "100"
    )


def test_place_trigger_order_with_basic_appendix(senders: list[str]):
    """Test placing trigger order with basic appendix functionality."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Test with IOC order type
    ioc_appendix = build_appendix(
        OrderType.IOC, trigger_type=OrderAppendixTriggerType.PRICE
    )
    params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-10000000000000000,
            expiration=4611687701117784255,
            appendix=ioc_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(
                    last_price_above="30000000000000000000000"
                )
            )
        ),
    )

    assert params.order.appendix == ioc_appendix

    # Test with reduce-only flag
    reduce_only_appendix = build_appendix(
        OrderType.POST_ONLY,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.PRICE,
    )
    params_reduce = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-10000000000000000,
            expiration=4611687701117784255,
            appendix=reduce_only_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="28000000000000000000000"
                )
            )
        ),
    )

    assert params_reduce.order.appendix == reduce_only_appendix


def test_place_trigger_order_with_price_trigger_appendix(senders: list[str]):
    """Test placing trigger order with price trigger appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # This creates a compound trigger: price-based trigger in the API + price-based trigger in appendix
    # This might be useful for complex trigger strategies
    trigger_appendix = build_appendix(
        OrderType.IOC, reduce_only=True, trigger_type=OrderAppendixTriggerType.PRICE
    )

    params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=-5000000000000000,  # Partial close
            expiration=4611687701117784255,
            appendix=trigger_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(
                    last_price_above="29000000000000000000000"
                )
            )
        ),
    )

    assert params.order.appendix == trigger_appendix


def test_place_trigger_order_with_isolated_position_appendix(senders: list[str]):
    """Test placing trigger order with isolated position appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])
    margin = 2000000  # 2M units margin

    isolated_appendix = build_appendix(
        OrderType.POST_ONLY,
        isolated=True,
        reduce_only=False,
        isolated_margin=margin,
        trigger_type=OrderAppendixTriggerType.PRICE,
    )

    params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=28898000000000000000000,
            amount=10000000000000000,  # Long position
            expiration=4611687701117784255,
            appendix=isolated_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="28000000000000000000000"
                )
            )
        ),  # Buy the dip
    )

    assert params.order.appendix == isolated_appendix


def test_place_trigger_order_appendix_combinations(senders: list[str]):
    """Test various valid appendix combinations with trigger orders."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Test all order types with reduce-only and price triggers
    order_types = [OrderType.DEFAULT, OrderType.IOC, OrderType.FOK, OrderType.POST_ONLY]

    for order_type in order_types:
        appendix = build_appendix(
            order_type, reduce_only=True, trigger_type=OrderAppendixTriggerType.PRICE
        )

        params = PlaceTriggerOrderParams(
            product_id=product_id,
            order=OrderParams(
                sender=sender,
                priceX18=28898000000000000000000,
                amount=-10000000000000000,
                expiration=4611687701117784255,
                appendix=appendix,
            ),
            trigger=PriceTrigger(
                price_trigger=PriceTriggerData(
                    price_requirement=LastPriceAbove(
                        last_price_above="29500000000000000000000"
                    )
                )
            ),
        )

        assert params.order.appendix == appendix

    # Test isolated position with different trigger types
    for trigger_price in ["27000000000000000000000", "31000000000000000000000"]:
        isolated_appendix = build_appendix(
            OrderType.DEFAULT,
            isolated=True,
            isolated_margin=to_x18(1500000),
            trigger_type=OrderAppendixTriggerType.PRICE,
        )

        trigger = (
            PriceTrigger(
                price_trigger=PriceTriggerData(
                    price_requirement=LastPriceBelow(last_price_below=trigger_price)
                )
            )
            if trigger_price.startswith("27")
            else PriceTrigger(
                price_trigger=PriceTriggerData(
                    price_requirement=LastPriceAbove(last_price_above=trigger_price)
                )
            )
        )

        params = PlaceTriggerOrderParams(
            product_id=product_id,
            order=OrderParams(
                sender=sender,
                priceX18=28898000000000000000000,
                amount=10000000000000000,
                expiration=4611687701117784255,
                appendix=isolated_appendix,
            ),
            trigger=trigger,
        )

        assert params.order.appendix == isolated_appendix


def test_place_trigger_order_complex_scenarios(senders: list[str]):
    """Test complex real-world scenarios with trigger orders and appendix."""
    product_id = 1
    sender = hex_to_bytes32(senders[0])

    # Scenario 1: Stop-loss with reduce-only
    stop_loss_appendix = build_appendix(
        OrderType.IOC,  # Execute immediately when triggered
        reduce_only=True,  # Only reduce position, don't increase
        trigger_type=OrderAppendixTriggerType.PRICE,
    )

    stop_loss_params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=27000000000000000000000,  # Lower than current price
            amount=-10000000000000000,  # Sell to close long
            expiration=4611687701117784255,
            appendix=stop_loss_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceBelow(
                    last_price_below="27500000000000000000000"
                )
            )
        ),  # Trigger below current
    )

    assert stop_loss_params.order.appendix == stop_loss_appendix

    # Scenario 2: Take-profit with post-only to avoid paying fees
    take_profit_appendix = build_appendix(
        OrderType.POST_ONLY,  # Only add liquidity
        reduce_only=True,  # Only reduce position
        trigger_type=OrderAppendixTriggerType.PRICE,
    )

    take_profit_params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=32000000000000000000000,  # Higher than current price
            amount=-10000000000000000,  # Sell to close long
            expiration=4611687701117784255,
            appendix=take_profit_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(
                    last_price_above="31500000000000000000000"
                )
            )
        ),  # Trigger above current
    )

    assert take_profit_params.order.appendix == take_profit_appendix

    # Scenario 3: Isolated position entry on breakout
    breakout_appendix = build_appendix(
        OrderType.IOC,  # Execute immediately on breakout
        isolated=True,
        isolated_margin=to_x18(5000000),  # 5M units of isolated margin
        trigger_type=OrderAppendixTriggerType.PRICE,
    )

    breakout_params = PlaceTriggerOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=sender,
            priceX18=31000000000000000000000,  # Above breakout level
            amount=15000000000000000,  # Larger position for breakout
            expiration=4611687701117784255,
            appendix=breakout_appendix,
        ),
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(
                    last_price_above="30500000000000000000000"
                )
            )
        ),  # Breakout trigger
    )

    assert breakout_params.order.appendix == breakout_appendix


def test_place_twap_order_entry_point(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test the place_twap_order convenience method."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
        "data": None,
    }
    mock_post.return_value = mock_response

    # Test basic TWAP order - using defaults for subaccount_owner and subaccount_name
    res = trigger_client.place_twap_order(
        product_id=1,
        price_x18="50000000000000000000000",  # $50,000
        total_amount_x18="1000000000000000000",  # 1 BTC
        times=5,
        slippage_frac=0.01,
        interval_seconds=300,
        expiration=1700000000,
        nonce=123456,
    )

    assert res.status == "success"
    assert res.signature == "test_signature"

    # Verify the request structure
    req_data = res.req
    assert req_data["place_order"]["product_id"] == 1
    assert req_data["place_order"]["order"]["amount"] == "1000000000000000000"
    assert "time_trigger" in req_data["place_order"]["trigger"]
    assert req_data["place_order"]["trigger"]["time_trigger"]["interval"] == 300
    # amounts is None, so it's not included in serialized JSON
    assert "amounts" not in req_data["place_order"]["trigger"]["time_trigger"]

    # Check that it's a TWAP trigger type in the appendix
    appendix = int(req_data["place_order"]["order"]["appendix"])
    trigger_type = order_trigger_type(appendix)
    assert trigger_type == OrderAppendixTriggerType.TWAP

    # Check execution type is IOC
    execution_type = order_execution_type(appendix)
    assert execution_type == OrderType.IOC

    # Check TWAP data encoding
    times, slippage = order_twap_data(appendix)
    assert times == 5
    assert abs(slippage - 0.01) < 1e-6


def test_place_twap_order_with_custom_amounts(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test TWAP order with custom amounts."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    custom_amounts_x18 = [
        "400000000000000000",
        "300000000000000000",
        "300000000000000000",
    ]
    total_amount_x18 = "1000000000000000000"

    res = trigger_client.place_twap_order(
        product_id=2,
        price_x18="25000000000000000000000",
        total_amount_x18=total_amount_x18,
        times=3,
        slippage_frac=0.005,
        interval_seconds=600,
        custom_amounts_x18=custom_amounts_x18,
        expiration=1700000000,
        nonce=789012,
    )

    assert res.status == "success"

    # Verify custom amounts are included
    req_data = res.req
    assert "time_trigger" in req_data["place_order"]["trigger"]
    assert (
        req_data["place_order"]["trigger"]["time_trigger"]["amounts"]
        == custom_amounts_x18
    )

    # Check that it's a TWAP_CUSTOM_AMOUNTS trigger type
    appendix = int(req_data["place_order"]["order"]["appendix"])
    trigger_type = order_trigger_type(appendix)
    assert trigger_type == OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS


def test_place_twap_order_with_reduce_only(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test TWAP order with reduce_only flag."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_twap_order(
        product_id=1,
        price_x18="48000000000000000000000",
        total_amount_x18="-500000000000000000",  # Sell order
        times=2,
        slippage_frac=0.01,
        interval_seconds=300,
        reduce_only=True,
        expiration=1700000000,
        nonce=123456,
    )

    assert res.status == "success"

    # Verify reduce_only is encoded in appendix
    req_data = res.req
    appendix = int(req_data["place_order"]["order"]["appendix"])

    from nado_protocol.utils.order import order_reduce_only

    assert order_reduce_only(appendix) is True


def test_place_price_trigger_order_entry_point(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test the place_price_trigger_order convenience method."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
        "data": None,
    }
    mock_post.return_value = mock_response

    # Test last_price_above trigger - using defaults
    res = trigger_client.place_price_trigger_order(
        product_id=1,
        price_x18="52000000000000000000000",  # $52,000 limit price
        amount_x18="500000000000000000",  # 0.5 BTC
        trigger_price_x18="51000000000000000000000",  # $51,000 trigger price
        trigger_type="last_price_above",
        expiration=1700000000,
        nonce=123456,
    )

    assert res.status == "success"
    assert res.signature == "test_signature"

    # Verify the request structure
    req_data = res.req
    assert req_data["place_order"]["product_id"] == 1
    assert req_data["place_order"]["order"]["amount"] == "500000000000000000"
    assert req_data["place_order"]["order"]["priceX18"] == "52000000000000000000000"

    # Check trigger structure
    trigger = req_data["place_order"]["trigger"]
    assert "price_trigger" in trigger
    assert "price_requirement" in trigger["price_trigger"]
    assert "last_price_above" in trigger["price_trigger"]["price_requirement"]
    assert (
        trigger["price_trigger"]["price_requirement"]["last_price_above"]
        == "51000000000000000000000"
    )


def test_place_price_trigger_order_all_trigger_types(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test all supported price trigger types."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    trigger_types = [
        "last_price_above",
        "last_price_below",
        "oracle_price_above",
        "oracle_price_below",
        "mid_price_above",
        "mid_price_below",
    ]

    for trigger_type in trigger_types:
        res = trigger_client.place_price_trigger_order(
            product_id=1,
            sender=senders[0],
            price_x18="50000000000000000000000",
            amount_x18="1000000000000000000",
            expiration=1700000000,
            nonce=123456 + hash(trigger_type) % 1000000,  # Unique nonce
            trigger_price_x18="49000000000000000000000",
            trigger_type=trigger_type,
        )

        assert res.status == "success"

        # Verify correct trigger type is used
        req_data = res.req
        trigger = req_data["place_order"]["trigger"]
        assert "price_trigger" in trigger
        assert "price_requirement" in trigger["price_trigger"]
        assert (
            trigger_type.replace("_price_", "_price_")
            in trigger["price_trigger"]["price_requirement"]
        )


def test_place_price_trigger_order_with_reduce_only(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test price trigger order with reduce_only flag."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="48000000000000000000000",
        amount_x18="-2000000000000000000",  # Sell 2 BTC
        expiration=1700000000,
        nonce=123456,
        trigger_price_x18="47000000000000000000000",
        trigger_type="last_price_below",
        reduce_only=True,
    )

    assert res.status == "success"

    # Verify reduce_only is handled (would be encoded in appendix during order preparation)
    req_data = res.req
    assert req_data["place_order"]["order"]["amount"] == "-2000000000000000000"


def test_place_price_trigger_order_with_spot_leverage(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test price trigger order with spot_leverage option."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        amount_x18="1000000000000000000",
        expiration=1700000000,
        nonce=123456,
        trigger_price_x18="51000000000000000000000",
        trigger_type="last_price_above",
        spot_leverage=True,
    )

    assert res.status == "success"

    # Verify spot_leverage is included in the request
    req_data = res.req
    assert req_data["place_order"]["spot_leverage"] is True


def test_place_price_trigger_order_invalid_trigger_type(
    trigger_client: TriggerClient, senders: list[str]
):
    """Test error handling for invalid trigger types."""
    with pytest.raises(ValueError, match="Unsupported trigger_type"):
        trigger_client.place_price_trigger_order(
            product_id=1,
            sender=senders[0],
            price_x18="50000000000000000000000",
            amount_x18="1000000000000000000",
            expiration=1700000000,
            nonce=123456,
            trigger_price_x18="51000000000000000000000",
            trigger_type="invalid_trigger_type",
        )


def test_place_twap_order_validation_errors(
    trigger_client: TriggerClient, senders: list[str]
):
    """Test TWAP order validation errors through entry point."""
    # Test times out of range
    with pytest.raises(ValueError, match="must be between 1 and 500"):
        trigger_client.place_twap_order(
            product_id=1,
            sender=senders[0],
            price_x18="50000000000000000000000",
            total_amount_x18="1000000000000000000",
            expiration=1700000000,
            nonce=123456,
            times=501,  # Invalid: too high
            slippage_frac=0.01,
            interval_seconds=300,
        )

    # Test invalid slippage
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        trigger_client.place_twap_order(
            product_id=1,
            sender=senders[0],
            price_x18="50000000000000000000000",
            total_amount_x18="1000000000000000000",
            expiration=1700000000,
            nonce=123456,
            times=5,
            slippage_frac=1.5,  # Invalid: too high
            interval_seconds=300,
        )

    # Test invalid interval
    with pytest.raises(ValueError, match="must be positive"):
        trigger_client.place_twap_order(
            product_id=1,
            sender=senders[0],
            price_x18="50000000000000000000000",
            total_amount_x18="1000000000000000000",
            expiration=1700000000,
            nonce=123456,
            times=5,
            slippage_frac=0.01,
            interval_seconds=0,  # Invalid: not positive
        )


def test_entry_points_integration_flow(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test realistic integration scenario using entry points."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    # Scenario: Set up stop-loss and take-profit, then DCA with TWAP

    # 1. Stop-loss order using price trigger
    stop_loss_res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="45000000000000000000000",  # Sell at $45k
        amount_x18="-1000000000000000000",  # Close 1 BTC position
        expiration=1700000000,
        nonce=123001,
        trigger_price_x18="46000000000000000000000",  # Trigger below $46k
        trigger_type="last_price_below",
        reduce_only=True,
    )
    assert stop_loss_res.status == "success"

    # 2. Take-profit order using price trigger
    take_profit_res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="55000000000000000000000",  # Sell at $55k
        amount_x18="-1000000000000000000",  # Close 1 BTC position
        expiration=1700000000,
        nonce=123002,
        trigger_price_x18="54000000000000000000000",  # Trigger above $54k
        trigger_type="last_price_above",
        reduce_only=True,
    )
    assert take_profit_res.status == "success"

    # 3. DCA using TWAP order
    dca_res = trigger_client.place_twap_order(
        product_id=1,
        sender=senders[0],
        price_x18="52000000000000000000000",  # Max $52k per execution
        total_amount_x18="5000000000000000000",  # Buy 5 BTC total
        expiration=1700000000,
        nonce=123003,
        times=10,  # Split into 10 executions
        slippage_frac=0.005,  # 0.5% slippage tolerance
        interval_seconds=3600,  # 1 hour intervals
    )
    assert dca_res.status == "success"

    # Verify all orders were placed successfully
    assert mock_post.call_count == 3


def test_place_price_trigger_order_appendix_validation(
    trigger_client: TriggerClient, mock_post: MagicMock, senders: list[str]
):
    """Test that place_price_trigger_order correctly builds the appendix with PRICE trigger type."""
    from nado_protocol.utils.order import (
        order_trigger_type,
        order_reduce_only,
        order_execution_type,
        OrderAppendixTriggerType,
    )
    from nado_protocol.utils.expiration import OrderType

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "signature": "test_signature",
    }
    mock_post.return_value = mock_response

    # Test with DEFAULT order type and reduce_only=False
    res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        amount_x18="1000000000000000000",
        expiration=1700000000,
        nonce=123456,
        trigger_price_x18="51000000000000000000000",
        trigger_type="last_price_above",
        reduce_only=False,
        order_type=OrderType.DEFAULT,
    )

    # Extract the appendix from the request
    req_data = res.req
    appendix = int(req_data["place_order"]["order"]["appendix"])

    # Validate trigger type is PRICE
    assert order_trigger_type(appendix) == OrderAppendixTriggerType.PRICE
    assert order_execution_type(appendix) == OrderType.DEFAULT
    assert order_reduce_only(appendix) is False

    # Test with IOC order type and reduce_only=True
    res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        amount_x18="-1000000000000000000",
        expiration=1700000000,
        nonce=123457,
        trigger_price_x18="45000000000000000000000",
        trigger_type="last_price_below",
        reduce_only=True,
        order_type=OrderType.IOC,
    )

    req_data = res.req
    appendix = int(req_data["place_order"]["order"]["appendix"])

    assert order_trigger_type(appendix) == OrderAppendixTriggerType.PRICE
    assert order_execution_type(appendix) == OrderType.IOC
    assert order_reduce_only(appendix) is True

    # Test with POST_ONLY order type
    res = trigger_client.place_price_trigger_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        amount_x18="1000000000000000000",
        expiration=1700000000,
        nonce=123458,
        trigger_price_x18="49000000000000000000000",
        trigger_type="oracle_price_below",
        order_type=OrderType.POST_ONLY,
    )

    req_data = res.req
    appendix = int(req_data["place_order"]["order"]["appendix"])

    assert order_trigger_type(appendix) == OrderAppendixTriggerType.PRICE
    assert order_execution_type(appendix) == OrderType.POST_ONLY
