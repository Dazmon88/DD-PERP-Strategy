from nado_protocol.indexer_client.query import IndexerQueryClient
from nado_protocol.indexer_client.types import IndexerClientOpts


class IndexerClient(IndexerQueryClient):
    """
    Client for interacting with the indexer service.

    It provides methods for querying data from the indexer service.

    Attributes:
        opts (IndexerClientOpts): Client configuration options for connecting and interacting with the indexer service.

    Methods:
        __init__: Initializes the `IndexerClient` with the provided options.
    """

    def __init__(self, opts: IndexerClientOpts):
        """
        Initializes the IndexerClient with the provided options.

        Args:
            opts (IndexerClientOpts): Client configuration options for connecting and interacting with the indexer service.
        """
        super().__init__(opts)


__all__ = ["IndexerClient", "IndexerClientOpts", "IndexerQueryClient"]
