from unittest.mock import MagicMock

from nado_protocol.contracts import NadoContracts, NadoContractsContext


def test_nado_contracts(
    url: str,
    mock_web3: MagicMock,
    mock_load_abi: MagicMock,
    contracts_context: NadoContractsContext,
):
    contracts = NadoContracts(node_url=url, contracts_context=contracts_context)

    assert contracts.endpoint
    assert contracts.querier
    assert not contracts.clearinghouse
    assert not contracts.perp_engine
    assert not contracts.spot_engine
