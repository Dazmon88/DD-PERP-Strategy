from typing import Optional
from nado_protocol.client.apis.base import NadoBaseAPI
from nado_protocol.engine_client.types.query import (
    AllProductsData,
    MarketLiquidityData,
    MarketPriceData,
    MaxLpMintableData,
    MaxOrderSizeData,
    ProductSymbolsData,
    SubaccountOpenOrdersData,
    SubaccountMultiProductsOpenOrdersData,
    QueryMaxOrderSizeParams,
    IsolatedPositionsData,
)
from nado_protocol.indexer_client.types.query import (
    IndexerCandlesticksData,
    IndexerCandlesticksParams,
    IndexerFundingRateData,
    IndexerFundingRatesData,
    IndexerHistoricalOrdersData,
    IndexerSubaccountHistoricalOrdersParams,
    IndexerProductSnapshotsData,
    IndexerProductSnapshotsParams,
    IndexerMarketSnapshotsParams,
    IndexerMarketSnapshotsData,
)
from nado_protocol.trigger_client.types.query import (
    ListTriggerOrdersParams,
    TriggerQueryResponse,
)
from nado_protocol.utils.exceptions import MissingTriggerClient


class MarketQueryAPI(NadoBaseAPI):
    """
    The MarketQueryAPI class provides methods to interact with the Nado's market querying APIs.

    This class provides functionality for querying various details about the market including fetching
    information about order books, fetching historical orders, and retrieving market matches, among others.

    Attributes:
        context (NadoClientContext): The context that provides connectivity configuration for NadoClient.

    Note:
        This class should not be instantiated directly, it is designed to be used through a NadoClient instance.
    """

    def get_all_engine_markets(self) -> AllProductsData:
        """
        Retrieves all market states from the off-chain engine.

        Returns:
            AllProductsData: A data class object containing information about all products in the engine.
        """
        return self.context.engine_client.get_all_products()

    def get_all_product_symbols(self) -> ProductSymbolsData:
        """
        Retrieves all product symbols from the off-chain engine

        Returns:
            ProductSymbolsData: A list of all products with corresponding symbol.
        """
        return self.context.engine_client.get_product_symbols()

    def get_market_liquidity(self, product_id: int, depth: int) -> MarketLiquidityData:
        """
        Retrieves liquidity per price tick from the engine.

        The engine will skip price levels that have no liquidity,
        so it is not guaranteed that the bids/asks are evenly spaced

        Parameters:
            product_id (int): The product ID for which liquidity is to be fetched.
            depth (int): The depth of the order book to retrieve liquidity from.

        Returns:
            MarketLiquidityData: A data class object containing liquidity information for the specified product.
        """
        return self.context.engine_client.get_market_liquidity(product_id, depth)

    def get_latest_market_price(self, product_id: int) -> MarketPriceData:
        """
        Retrieves the latest off-chain orderbook price from the engine for a specific product.

        Args:
            product_id (int): The identifier for the product to retrieve the latest market price.

        Returns:
            MarketPriceData: A data class object containing information about the latest market price for the given product.
        """
        return self.context.engine_client.get_market_price(product_id)

    def get_subaccount_open_orders(
        self, product_id: int, sender: str
    ) -> SubaccountOpenOrdersData:
        """
        Queries the off-chain engine to retrieve the status of any open orders for a given subaccount.

        This function fetches any open orders that a specific subaccount might have
        for a specific product from the off-chain engine. The orders are returned as
        an SubaccountOpenOrdersData object.

        Args:
            product_id (int): The identifier for the product to fetch open orders.

            sender (str): The address and subaccount identifier as a bytes32 hex string.

        Returns:
            SubaccountOpenOrdersData: A data class object containing information about the open orders of a subaccount.
        """
        return self.context.engine_client.get_subaccount_open_orders(product_id, sender)

    def get_subaccount_multi_products_open_orders(
        self, product_ids: list[int], sender: str
    ) -> SubaccountMultiProductsOpenOrdersData:
        """
        Queries the off-chain engine to retrieve the status of any open orders for a given subaccount across multiple products.

        This function fetches any open orders that a specific subaccount might have
        for products product from the off-chain engine. The orders are returned as
        an SubaccountMultiProductsOpenOrdersData object.

        Args:
            product_ids (list[int]): List of product ids to fetch open orders for.

            sender (str): The address and subaccount identifier as a bytes32 hex string.

        Returns:
            SubaccountMultiProductsOpenOrdersData: A data class object containing information about the open orders of a subaccount.
        """
        return self.context.engine_client.get_subaccount_multi_products_open_orders(
            product_ids, sender
        )

    def get_subaccount_historical_orders(
        self, params: IndexerSubaccountHistoricalOrdersParams
    ) -> IndexerHistoricalOrdersData:
        """
        Queries the indexer to fetch historical orders of a specific subaccount.

        This function retrieves a list of historical orders that a specific subaccount has placed.
        The order data can be filtered using various parameters provided in the
        IndexerSubaccountHistoricalOrdersParams object. The fetched historical orders data
        is returned as an IndexerHistoricalOrdersData object.

        Args:
            params (IndexerSubaccountHistoricalOrdersParams): Parameters to filter the historical orders data:
                - subaccount (str): The address and subaccount identifier as a bytes32 hex string.
                - product_ids (list[int], optional): A list of identifiers for the products to fetch orders for. If provided, the function will return orders related to these products.
                - idx (int, optional): Submission index. If provided, the function will return orders submitted before this index.
                - max_time (int, optional): Maximum timestamp for the orders. The function will return orders submitted before this time.
                - limit (int, optional): Maximum number of orders to return. If provided, the function will return at most 'limit' number of orders.

        Returns:
            IndexerHistoricalOrdersData: A data class object containing information about the historical orders of a subaccount.
        """
        return self.context.indexer_client.get_subaccount_historical_orders(params)

    def get_historical_orders_by_digest(
        self, digests: list[str]
    ) -> IndexerHistoricalOrdersData:
        """
        Queries the indexer to fetch historical orders based on a list of provided digests.

        This function retrieves historical order data for a given list of order digests.
        Each digest represents a unique order. The returned object includes the historical
        order data for each digest in the provided list.

        Args:
            digests (list[str]): List of order digests. An order digest is a unique identifier for each order.

        Returns:
            IndexerHistoricalOrdersData: A data class object containing information about the historical orders associated with the provided digests.
        """
        return self.context.indexer_client.get_historical_orders_by_digest(digests)

    def get_max_order_size(self, params: QueryMaxOrderSizeParams) -> MaxOrderSizeData:
        """
        Queries the engine to determine the maximum order size that can be submitted within
        health requirements.

        Args:
            params (QueryMaxOrderSizeParams):
                - sender (str): The address and subaccount identifier in a bytes32 hex string.
                - product_id (int): The identifier for the spot/perp product.
                - price_x18 (str): The price of the order in x18 format as a string.
                - direction (MaxOrderSizeDirection): 'long' for max bid or 'short' for max ask.
                - spot_leverage (Optional[bool]): If False, calculates max size without borrowing. Defaults to True.

        Returns:
            MaxOrderSizeData: The maximum size of the order that can be placed.
        """
        return self.context.engine_client.get_max_order_size(params)

    def get_max_nlp_mintable(
        self, product_id: int, sender: str, spot_leverage: Optional[bool] = None
    ) -> MaxLpMintableData:
        """
        Queries the engine to determine the maximum base amount that can be contributed for minting LPs.

        Args:
            product_id (int): The identifier for the spot/perp product.

            sender (str): The address and subaccount identifier in a bytes32 hex string.

            spot_leverage (Optional[bool]): If False, calculates max amount without considering leverage. Defaults to True.

        Returns:
            MaxLpMintableData: Maximum base amount that can be contributed for minting LPs, in string format.
        """
        return self.context.engine_client.get_max_nlp_mintable(
            product_id, sender, spot_leverage
        )

    def get_candlesticks(
        self, params: IndexerCandlesticksParams
    ) -> IndexerCandlesticksData:
        """
        Fetches historical candlestick data for a specific product using the indexer.

        Args:
            params (IndexerCandlesticksParams): Parameters for the query, which include:
                - product_id (int): The identifier for the product.
                - granularity (IndexerCandlesticksGranularity): Duration for each candlestick in seconds.

        Returns:
            IndexerCandlesticksData: Contains a list of historical candlestick data (IndexerCandlestick)
            for the specified product at the specified granularity.

        Note:
            For obtaining the latest orderbook prices, consider using the 'get_latest_market_price()' method.
        """

        return self.context.indexer_client.get_candlesticks(params)

    def get_perp_funding_rate(self, product_id: int) -> IndexerFundingRateData:
        """
        Fetches the latest funding rate for a specific perp product.

        Args:
            product_id (int): Identifier for the perp product.

        Returns:
            IndexerFundingRateData: Contains the latest funding rate and related details for the given perp product.
        """
        return self.context.indexer_client.get_perp_funding_rate(product_id)

    def get_perp_funding_rates(self, product_ids: list) -> IndexerFundingRatesData:
        """
        Fetches the latest funding rates for a list of perp products.

        Args:
            product_ids (list): List of identifiers for the perp products.

        Returns:
            dict: A dictionary mapping each product_id to its latest funding rate and related details.
        """
        return self.context.indexer_client.get_perp_funding_rates(product_ids)

    def get_product_snapshots(
        self, params: IndexerProductSnapshotsParams
    ) -> IndexerProductSnapshotsData:
        """
        Fetches the historical snapshots for a specific product from the indexer.

        Args:
            params (IndexerProductSnapshotsParams): Query parameters consisting of:
                - product_id (int): Identifier for the product.
                - idx (int, optional): Submission index to filter the returned snapshots.
                - max_time (int, optional): Maximum timestamp to filter the returned snapshots.
                - limit (int, optional): Maximum number of snapshots to return.

        Returns:
            IndexerProductSnapshotsData: Object containing lists of product snapshots and related transaction data.
        """
        return self.context.indexer_client.get_product_snapshots(params)

    def get_market_snapshots(
        self, params: IndexerMarketSnapshotsParams
    ) -> IndexerMarketSnapshotsData:
        """
        Fetches the historical market snapshots from the indexer.

        Args:
            params (IndexerMarketSnapshotsParams): Parameters specifying the historical market snapshot request.

        Returns:
            IndexerMarketSnapshotsData: The market snapshot data corresponding to the provided parameters.
        """
        return self.context.indexer_client.get_market_snapshots(params)

    def get_trigger_orders(
        self, params: ListTriggerOrdersParams
    ) -> TriggerQueryResponse:
        if self.context.trigger_client is None:
            raise MissingTriggerClient()
        return self.context.trigger_client.list_trigger_orders(params)

    def get_isolated_positions(self, subaccount: str) -> IsolatedPositionsData:
        """
        Retrieve isolated positions for a specific subaccount.

        Args:
            subaccount (str): Unique identifier for the subaccount.

        Returns:
            IsolatedPositionsData: A data class object containing information about the isolated positions for the specified subaccount.
        """
        return self.context.engine_client.get_isolated_positions(subaccount)
