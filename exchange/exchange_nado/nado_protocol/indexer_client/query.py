from typing import Optional, Union
import requests
from functools import singledispatchmethod
from nado_protocol.indexer_client.types import IndexerClientOpts
from nado_protocol.indexer_client.types.models import MarketType
from nado_protocol.indexer_client.types.query import (
    IndexerCandlesticksParams,
    IndexerCandlesticksData,
    IndexerEventsParams,
    IndexerEventsData,
    IndexerFundingRateParams,
    IndexerFundingRateData,
    IndexerFundingRatesParams,
    IndexerFundingRatesData,
    IndexerHistoricalOrdersByDigestParams,
    IndexerHistoricalOrdersData,
    IndexerSubaccountHistoricalOrdersParams,
    IndexerLinkedSignerRateLimitData,
    IndexerLinkedSignerRateLimitParams,
    IndexerLiquidationFeedData,
    IndexerLiquidationFeedParams,
    IndexerMarketSnapshotsData,
    IndexerMarketSnapshotsParams,
    IndexerMatchesParams,
    IndexerMatchesData,
    IndexerOraclePricesData,
    IndexerOraclePricesParams,
    IndexerParams,
    IndexerPerpPricesData,
    IndexerPerpPricesParams,
    IndexerProductSnapshotsData,
    IndexerProductSnapshotsParams,
    IndexerRequest,
    IndexerResponse,
    IndexerSubaccountsData,
    IndexerSubaccountsParams,
    IndexerQuotePriceParams,
    IndexerQuotePriceData,
    IndexerInterestAndFundingParams,
    IndexerInterestAndFundingData,
    IndexerAccountSnapshotsParams,
    IndexerAccountSnapshotsData,
    IndexerTickersData,
    IndexerPerpContractsData,
    IndexerHistoricalTradesData,
    to_indexer_request,
)
from nado_protocol.utils.model import (
    NadoBaseModel,
    ensure_data_type,
    is_instance_of_union,
)


class IndexerQueryClient:
    """
    Client for querying data from the indexer service.

    Attributes:
        _opts (IndexerClientOpts): Client configuration options for connecting and interacting with the indexer service.
        url (str): URL of the indexer service.
    """

    def __init__(self, opts: IndexerClientOpts):
        """
        Initializes the IndexerQueryClient with the provided options.

        Args:
            opts (IndexerClientOpts): Client configuration options for connecting and interacting with the indexer service.
        """
        self._opts = IndexerClientOpts.parse_obj(opts)
        self.url = self._opts.url
        self.url_v2: str = self.url.replace("/v1", "") + "/v2"
        self.session = requests.Session()

    @singledispatchmethod
    def query(self, params: Union[IndexerParams, IndexerRequest]) -> IndexerResponse:
        """
        Sends a query request to the indexer service and returns the response.

        The `query` method is overloaded to accept either `IndexerParams` or a dictionary or `IndexerRequest`
        as the input parameters. Based on the type of the input, the appropriate internal method is invoked
        to process the query request.

        Args:
            params (IndexerParams | dict | IndexerRequest): The parameters for the query request.

        Returns:
            IndexerResponse: The response from the indexer service.
        """
        req: IndexerRequest = (
            params if is_instance_of_union(params, IndexerRequest) else to_indexer_request(params)  # type: ignore
        )
        return self._query(req)

    @query.register
    def _(self, req: dict) -> IndexerResponse:
        return self._query(NadoBaseModel.parse_obj(req))  # type: ignore

    def _query(self, req: IndexerRequest) -> IndexerResponse:
        res = self.session.post(self.url, json=req.dict())
        if res.status_code != 200:
            raise Exception(res.text)
        try:
            indexer_res = IndexerResponse(data=res.json())
        except Exception:
            raise Exception(res.text)
        return indexer_res

    def _query_v2(self, url):
        res = self.session.get(url)
        if res.status_code != 200:
            raise Exception(res.text)
        return res.json()

    def get_subaccount_historical_orders(
        self, params: IndexerSubaccountHistoricalOrdersParams
    ) -> IndexerHistoricalOrdersData:
        """
        Retrieves the historical orders associated with a specific subaccount.

        Args:
            params (IndexerSubaccountHistoricalOrdersParams): The parameters specifying the subaccount for which to retrieve historical orders.

        Returns:
            IndexerHistoricalOrdersData: The historical orders associated with the specified subaccount.
        """
        return ensure_data_type(
            self.query(IndexerSubaccountHistoricalOrdersParams.parse_obj(params)).data,
            IndexerHistoricalOrdersData,
        )

    def get_historical_orders_by_digest(
        self, digests: list[str]
    ) -> IndexerHistoricalOrdersData:
        """
        Retrieves historical orders using their unique digests.

        Args:
            digests (list[str]): A list of order digests.

        Returns:
            IndexerHistoricalOrdersData: The historical orders corresponding to the provided digests.
        """
        return ensure_data_type(
            self.query(IndexerHistoricalOrdersByDigestParams(digests=digests)).data,
            IndexerHistoricalOrdersData,
        )

    def get_matches(self, params: IndexerMatchesParams) -> IndexerMatchesData:
        """
        Retrieves match data based on provided parameters.

        Args:
            params (IndexerMatchesParams): The parameters for the match data retrieval request.

        Returns:
            IndexerMatchesData: The match data corresponding to the provided parameters.
        """
        return ensure_data_type(
            self.query(IndexerMatchesParams.parse_obj(params)).data, IndexerMatchesData
        )

    def get_events(self, params: IndexerEventsParams) -> IndexerEventsData:
        """
        Retrieves event data based on provided parameters.

        Args:
            params (IndexerEventsParams): The parameters for the event data retrieval request.

        Returns:
            IndexerEventsData: The event data corresponding to the provided parameters.
        """
        return ensure_data_type(
            self.query(IndexerEventsParams.parse_obj(params)).data, IndexerEventsData
        )

    def get_product_snapshots(
        self, params: IndexerProductSnapshotsParams
    ) -> IndexerProductSnapshotsData:
        """
        Retrieves snapshot data for specific products.

        Args:
            params (IndexerProductSnapshotsParams): Parameters specifying the products for which to retrieve snapshot data.

        Returns:
            IndexerProductSnapshotsData: The product snapshot data corresponding to the provided parameters.
        """
        return ensure_data_type(
            self.query(IndexerProductSnapshotsParams.parse_obj(params)).data,
            IndexerProductSnapshotsData,
        )

    def get_market_snapshots(
        self, params: IndexerMarketSnapshotsParams
    ) -> IndexerMarketSnapshotsData:
        """
        Retrieves historical market snapshots.

        Args:
            params (IndexerMarketSnapshotsParams): Parameters specifying the historical market snapshot request.

        Returns:
            IndexerMarketSnapshotsData: The market snapshot data corresponding to the provided parameters.
        """
        return ensure_data_type(
            self.query(IndexerMarketSnapshotsParams.parse_obj(params)).data,
            IndexerMarketSnapshotsData,
        )

    def get_candlesticks(
        self, params: IndexerCandlesticksParams
    ) -> IndexerCandlesticksData:
        """
        Retrieves candlestick data based on provided parameters.

        Args:
            params (IndexerCandlesticksParams): The parameters for retrieving candlestick data.

        Returns:
            IndexerCandlesticksData: The candlestick data corresponding to the provided parameters.
        """
        return ensure_data_type(
            self.query(IndexerCandlesticksParams.parse_obj(params)).data,
            IndexerCandlesticksData,
        )

    def get_perp_funding_rate(self, product_id: int) -> IndexerFundingRateData:
        """
        Retrieves the funding rate data for a specific perp product.

        Args:
            product_id (int): The identifier of the perp product.

        Returns:
            IndexerFundingRateData: The funding rate data for the specified perp product.
        """
        return ensure_data_type(
            self.query(IndexerFundingRateParams(product_id=product_id)).data,
            IndexerFundingRateData,
        )

    def get_perp_funding_rates(self, product_ids: list) -> IndexerFundingRatesData:
        """
        Fetches the latest funding rates for a list of perp products.

        Args:
            product_ids (list): List of identifiers for the perp products.

        Returns:
            dict: A dictionary mapping each product_id to its latest funding rate and related details.
        """
        return ensure_data_type(
            self.query(IndexerFundingRatesParams(product_ids=product_ids)).data, dict
        )

    def get_perp_prices(self, product_id: int) -> IndexerPerpPricesData:
        """
        Retrieves the price data for a specific perp product.

        Args:
            product_id (int): The identifier of the perp product.

        Returns:
            IndexerPerpPricesData: The price data for the specified perp product.
        """
        return ensure_data_type(
            self.query(IndexerPerpPricesParams(product_id=product_id)).data,
            IndexerPerpPricesData,
        )

    def get_oracle_prices(self, product_ids: list[int]) -> IndexerOraclePricesData:
        """
        Retrieves the oracle price data for specific products.

        Args:
            product_ids (list[int]): A list of product identifiers.

        Returns:
            IndexerOraclePricesData: The oracle price data for the specified products.
        """
        return ensure_data_type(
            self.query(IndexerOraclePricesParams(product_ids=product_ids)).data,
            IndexerOraclePricesData,
        )

    def get_liquidation_feed(self) -> IndexerLiquidationFeedData:
        """
        Retrieves the liquidation feed data.

        Returns:
            IndexerLiquidationFeedData: The latest liquidation feed data.
        """
        return ensure_data_type(self.query(IndexerLiquidationFeedParams()).data, list)

    def get_linked_signer_rate_limits(
        self, subaccount: str
    ) -> IndexerLinkedSignerRateLimitData:
        """
        Retrieves the rate limits for a linked signer of a specific subaccount.

        Args:
            subaccount (str): The identifier of the subaccount.

        Returns:
            IndexerLinkedSignerRateLimitData: The rate limits for the linked signer of the specified subaccount.
        """
        return ensure_data_type(
            self.query(IndexerLinkedSignerRateLimitParams(subaccount=subaccount)).data,
            IndexerLinkedSignerRateLimitData,
        )

    def get_subaccounts(
        self, params: IndexerSubaccountsParams
    ) -> IndexerSubaccountsData:
        """
        Retrieves subaccounts via the indexer.

        Args:
            params (IndexerSubaccountsParams): The filter parameters for retrieving subaccounts.

        Returns:
            IndexerSubaccountsData: List of subaccounts found.
        """
        return ensure_data_type(
            self.query(params).data,
            IndexerSubaccountsData,
        )

    def get_quote_price(self) -> IndexerQuotePriceData:
        return ensure_data_type(
            self.query(IndexerQuotePriceParams()).data,
            IndexerQuotePriceData,
        )

    def get_interest_and_funding_payments(
        self, params: IndexerInterestAndFundingParams
    ) -> IndexerInterestAndFundingData:
        return ensure_data_type(
            self.query(
                params,
            ).data,
            IndexerInterestAndFundingData,
        )

    def get_tickers(
        self, market_type: Optional[MarketType] = None
    ) -> IndexerTickersData:
        url = f"{self.url_v2}/tickers"
        if market_type is not None:
            url += f"?market={str(market_type)}"
        return ensure_data_type(self._query_v2(url), dict)

    def get_perp_contracts_info(self) -> IndexerPerpContractsData:
        return ensure_data_type(self._query_v2(f"{self.url_v2}/contracts"), dict)

    def get_historical_trades(
        self, ticker_id: str, limit: Optional[int], max_trade_id: Optional[int] = None
    ) -> IndexerHistoricalTradesData:
        url = f"{self.url_v2}/trades?ticker_id={ticker_id}"
        if limit is not None:
            url += f"&limit={limit}"
        if max_trade_id is not None:
            url += f"&max_trade_id={max_trade_id}"
        return ensure_data_type(self._query_v2(url), list)

    def get_multi_subaccount_snapshots(
        self, params: IndexerAccountSnapshotsParams
    ) -> IndexerAccountSnapshotsData:
        """
        Retrieves subaccount snapshots at specified timestamps.
        Each snapshot is a view of the subaccount's balances at that point in time,
        with tracked variables for interest, funding, etc.

        Args:
            params (IndexerAccountSnapshotsParams): Parameters specifying subaccounts,
                timestamps, and whether to include isolated positions.

        Returns:
            IndexerAccountSnapshotsData: Dict mapping subaccount hex -> timestamp -> snapshot data.
                Each snapshot contains balances with trackedVars including netEntryUnrealized.
        """
        return ensure_data_type(
            self.query(IndexerAccountSnapshotsParams.parse_obj(params)).data,
            IndexerAccountSnapshotsData,
        )
