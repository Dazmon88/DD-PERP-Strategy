from nado_protocol.engine_client.types.execute import (
    MintNlpParams,
    MintNlpRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_mint_nlp_params(senders: list[str], owners: list[str], mint_nlp_params: dict):
    sender = senders[0]
    quote_amount = mint_nlp_params["quoteAmount"]
    params_from_dict = MintNlpParams(
        **{
            "sender": sender,
            "quoteAmount": quote_amount,
        }
    )
    params_from_obj = MintNlpParams(
        sender=sender,
        quoteAmount=quote_amount,
    )
    bytes32_sender = MintNlpParams(
        sender=hex_to_bytes32(sender),
        quoteAmount=quote_amount,
    )
    subaccount_params_sender = MintNlpParams(
        sender={"subaccount_owner": owners[0], "subaccount_name": "default"},
        quoteAmount=quote_amount,
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
    req_from_params = MintNlpRequest(mint_nlp=params_from_dict)
    assert req_from_params == to_execute_request(params_from_dict)
    assert req_from_params.dict() == {
        "mint_nlp": {
            "tx": {
                "sender": sender.lower(),
                "quoteAmount": str(quote_amount),
                "nonce": str(params_from_dict.nonce),
            },
            "signature": params_from_dict.signature,
        }
    }
