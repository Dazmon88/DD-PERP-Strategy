from eth_account import Account
from nado_protocol.trigger_client import TriggerClient
import pytest


def test_execute_client_properties(
    url: str,
    chain_id: int,
    endpoint_addr: str,
    private_keys: list[str],
):
    trigger_client = TriggerClient(opts={"url": url})
    with pytest.raises(AttributeError, match="Endpoint address not set"):
        trigger_client.endpoint_addr

    with pytest.raises(AttributeError, match="Chain ID is not set"):
        trigger_client.chain_id

    with pytest.raises(AttributeError, match="Signer is not set"):
        trigger_client.signer

    with pytest.raises(AttributeError, match="Signer is not set"):
        trigger_client.linked_signer

    trigger_client.endpoint_addr = endpoint_addr
    trigger_client.chain_id = chain_id

    signer = Account.from_key(private_keys[0])
    linked_signer = Account.from_key(private_keys[1])

    assert signer != linked_signer

    with pytest.raises(
        AttributeError,
        match="Must set a `signer` first before setting `linked_signer`.",
    ):
        trigger_client.linked_signer = linked_signer

    trigger_client.signer = signer

    assert trigger_client.signer == trigger_client.linked_signer

    trigger_client.linked_signer = linked_signer

    assert trigger_client.endpoint_addr == endpoint_addr
    assert trigger_client.chain_id == chain_id
    assert trigger_client.signer == signer
    assert trigger_client.linked_signer == linked_signer

    trigger_client.linked_signer = None

    assert trigger_client.linked_signer == trigger_client.signer
