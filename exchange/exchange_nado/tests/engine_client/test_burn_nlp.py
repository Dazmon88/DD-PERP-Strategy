from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    BurnNlpRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_burn_nlp_params(senders: list[str], owners: list[str], burn_nlp_params: dict):
    sender = senders[0]
    nlp_amount = burn_nlp_params["nlpAmount"]
    params_from_dict = BurnNlpParams(**{"sender": sender, "nlpAmount": nlp_amount})
    params_from_obj = BurnNlpParams(
        sender=sender,
        nlpAmount=nlp_amount,
    )
    bytes32_sender = BurnNlpParams(sender=hex_to_bytes32(sender), nlpAmount=nlp_amount)
    subaccount_params_sender = BurnNlpParams(
        sender={"subaccount_owner": owners[0], "subaccount_name": "default"},
        nlpAmount=nlp_amount,
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
    req_from_params = BurnNlpRequest(burn_nlp=params_from_dict)
    assert req_from_params == to_execute_request(params_from_dict)
    assert req_from_params.dict() == {
        "burn_nlp": {
            "tx": {
                "sender": sender.lower(),
                "nlpAmount": str(nlp_amount),
                "nonce": str(params_from_dict.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }
