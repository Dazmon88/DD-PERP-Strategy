from sanity import NETWORK
from nado_protocol.contracts import NadoContracts, NadoContractsContext
from nado_protocol.contracts.loader import load_deployment


def run():
    print("setting up nado contracts")
    deployment = load_deployment(NETWORK)
    nado_contracts = NadoContracts(
        node_url=deployment.node_url,
        contracts_context=NadoContractsContext(**deployment.dict()),
    )

    print("node url:", deployment.node_url)
    print("endpoint:", nado_contracts.endpoint.address)
    print("querier:", nado_contracts.querier.address)
    print("clearinghouse:", nado_contracts.clearinghouse.address)
    print("spot_engine:", nado_contracts.spot_engine.address)
    print("perp_engine:", nado_contracts.perp_engine.address)
    print("n-submissions", nado_contracts.endpoint.functions.nSubmissions().call())
