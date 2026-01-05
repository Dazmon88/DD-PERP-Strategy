from nado_protocol.engine_client.types import EngineClientOpts
from nado_protocol.engine_client.execute import EngineExecuteClient
from nado_protocol.engine_client.query import EngineQueryClient


class EngineClient(EngineQueryClient, EngineExecuteClient):  # type: ignore
    """
    Client for interacting with the engine service.

    It allows users to both query data from and execute commands on the engine service.

    Attributes:
        opts (EngineClientOpts): Client configuration options for connecting and interacting with the engine service.

    Methods:
        __init__: Initializes the `EngineClient` with the provided options.
    """

    def __init__(self, opts: EngineClientOpts):
        """
        Initializes the EngineClient with the provided options.

        Args:
            opts (EngineClientOpts): Client configuration options for connecting and interacting with the engine service.
        """
        EngineQueryClient.__init__(self, opts)
        EngineExecuteClient.__init__(self, opts)


__all__ = [
    "EngineClient",
    "EngineClientOpts",
    "EngineExecuteClient",
    "EngineQueryClient",
]
