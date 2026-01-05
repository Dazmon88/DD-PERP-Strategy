import logging
from dataclasses import dataclass
from typing import Optional
from eth_account import Account

from pydantic import AnyUrl, BaseModel
from nado_protocol.contracts import NadoContracts, NadoContractsContext
from eth_account.signers.local import LocalAccount
from nado_protocol.engine_client import EngineClient
from nado_protocol.engine_client.types import EngineClientOpts
from nado_protocol.utils.backend import Signer
from nado_protocol.indexer_client import IndexerClient
from nado_protocol.trigger_client import TriggerClient
from nado_protocol.indexer_client.types import IndexerClientOpts
from nado_protocol.trigger_client.types import TriggerClientOpts


@dataclass
class NadoClientContext:
    """
    Context required to use the Nado client.
    """

    signer: Optional[LocalAccount]
    engine_client: EngineClient
    indexer_client: IndexerClient
    trigger_client: Optional[TriggerClient]
    contracts: NadoContracts


class NadoClientContextOpts(BaseModel):
    contracts_context: Optional[NadoContractsContext]
    rpc_node_url: Optional[AnyUrl]
    engine_endpoint_url: Optional[AnyUrl]
    indexer_endpoint_url: Optional[AnyUrl]
    trigger_endpoint_url: Optional[AnyUrl]


def create_nado_client_context(
    opts: NadoClientContextOpts, signer: Optional[Signer] = None
) -> NadoClientContext:
    """
    Initializes a NadoClientContext instance with the provided signer and options.

    Args:
        opts (NadoClientContextOpts): Options including endpoints for the engine and indexer clients.

        signer (Signer, optional): An instance of LocalAccount or a private key string for signing transactions.

    Returns:
        NadoClientContext: The initialized Nado client context.

    Note:
        This helper attempts to fully set up the engine, indexer and trigger clients, including the necessary verifying contracts
        to correctly sign executes. If this step fails, it is skipped and can be set up later, while logging the error.
    """
    assert opts.contracts_context is not None, "Missing contracts context"
    assert opts.rpc_node_url is not None, "Missing RPC node URL"
    assert opts.engine_endpoint_url is not None, "Missing engine endpoint URL"
    assert opts.indexer_endpoint_url is not None, "Missing indexer endpoint URL"

    signer = Account.from_key(signer) if isinstance(signer, str) else signer
    engine_client = EngineClient(
        EngineClientOpts(url=opts.engine_endpoint_url, signer=signer)
    )
    trigger_client = None
    try:
        contracts = engine_client.get_contracts()
        engine_client.endpoint_addr = contracts.endpoint_addr
        engine_client.chain_id = int(contracts.chain_id)

        if opts.trigger_endpoint_url is not None:
            trigger_client = TriggerClient(
                TriggerClientOpts(url=opts.trigger_endpoint_url, signer=signer)
            )
            trigger_client.endpoint_addr = contracts.endpoint_addr
            trigger_client.chain_id = int(contracts.chain_id)
    except Exception as e:
        logging.warning(
            f"Failed to setup engine client verifying contracts with error: {e}"
        )
    return NadoClientContext(
        signer=signer,
        engine_client=engine_client,
        trigger_client=trigger_client,
        indexer_client=IndexerClient(IndexerClientOpts(url=opts.indexer_endpoint_url)),
        contracts=NadoContracts(opts.rpc_node_url, opts.contracts_context),
    )
