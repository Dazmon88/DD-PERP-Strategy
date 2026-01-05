from eth_account import Account
from nado_protocol.trigger_client import TriggerClient, TriggerClientOpts
from eth_account.signers.local import LocalAccount
from pydantic import ValidationError
import pytest


def test_create_client_url_validation():
    with pytest.raises(ValidationError):
        _ = TriggerClient({"url": "invalid_url"})

    ws_url = "ws://example.com"
    ws_client = TriggerClient({"url": ws_url})
    assert ws_client.url == ws_url

    http_url = "http://example.com"
    http_client = TriggerClient({"url": http_url})
    assert http_client.url == http_url

    opts = TriggerClientOpts(url=http_url)
    trigger_client = TriggerClient(opts)

    assert trigger_client.url == http_url


def test_create_client_signer_validation(url: str, private_keys: list[str]):
    opts_signer_from_private_key = TriggerClientOpts(url=url, signer=private_keys[0])
    assert isinstance(opts_signer_from_private_key.signer, LocalAccount)
    assert opts_signer_from_private_key.signer.key.hex() == private_keys[0]
    assert opts_signer_from_private_key.linked_signer is None

    with pytest.raises(
        ValidationError, match="linked_signer cannot be set if signer is not set"
    ):
        TriggerClientOpts(url=url, linked_signer=private_keys[1])

    signer = Account.from_key(private_keys[0])
    opts_linked_signer_from_private_key = TriggerClientOpts(
        url=url, linked_signer=private_keys[1], signer=signer
    )
    assert isinstance(opts_linked_signer_from_private_key.linked_signer, LocalAccount)
    assert (
        opts_linked_signer_from_private_key.linked_signer.key.hex() == private_keys[1]
    )
    assert opts_linked_signer_from_private_key.signer is not None

    opts_signer_from_account = TriggerClientOpts(url=url, signer=signer)
    assert isinstance(opts_signer_from_account.signer, LocalAccount)
    assert opts_signer_from_account.signer.key.hex() == private_keys[0]

    linked_signer = Account.from_key(private_keys[1])
    opts_linked_signer_from_account = TriggerClientOpts(
        url=url, signer=signer, linked_signer=linked_signer
    )
    assert isinstance(opts_linked_signer_from_account.linked_signer, LocalAccount)
    assert opts_linked_signer_from_account.linked_signer.key.hex() == private_keys[1]


def test_create_client_all_opts(
    url: str, private_keys: list[str], chain_id: int, endpoint_addr: str
):
    client_from_dict = TriggerClient(
        {
            "url": url,
            "signer": private_keys[0],
            "linked_signer": private_keys[1],
            "chain_id": chain_id,
            "endpoint_addr": endpoint_addr,
        }
    )
    client_from_opts = TriggerClient(
        opts=TriggerClientOpts(
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
