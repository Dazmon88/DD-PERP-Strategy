from nado_protocol.engine_client.types.execute import (
    LinkSignerParams,
    LinkSignerRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_link_signer_params(senders: list[str], owners: list[str]):
    sender = senders[0]
    signer = senders[1]
    params_from_dict = LinkSignerParams(
        **{
            "sender": sender,
            "signer": signer,
        }
    )
    params_from_obj = LinkSignerParams(sender=sender, signer=signer)
    bytes32_sender = LinkSignerParams(
        sender=hex_to_bytes32(sender),
        signer=hex_to_bytes32(signer),
    )
    subaccount_params_sender = LinkSignerParams(
        sender={"subaccount_owner": owners[0], "subaccount_name": "default"},
        signer={"subaccount_owner": owners[1], "subaccount_name": "default"},
    )

    assert (
        params_from_dict
        == params_from_obj
        == bytes32_sender
        == subaccount_params_sender
    )
    params_from_dict.signature = (
        "0x51ba8762bc5f77957a4e896dba34e17b553b872c618ffb83dba54878796f2821"
    )
    params_from_dict.nonce = 100000
    req_from_params = LinkSignerRequest(link_signer=params_from_dict)
    assert req_from_params == to_execute_request(params_from_dict)
    assert req_from_params.dict() == {
        "link_signer": {
            "tx": {
                "sender": sender.lower(),
                "signer": signer.lower(),
                "nonce": str(params_from_dict.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }
