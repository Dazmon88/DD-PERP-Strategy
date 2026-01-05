from nado_protocol.engine_client.types.execute import (
    CancelProductOrdersParams,
    CancelProductOrdersRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_cancel_product_orders_params(senders: list[str]):
    product_ids = [4]
    digest = "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    sender = senders[0]
    params_from_dict = CancelProductOrdersParams(
        **{
            "sender": sender,
            "productIds": product_ids,
        }
    )
    params_from_obj = CancelProductOrdersParams(sender=sender, productIds=product_ids)
    bytes32_sender = CancelProductOrdersParams(
        sender=hex_to_bytes32(sender), productIds=product_ids
    )

    assert params_from_dict == params_from_obj == bytes32_sender
    params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    params_from_dict.nonce = 100000
    params_from_dict.digest = digest
    req_from_params = CancelProductOrdersRequest(cancel_product_orders=params_from_dict)
    assert req_from_params == to_execute_request(params_from_dict)
    assert req_from_params.dict() == {
        "cancel_product_orders": {
            "tx": {
                "sender": sender.lower(),
                "productIds": product_ids,
                "nonce": str(params_from_dict.nonce),
            },
            "digest": params_from_dict.digest,
            "signature": params_from_dict.signature,
        }
    }
