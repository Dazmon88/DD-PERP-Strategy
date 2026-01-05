from nado_protocol.trigger_client.types.execute import (
    CancelTriggerOrdersParams,
    CancelTriggerOrdersRequest,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_cancel_trigger_orders_params(senders: list[str]):
    product_ids = [4]
    digests = ["0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"]
    sender = hex_to_bytes32(senders[0])
    params_from_dict = CancelTriggerOrdersParams(
        **{"productIds": product_ids, "sender": sender, "digests": digests}
    )
    params_from_obj = CancelTriggerOrdersParams(
        sender=senders[0],
        productIds=product_ids,
        digests=digests,
    )
    bytes32_digests = CancelTriggerOrdersParams(
        sender=sender,
        productIds=product_ids,
        digests=[hex_to_bytes32(digest) for digest in digests],
    )
    assert params_from_dict == params_from_obj == bytes32_digests
    params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    params_from_dict.nonce = 100000
    request_from_params = CancelTriggerOrdersRequest(cancel_orders=params_from_dict)
    assert request_from_params.dict() == {
        "cancel_orders": {
            "tx": {
                "productIds": product_ids,
                "digests": digests,
                "sender": senders[0].lower(),
                "nonce": str(params_from_dict.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }
