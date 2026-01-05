from unittest.mock import MagicMock

from nado_protocol.client import NadoClient
from nado_protocol.contracts.types import NadoExecuteType

from nado_protocol.engine_client.types.execute import (
    WithdrawCollateralParams,
)
from nado_protocol.utils.bytes32 import subaccount_to_bytes32


def test_withdraw(
    nado_client: NadoClient,
    senders: list[str],
    mock_execute_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    params = WithdrawCollateralParams(
        sender=senders[0],
        productId=1,
        amount=10,
        nonce=2,
    )
    res = nado_client.spot.withdraw(params)
    params.sender = subaccount_to_bytes32(senders[0])
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.WITHDRAW_COLLATERAL,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.req == {
        "withdraw_collateral": {
            "tx": {
                "sender": senders[0].lower(),
                "productId": 1,
                "amount": str(10),
                "nonce": str(2),
            },
            "signature": signature,
        }
    }
