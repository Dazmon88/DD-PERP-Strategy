from nado_protocol.engine_client.types.execute import (
    CancelOrdersParams,
    CancelOrdersRequest,
    CancelAndPlaceParams,
    CancelAndPlaceRequest,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32
from nado_protocol.engine_client.types.execute import (
    OrderParams,
    PlaceOrderParams,
    PlaceOrderRequest,
    to_execute_request,
)
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.subaccount import SubaccountParams


def test_cancel_and_place_params(
    senders: list[str], owners: list[str], order_params: dict
):
    product_ids = [4]
    digests = ["0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"]
    sender = hex_to_bytes32(senders[0])
    cancel_params_from_dict = CancelOrdersParams(
        **{"productIds": product_ids, "sender": sender, "digests": digests}
    )
    cancel_params_from_obj = CancelOrdersParams(
        sender=senders[0],
        productIds=product_ids,
        digests=digests,
    )
    cancel_bytes32_digests = CancelOrdersParams(
        sender=sender,
        productIds=product_ids,
        digests=[hex_to_bytes32(digest) for digest in digests],
    )
    assert cancel_params_from_dict == cancel_params_from_obj == cancel_bytes32_digests
    cancel_params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    cancel_params_from_dict.nonce = 100000

    product_id = 1
    sender = hex_to_bytes32(senders[0])
    place_params_from_dict = PlaceOrderParams(
        **{
            "product_id": product_id,
            "order": {
                "sender": senders[0],
                "priceX18": order_params["priceX18"],
                "amount": order_params["amount"],
                "expiration": order_params["expiration"],
                "appendix": order_params["appendix"],
            },
        }
    )
    place_params_from_obj = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=senders[0],
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
    )
    place_bytes32_sender = PlaceOrderParams(
        product_id=product_id,
        order=OrderParams(
            sender=hex_to_bytes32(senders[0]),
            priceX18=order_params["priceX18"],
            amount=order_params["amount"],
            expiration=order_params["expiration"],
            appendix=order_params["appendix"],
        ),
    )
    place_subaccount_params_sender = PlaceOrderParams(
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
        place_params_from_dict
        == place_params_from_obj
        == place_bytes32_sender
        == place_subaccount_params_sender
    )

    assert place_params_from_dict.product_id == product_id
    assert place_params_from_dict.order.sender == sender
    assert place_params_from_dict.order.amount == order_params["amount"]
    assert place_params_from_dict.order.priceX18 == order_params["priceX18"]
    assert place_params_from_dict.order.expiration == order_params["expiration"]
    assert place_params_from_dict.order.appendix == order_params["appendix"]
    assert place_params_from_dict.signature is None

    place_params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    place_params_from_dict.order.nonce = gen_order_nonce()
    place_order_req = PlaceOrderRequest(place_order=place_params_from_dict)
    assert place_order_req == to_execute_request(place_params_from_dict)

    cancel_and_place_params = CancelAndPlaceParams(
        cancel_orders=cancel_params_from_dict, place_order=place_params_from_dict
    )
    cancel_and_place_req = CancelAndPlaceRequest(
        cancel_and_place=cancel_and_place_params
    )
    assert cancel_and_place_req.dict() == {
        "cancel_and_place": {
            "cancel_tx": {
                "productIds": product_ids,
                "digests": digests,
                "sender": senders[0].lower(),
                "nonce": str(cancel_params_from_dict.nonce),
            },
            "cancel_signature": cancel_params_from_dict.signature,
            "place_order": {
                "product_id": product_id,
                "order": {
                    "sender": senders[0].lower(),
                    "priceX18": str(order_params["priceX18"]),
                    "amount": str(order_params["amount"]),
                    "expiration": str(order_params["expiration"]),
                    "appendix": str(order_params["appendix"]),
                    "nonce": str(place_params_from_dict.order.nonce),
                },
                "signature": place_params_from_dict.signature,
            },
        }
    }
