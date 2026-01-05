from nado_protocol.engine_client.types.execute import (
    WithdrawCollateralParams,
    WithdrawCollateralRequest,
    to_execute_request,
)
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_withdraw_collateral_params(senders: list[str], owners: list[str]):
    product_id = 1
    amount = 10000
    sender = senders[0]
    params_from_dict = WithdrawCollateralParams(
        **{
            "sender": sender,
            "productId": product_id,
            "amount": amount,
            "spot_leverage": False,
        }
    )
    params_from_obj = WithdrawCollateralParams(
        sender=sender, productId=product_id, amount=amount, spot_leverage=False
    )
    bytes32_sender = WithdrawCollateralParams(
        sender=hex_to_bytes32(sender),
        productId=product_id,
        amount=amount,
        spot_leverage=False,
    )
    subaccount_params_sender = WithdrawCollateralParams(
        sender={"subaccount_owner": owners[0], "subaccount_name": "default"},
        productId=product_id,
        amount=amount,
        spot_leverage=False,
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
    req_from_params = WithdrawCollateralRequest(withdraw_collateral=params_from_dict)
    assert req_from_params == to_execute_request(params_from_dict)
    assert req_from_params.dict() == {
        "withdraw_collateral": {
            "tx": {
                "sender": sender.lower(),
                "productId": product_id,
                "amount": str(amount),
                "nonce": str(params_from_dict.nonce),
            },
            "spot_leverage": False,
            "signature": params_from_dict.signature,
        }
    }
