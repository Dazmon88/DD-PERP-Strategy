import logging
from nado_protocol.client.apis.market import MarketAPI
from nado_protocol.client.apis.perp import PerpAPI
from nado_protocol.client.apis.spot import SpotAPI
from nado_protocol.client.apis.subaccount import SubaccountAPI
from nado_protocol.client.apis.rewards import RewardsAPI
from nado_protocol.client.context import (
    NadoClientContext,
    NadoClientContextOpts,
    create_nado_client_context,
)
from nado_protocol.contracts import NadoContractsContext
from nado_protocol.contracts.loader import load_deployment
from nado_protocol.contracts.types import NadoNetwork
from nado_protocol.utils.backend import NadoBackendURL, Signer
from nado_protocol.utils.enum import StrEnum
from nado_protocol.client.context import *

from pydantic import parse_obj_as


class NadoClientMode(StrEnum):
    """
    NadoClientMode is an enumeration representing the operational modes of the NadoClient.

    Attributes:
        MAINNET: For operating in Nado's mainnet environment deployed on Ink.

        DEVNET: For local development.

        TESTING: For running tests.
    """

    # dev
    DEVNET = "devnet"
    TESTING = "testing"

    # testnet
    TESTNET = "testnet"  # Ink Sepolia

    # mainnet
    MAINNET = "mainnet"  # Ink Mainnet


class NadoClient:
    """
    The primary client interface for interacting with Nado Protocol.

    This client consolidates the functionality of various aspects of Nado such as spot, market,
    subaccount, and perpetual (perp) operations.

    To initialize an instance of this client, use the `create_nado_client` utility.

    Attributes:
        - context (NadoClientContext): The client context containing configuration for interacting with Nado.
        - market (MarketAPI): Sub-client for executing and querying market operations.
        - subaccount (SubaccountAPI): Sub-client for executing and querying subaccount operations.
        - spot (SpotAPI): Sub-client for executing and querying spot operations.
        - perp (PerpAPI): Sub-client for executing and querying perpetual operations.
        - rewards (RewardsAPI): Sub-client for executing and querying rewards operations (e.g: staking, claiming, etc).
    """

    context: NadoClientContext
    market: MarketAPI
    subaccount: SubaccountAPI
    spot: SpotAPI
    perp: PerpAPI
    rewards: RewardsAPI

    def __init__(self, context: NadoClientContext):
        """
        Initialize a new instance of the NadoClient.

        This constructor should not be called directly. Instead, use the `create_nado_client` utility to
        create a new NadoClient. This is because the `create_nado_client` utility includes important
        additional setup steps that aren't included in this constructor.

        Args:
            context (NadoClientContext): The client context.

        Note:
            Use `create_nado_client` for creating instances.
        """
        self.context = context
        self.market = MarketAPI(context)
        self.subaccount = SubaccountAPI(context)
        self.spot = SpotAPI(context)
        self.perp = PerpAPI(context)
        self.rewards = RewardsAPI(context)


def create_nado_client(
    mode: NadoClientMode,
    signer: Optional[Signer] = None,
    context_opts: Optional[NadoClientContextOpts] = None,
) -> NadoClient:
    """
    Create a new NadoClient based on the given mode and signer.

    This function will create a new NadoClientContext based on the provided mode, and then
    initialize a new NadoClient with that context.

    If `context_opts` are provided, they will be used to create the client context. Otherwise,
    default context options for the given mode will be used.

    Args:
        mode (NadoClientMode): The mode in which to operate the client. Can be one of the following:
            NadoClientMode.DEVNET: For local development.

        signer (Signer, optional): An instance of LocalAccount or a private key string for signing transactions.

        context_opts (NadoClientContextOpts, optional): Options for creating the client context.
            If not provided, default options for the given mode will be used.

    Returns:
        NadoClient: The created NadoClient instance.
    """
    logging.info(f"Initializing default {mode} context")
    (
        engine_endpoint_url,
        indexer_endpoint_url,
        trigger_endpoint_url,
        network_name,
    ) = client_mode_to_setup(mode)
    try:
        network = NadoNetwork(network_name)
        deployment = load_deployment(network)
        rpc_node_url = deployment.node_url
        contracts_context = NadoContractsContext(
            network=network,
            endpoint_addr=deployment.endpoint_addr,
            querier_addr=deployment.querier_addr,
            perp_engine_addr=deployment.perp_engine_addr,
            spot_engine_addr=deployment.spot_engine_addr,
            clearinghouse_addr=deployment.clearinghouse_addr,
            airdrop_addr=deployment.airdrop_addr,
            staking_addr=deployment.staking_addr,
            foundation_rewards_airdrop_addr=deployment.foundation_rewards_airdrop_addr,
        )
    except Exception as e:
        logging.warning(
            f"Failed to load contracts for mode {mode} with error: {e}, using provided defaults."
        )
        assert context_opts is not None and context_opts.rpc_node_url is not None
        assert context_opts is not None and context_opts.contracts_context is not None

        rpc_node_url = context_opts.rpc_node_url
        contracts_context = context_opts.contracts_context

    if context_opts:
        parsed_context_opts: NadoClientContextOpts = NadoClientContextOpts.parse_obj(
            context_opts
        )
        engine_endpoint_url = (
            parsed_context_opts.engine_endpoint_url or engine_endpoint_url
        )
        indexer_endpoint_url = (
            parsed_context_opts.indexer_endpoint_url or indexer_endpoint_url
        )
        trigger_endpoint_url = (
            parsed_context_opts.trigger_endpoint_url or trigger_endpoint_url
        )
        rpc_node_url = parsed_context_opts.rpc_node_url or rpc_node_url
        contracts_context = parsed_context_opts.contracts_context or contracts_context

    context = create_nado_client_context(
        NadoClientContextOpts(
            rpc_node_url=rpc_node_url,
            engine_endpoint_url=parse_obj_as(AnyUrl, engine_endpoint_url),
            indexer_endpoint_url=parse_obj_as(AnyUrl, indexer_endpoint_url),
            trigger_endpoint_url=parse_obj_as(AnyUrl, trigger_endpoint_url),
            contracts_context=contracts_context,
        ),
        signer,
    )
    return NadoClient(context)


def client_mode_to_setup(
    client_mode: NadoClientMode,
) -> tuple[str, str, str, str]:
    try:
        return {
            NadoClientMode.DEVNET: (
                NadoBackendURL.DEVNET_GATEWAY.value,
                NadoBackendURL.DEVNET_INDEXER.value,
                NadoBackendURL.DEVNET_TRIGGER.value,
                NadoNetwork.HARDHAT.value,
            ),
            NadoClientMode.TESTING: (
                NadoBackendURL.DEVNET_GATEWAY.value,
                NadoBackendURL.DEVNET_INDEXER.value,
                NadoBackendURL.DEVNET_TRIGGER.value,
                NadoNetwork.TESTING.value,
            ),
            NadoClientMode.TESTNET: (
                NadoBackendURL.TESTNET_GATEWAY.value,
                NadoBackendURL.TESTNET_INDEXER.value,
                NadoBackendURL.TESTNET_TRIGGER.value,
                NadoNetwork.TESTNET.value,
            ),
            NadoClientMode.MAINNET: (
                NadoBackendURL.MAINNET_GATEWAY.value,
                NadoBackendURL.MAINNET_INDEXER.value,
                NadoBackendURL.MAINNET_TRIGGER.value,
                NadoNetwork.MAINNET.value,
            ),
        }[client_mode]
    except KeyError:
        raise Exception(f"Mode provided `{client_mode}` not supported!")


__all__ = [
    "NadoClient",
    "NadoClientMode",
    "create_nado_client",
    "NadoClientContext",
    "NadoClientContextOpts",
    "create_nado_client_context",
]
