from eth_account import Account
from nado_protocol.engine_client import EngineClient
import pytest


def test_execute_client_properties(
    url: str,
    chain_id: int,
    endpoint_addr: str,
    private_keys: list[str],
):
    engine_client = EngineClient(opts={"url": url})
    with pytest.raises(AttributeError, match="Endpoint address not set"):
        engine_client.endpoint_addr

    with pytest.raises(AttributeError, match="Chain ID is not set"):
        engine_client.chain_id

    with pytest.raises(AttributeError, match="Signer is not set"):
        engine_client.signer

    with pytest.raises(AttributeError, match="Signer is not set"):
        engine_client.linked_signer

    engine_client.endpoint_addr = endpoint_addr
    engine_client.chain_id = chain_id

    signer = Account.from_key(private_keys[0])
    linked_signer = Account.from_key(private_keys[1])

    assert signer != linked_signer

    with pytest.raises(
        AttributeError,
        match="Must set a `signer` first before setting `linked_signer`.",
    ):
        engine_client.linked_signer = linked_signer

    engine_client.signer = signer

    assert engine_client.signer == engine_client.linked_signer

    engine_client.linked_signer = linked_signer

    assert engine_client.endpoint_addr == endpoint_addr
    assert engine_client.chain_id == chain_id
    assert engine_client.signer == signer
    assert engine_client.linked_signer == linked_signer

    engine_client.linked_signer = None

    assert engine_client.linked_signer == engine_client.signer
