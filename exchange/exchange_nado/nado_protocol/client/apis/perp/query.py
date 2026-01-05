from nado_protocol.client.apis.base import NadoBaseAPI
from nado_protocol.indexer_client.types.query import IndexerPerpPricesData


class PerpQueryAPI(NadoBaseAPI):
    """
    Provides functionalities for querying data related to Perpetual (Perp) products in the Nado Protocol.

    Inherits from NadoBaseAPI, which provides a basic context setup for accessing Nado.
    This class extends the base class to provide specific functionalities for querying data related to Perp products.

    Attributes:
        context (NadoClientContext): Provides connectivity details for accessing Nado APIs.
    """

    def get_prices(self, product_id: int) -> IndexerPerpPricesData:
        """
        Retrieves the latest index and mark price for a specific perp product from the indexer.

        Args:
            product_id (int): The identifier for the perp product.

        Returns:
            IndexerPerpPricesData: An object containing the latest index and mark price for the specified product.
                - product_id (int): The identifier for the perp product.
                - index_price_x18 (str): The latest index price for the product, scaled by 1e18.
                - mark_price_x18 (str): The latest mark price for the product, scaled by 1e18.
                - update_time (str): The timestamp of the last price update.
        """
        return self.context.indexer_client.get_perp_prices(product_id)
