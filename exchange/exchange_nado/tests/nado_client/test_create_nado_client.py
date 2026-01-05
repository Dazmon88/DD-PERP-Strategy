from unittest.mock import MagicMock

from eth_account import Account
from nado_protocol.client import NadoClientMode, create_nado_client

from nado_protocol.client.context import (
    NadoClientContextOpts,
    create_nado_client_context,
)
import pytest
from nado_protocol.contracts import NadoContractsContext

from nado_protocol.utils.backend import NadoBackendURL


def test_create_nado_client_context(
    mock_post: MagicMock,
    mock_web3: MagicMock,
    mock_load_abi: MagicMock,
    private_keys: list[str],
    url: str,
    endpoint_addr: str,
    querier_addr: str,
    chain_id: int,
):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "data": {
            "endpoint_addr": endpoint_addr,
            "chain_id": chain_id,
        },
    }
    mock_post.return_value = mock_response

    full_engine_client_setup = create_nado_client_context(
        NadoClientContextOpts(
            engine_endpoint_url=url,
            indexer_endpoint_url=url,
            rpc_node_url=url,
            contracts_context=NadoContractsContext(
                endpoint_addr=endpoint_addr, querier_addr=querier_addr
            ),
        ),
        signer=private_keys[0],
    )

    assert full_engine_client_setup.engine_client.chain_id == chain_id
    assert full_engine_client_setup.engine_client.endpoint_addr == endpoint_addr
    assert (
        full_engine_client_setup.engine_client.signer.address
        == Account.from_key(private_keys[0]).address
    )
    assert (
        full_engine_client_setup.engine_client.url
        == full_engine_client_setup.indexer_client.url
        == url
    )

    mock_response.status_code = 400
    mock_response.json.return_value = {
        "status": "failure",
        "data": "invalid request",
    }
    mock_post.return_value = mock_response

    partial_engine_client_setup = create_nado_client_context(
        NadoClientContextOpts(
            engine_endpoint_url=url,
            indexer_endpoint_url=url,
            rpc_node_url=url,
            contracts_context=NadoContractsContext(
                endpoint_addr=endpoint_addr, querier_addr=querier_addr
            ),
        ),
        private_keys[0],
    )

    with pytest.raises(AttributeError, match="Endpoint address not set."):
        partial_engine_client_setup.engine_client.endpoint_addr

    with pytest.raises(AttributeError, match="Chain ID is not set."):
        partial_engine_client_setup.engine_client.chain_id

    assert (
        partial_engine_client_setup.engine_client.signer.address
        == Account.from_key(private_keys[0]).address
    )
    assert (
        partial_engine_client_setup.engine_client.url
        == partial_engine_client_setup.indexer_client.url
        == url
    )


def test_create_nado_client(
    mock_post: MagicMock,
    mock_web3: MagicMock,
    mock_load_abi: MagicMock,
    private_keys: list[str],
    url: str,
    endpoint_addr: str,
    chain_id: int,
    contracts_context: NadoContractsContext,
):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "data": {
            "endpoint_addr": endpoint_addr,
            "chain_id": chain_id,
        },
    }
    mock_post.return_value = mock_response

    signer = Account.from_key(private_keys[0])

    mainnet_nado_client = create_nado_client(NadoClientMode.MAINNET, signer)

    assert mainnet_nado_client.context.engine_client.chain_id == chain_id
    assert mainnet_nado_client.context.engine_client.endpoint_addr == endpoint_addr
    assert (
        mainnet_nado_client.context.engine_client.url == NadoBackendURL.MAINNET_GATEWAY
    )
    assert (
        mainnet_nado_client.context.indexer_client.url == NadoBackendURL.MAINNET_INDEXER
    )
    assert mainnet_nado_client.context.engine_client.signer == signer

    with pytest.raises(Exception, match="Mode provided `custom` not supported!"):
        create_nado_client("custom", signer)

    custom_nado_client = create_nado_client(
        NadoClientMode.TESTING,
        signer,
        NadoClientContextOpts(
            engine_endpoint_url=url,
            indexer_endpoint_url=url,
            rpc_node_url=url,
            contracts_context=contracts_context,
        ),
    )

    assert custom_nado_client.context.engine_client.url == url
    assert custom_nado_client.context.indexer_client.url == url
