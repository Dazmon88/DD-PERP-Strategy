from eth_account import Account
from nado_protocol.engine_client import EngineClient, EngineClientOpts
from eth_account.signers.local import LocalAccount
from pydantic import ValidationError
import pytest


def test_create_client_url_validation():
    with pytest.raises(ValidationError):
        _ = EngineClient({"url": "invalid_url"})

    ws_url = "ws://example.com"
    ws_client = EngineClient({"url": ws_url})
    assert ws_client.url == ws_url

    http_url = "http://example.com"
    http_client = EngineClient({"url": http_url})
    assert http_client.url == http_url

    opts = EngineClientOpts(url=http_url)
    engine_client = EngineClient(opts)

    assert engine_client.url == http_url


def test_create_client_signer_validation(url: str, private_keys: list[str]):
    opts_signer_from_private_key = EngineClientOpts(url=url, signer=private_keys[0])
    assert isinstance(opts_signer_from_private_key.signer, LocalAccount)
    assert opts_signer_from_private_key.signer.key.hex() == private_keys[0]
    assert opts_signer_from_private_key.linked_signer is None

    with pytest.raises(
        ValidationError, match="linked_signer cannot be set if signer is not set"
    ):
        EngineClientOpts(url=url, linked_signer=private_keys[1])

    signer = Account.from_key(private_keys[0])
    opts_linked_signer_from_private_key = EngineClientOpts(
        url=url, linked_signer=private_keys[1], signer=signer
    )
    assert isinstance(opts_linked_signer_from_private_key.linked_signer, LocalAccount)
    assert (
        opts_linked_signer_from_private_key.linked_signer.key.hex() == private_keys[1]
    )
    assert opts_linked_signer_from_private_key.signer is not None

    opts_signer_from_account = EngineClientOpts(url=url, signer=signer)
    assert isinstance(opts_signer_from_account.signer, LocalAccount)
    assert opts_signer_from_account.signer.key.hex() == private_keys[0]

    linked_signer = Account.from_key(private_keys[1])
    opts_linked_signer_from_account = EngineClientOpts(
        url=url, signer=signer, linked_signer=linked_signer
    )
    assert isinstance(opts_linked_signer_from_account.linked_signer, LocalAccount)
    assert opts_linked_signer_from_account.linked_signer.key.hex() == private_keys[1]


def test_create_client_all_opts(
    url: str,
    private_keys: list[str],
    chain_id: int,
    endpoint_addr: str,
):
    client_from_dict = EngineClient(
        {
            "url": url,
            "signer": private_keys[0],
            "linked_signer": private_keys[1],
            "chain_id": chain_id,
            "endpoint_addr": endpoint_addr,
        }
    )
    client_from_opts = EngineClient(
        opts=EngineClientOpts(
            url=url,
            signer=private_keys[0],
            linked_signer=private_keys[1],
            chain_id=chain_id,
            endpoint_addr=endpoint_addr,
        )
    )

    assert (
        client_from_dict.signer
        == client_from_opts.signer
        == Account.from_key(private_keys[0])
    )
    assert (
        client_from_dict.linked_signer
        == client_from_opts.linked_signer
        == Account.from_key(private_keys[1])
    )
    assert client_from_dict.chain_id == client_from_opts.chain_id == chain_id
    assert (
        client_from_dict.endpoint_addr
        == client_from_opts.endpoint_addr
        == endpoint_addr
    )
