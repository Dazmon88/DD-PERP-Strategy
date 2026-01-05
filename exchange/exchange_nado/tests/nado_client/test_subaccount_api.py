from unittest.mock import MagicMock

from nado_protocol.client import NadoClient
from nado_protocol.contracts.types import NadoExecuteType

from nado_protocol.engine_client.types.execute import (
    LinkSignerParams,
    LiquidateSubaccountParams,
)
from nado_protocol.utils.bytes32 import subaccount_to_bytes32


def test_liquidate_subaccount(
    nado_client: NadoClient,
    senders: list[str],
    mock_execute_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    params = LiquidateSubaccountParams(
        sender=senders[0],
        liquidatee=senders[1],
        productId=1,
        isEncodedSpread=False,
        amount=10,
        nonce=2,
    )
    res = nado_client.subaccount.liquidate_subaccount(params)
    params.sender = subaccount_to_bytes32(senders[0])
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.LIQUIDATE_SUBACCOUNT,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.req == {
        "liquidate_subaccount": {
            "tx": {
                "sender": senders[0].lower(),
                "liquidatee": senders[1].lower(),
                "productId": 1,
                "isEncodedSpread": False,
                "amount": str(10),
                "nonce": str(2),
            },
            "signature": signature,
        }
    }


def test_link_signer(
    nado_client: NadoClient,
    senders: list[str],
    mock_execute_response: MagicMock,
    mock_tx_nonce: MagicMock,
):
    params = LinkSignerParams(
        sender=senders[0],
        signer=senders[1],
        nonce=2,
    )
    res = nado_client.subaccount.link_signer(params)
    params.sender = subaccount_to_bytes32(senders[0])
    signature = nado_client.context.engine_client.sign(
        NadoExecuteType.LINK_SIGNER,
        params.dict(),
        nado_client.context.engine_client.endpoint_addr,
        nado_client.context.engine_client.chain_id,
        nado_client.context.engine_client.signer,
    )
    assert res.req == {
        "link_signer": {
            "tx": {
                "sender": senders[0].lower(),
                "signer": senders[1].lower(),
                "nonce": str(2),
            },
            "signature": signature,
        }
    }
