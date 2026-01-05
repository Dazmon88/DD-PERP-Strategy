import json
from typing import Optional
import requests

from nado_protocol.engine_client import EngineClientOpts
from nado_protocol.engine_client.types.models import (
    MarketType,
    Orderbook,
    ResponseStatus,
    SubaccountPosition,
)
from nado_protocol.engine_client.types.query import (
    AllProductsData,
    ContractsData,
    FeeRatesData,
    HealthGroupsData,
    LinkedSignerData,
    MarketLiquidityData,
    MarketPriceData,
    MaxLpMintableData,
    MaxOrderSizeData,
    MaxWithdrawableData,
    NoncesData,
    ProductSymbolsData,
    SubaccountOpenOrdersData,
    SubaccountMultiProductsOpenOrdersData,
    OrderData,
    QueryAllProductsParams,
    QueryContractsParams,
    QueryFeeRatesParams,
    QueryHealthGroupsParams,
    QueryLinkedSignerParams,
    QueryMarketLiquidityParams,
    QueryMarketPriceParams,
    QueryMaxLpMintableParams,
    QueryMaxOrderSizeParams,
    QueryMaxWithdrawableParams,
    QueryNoncesParams,
    QuerySubaccountOpenOrdersParams,
    QuerySubaccountMultiProductOpenOrdersParams,
    QueryOrderParams,
    QueryIsolatedPositionsParams,
    QueryRequest,
    QueryResponse,
    QueryStatusParams,
    QuerySubaccountInfoParams,
    QuerySubaccountInfoTx,
    StatusData,
    SubaccountInfoData,
    SymbolsData,
    QuerySymbolsParams,
    AssetsData,
    MarketPairsData,
    SpotsAprData,
    IsolatedPositionsData,
)
from nado_protocol.utils.exceptions import (
    BadStatusCodeException,
    QueryFailedException,
)
from nado_protocol.utils.model import ensure_data_type


class EngineQueryClient:
    """
    Client class for querying the off-chain engine.
    """

    def __init__(self, opts: EngineClientOpts):
        """
        Initialize EngineQueryClient with provided options.

        Args:
            opts (EngineClientOpts): Options for the client.
        """
        self._opts: EngineClientOpts = EngineClientOpts.parse_obj(opts)
        self.url: str = self._opts.url
        self.url_v2: str = self.url.replace("/v1", "") + "/v2"
        self.session = requests.Session()  # type: ignore

    def query(self, req: QueryRequest) -> QueryResponse:
        """
        Send a query to the engine.

        Args:
            req (QueryRequest): The query request parameters.

        Returns:
            QueryResponse: The response from the engine.

        Raises:
            BadStatusCodeException: If the response status code is not 200.
            QueryFailedException: If the query status is not "success".
        """
        res = self.session.post(f"{self.url}/query", json=req.dict())
        if res.status_code != 200:
            raise BadStatusCodeException(res.text)
        try:
            query_res = QueryResponse(**res.json())
        except Exception:
            raise QueryFailedException(res.text)
        if query_res.status != "success":
            raise QueryFailedException(res.text)
        return query_res

    def _query_v2(self, url):
        res = self.session.get(url)
        if res.status_code != 200:
            raise Exception(res.text)
        return res.json()

    def get_product_symbols(self) -> ProductSymbolsData:
        """
        Retrieves symbols for all available products.

        Returns:
            ProductSymbolsData: Symbols for all available products.
        """
        res = self.session.get(f"{self.url}/symbols?")
        if res.status_code != 200:
            raise BadStatusCodeException(res.text)
        try:
            query_res = QueryResponse(
                status=ResponseStatus.SUCCESS,
                data=res.json(),
                error=None,
                error_code=None,
                request_type=None,
            )
        except Exception:
            raise QueryFailedException(res.text)
        return ensure_data_type(query_res.data, list)

    def get_status(self) -> StatusData:
        """
        Query the engine for its status.

        Returns:
            StatusData: The status of the engine.
        """
        return ensure_data_type(self.query(QueryStatusParams()).data, StatusData)

    def get_contracts(self) -> ContractsData:
        """
        Query the engine for Nado contract addresses.

        Use this to fetch verifying contracts needed for signing executes.

        Returns:
            ContractsData: Nado contracts info.
        """
        return ensure_data_type(self.query(QueryContractsParams()).data, ContractsData)

    def get_nonces(self, address: str) -> NoncesData:
        """
        Query the engine for nonces of a specific address.

        Args:
            address (str): Wallet address to fetch nonces for.

        Returns:
            NoncesData: The nonces of the address.
        """
        return ensure_data_type(
            self.query(QueryNoncesParams(address=address)).data, NoncesData
        )

    def get_order(self, product_id: int, digest: str) -> OrderData:
        """
        Query the engine for an order with a specific product id and digest.

        Args:
            product_id (int): The id of the product.

            digest (str): The digest of the order.

        Returns:
            OrderData: The order data.
        """
        return ensure_data_type(
            self.query(QueryOrderParams(product_id=product_id, digest=digest)).data,
            OrderData,
        )

    def get_subaccount_info(
        self,
        subaccount: str,
        txs: Optional[list[QuerySubaccountInfoTx]] = None,
        pre_state: Optional[bool] = None,
    ) -> SubaccountInfoData:
        """
        Query the engine for the state of a subaccount, including balances.

        Args:
            subaccount (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

            txs (list[QuerySubaccountInfoTx], optional): You can optionally provide a list of txs, to get an estimated view
            of what the subaccount state would look like if the transactions were applied.

            pre_state (bool, optional): When True and txs are provided, returns the subaccount state before the
            transactions were applied in the pre_state field. Defaults to False.

        Returns:
            SubaccountInfoData: Information about the specified subaccount.
        """
        txns_str = None
        if txs is not None:
            txns_str = json.dumps([tx.dict() for tx in txs])

        pre_state_str = None
        if pre_state is not None:
            pre_state_str = str(pre_state).lower()

        return ensure_data_type(
            self.query(
                QuerySubaccountInfoParams(
                    subaccount=subaccount, txns=txns_str, pre_state=pre_state_str
                )
            ).data,
            SubaccountInfoData,
        )

    def get_subaccount_open_orders(
        self, product_id: int, sender: str
    ) -> SubaccountOpenOrdersData:
        """
        Retrieves the open orders for a subaccount on a specific product.

        Args:
            product_id (int): The identifier of the product for which open orders are to be fetched.

            sender (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

        Returns:
            SubaccountOpenOrdersData: A data object containing the open orders for the
            specified subaccount on the provided product.
        """
        return ensure_data_type(
            self.query(
                QuerySubaccountOpenOrdersParams(product_id=product_id, sender=sender)
            ).data,
            SubaccountOpenOrdersData,
        )

    def get_subaccount_multi_products_open_orders(
        self, product_ids: list[int], sender: str
    ) -> SubaccountMultiProductsOpenOrdersData:
        """
        Retrieves the open orders for a subaccount on a specific product.

        Args:
            product_ids (list[int]): List of product ids to fetch open orders for.

            sender (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

        Returns:
            SubaccountMultiProductsOpenOrdersData: A data object containing the open orders for the
            specified subaccount on the provided product.
        """
        return ensure_data_type(
            self.query(
                QuerySubaccountMultiProductOpenOrdersParams(
                    product_ids=product_ids, sender=sender
                )
            ).data,
            SubaccountMultiProductsOpenOrdersData,
        )

    def get_market_liquidity(self, product_id: int, depth: int) -> MarketLiquidityData:
        """
        Query the engine for market liquidity data for a specific product.

        Args:
            product_id (int): The id of the product.

            depth (int): The depth of the market.

        Returns:
            MarketLiquidityData: Market liquidity data for the specified product.
        """
        return ensure_data_type(
            self.query(
                QueryMarketLiquidityParams(product_id=product_id, depth=depth)
            ).data,
            MarketLiquidityData,
        )

    def get_symbols(
        self,
        product_type: Optional[str] = None,
        product_ids: Optional[list[int]] = None,
    ) -> SymbolsData:
        """
        Query engine for symbols and product info

        Args:
            product_type (Optional[str): "spot" or "perp" products

            product_ids (Optional[list[int]]): product_ids to return info for

        """
        return ensure_data_type(
            self.query(
                QuerySymbolsParams(product_type=product_type, product_ids=product_ids)
            ).data,
            SymbolsData,
        )

    def get_all_products(self) -> AllProductsData:
        """
        Retrieves info about all available products,
        including: product id, oracle price, configuration, state, etc.

        Returns:
            AllProductsData: Data about all products.
        """
        return ensure_data_type(
            self.query(QueryAllProductsParams()).data, AllProductsData
        )

    def get_market_price(self, product_id: int) -> MarketPriceData:
        """
        Retrieves the highest bid and lowest ask price levels
        from the orderbook for a given product.

        Args:
            product_id (int): The id of the product.

        Returns:
            MarketPriceData: Market price data for the specified product.
        """
        return ensure_data_type(
            self.query(QueryMarketPriceParams(product_id=product_id)).data,
            MarketPriceData,
        )

    def get_max_order_size(self, params: QueryMaxOrderSizeParams) -> MaxOrderSizeData:
        """
        Retrieves the maximum order size of a given product for a specified subaccount.

        Args:
            params (QueryMaxOrderSizeParams): The parameters object that contains
            the details of the subaccount and product for which the max order size is to be fetched.

        Returns:
            MaxOrderSizeData: A data object containing the maximum order size possible
            for the given subaccount and product.
        """
        return ensure_data_type(
            self.query(QueryMaxOrderSizeParams.parse_obj(params)).data, MaxOrderSizeData
        )

    def get_max_withdrawable(
        self, product_id: int, sender: str, spot_leverage: Optional[bool] = None
    ) -> MaxWithdrawableData:
        """
        Retrieves the maximum withdrawable amount for a given spot product for a subaccount.

        Args:
            product_id (int): ID of the spot product.

            sender (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

            spot_leverage (bool, optional): If False, calculates without borrowing. Defaults to True.

        Returns:
            MaxWithdrawableData: Contains the maximum withdrawable amount.
        """
        return ensure_data_type(
            self.query(
                QueryMaxWithdrawableParams(
                    product_id=product_id, sender=sender, spot_leverage=spot_leverage
                )
            ).data,
            MaxWithdrawableData,
        )

    def get_max_nlp_mintable(
        self, product_id: int, sender: str, spot_leverage: Optional[bool] = None
    ) -> MaxLpMintableData:
        """
        Retrieves the maximum LP token amount mintable for a given product for a subaccount.

        Args:
            product_id (int): ID of the product.

            sender (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

            spot_leverage (bool, optional): If False, calculates without considering borrowing. Defaults to True.

        Returns:
            MaxLpMintableData: Contains the maximum LP token mintable amount.
        """
        return ensure_data_type(
            self.query(
                QueryMaxLpMintableParams(
                    product_id=product_id, sender=sender, spot_leverage=spot_leverage
                )
            ).data,
            MaxLpMintableData,
        )

    def get_fee_rates(self, sender: str) -> FeeRatesData:
        """
        Retrieves the fee rates associated with a specific subaccount.

        Args:
            sender (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

        Returns:
            FeeRatesData: Contains fee rates information associated with the subaccount.
        """
        return ensure_data_type(
            self.query(QueryFeeRatesParams(sender=sender)).data, FeeRatesData
        )

    def get_health_groups(self) -> HealthGroupsData:
        """
        Retrieves all available health groups. A health group represents a set of perp
        and spot products whose health is calculated together, such as BTC
        and BTC-PERP.

        Returns:
            HealthGroupsData: Contains health group information, each including both a spot
            and a perp product.
        """
        return ensure_data_type(
            self.query(QueryHealthGroupsParams()).data, HealthGroupsData
        )

    def get_linked_signer(self, subaccount: str) -> LinkedSignerData:
        """
        Retrieves the current linked signer for the specified subaccount.

        Args:
            subaccount (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

        Returns:
            LinkedSignerData: Information about the currently linked signer for the subaccount.
        """
        return ensure_data_type(
            self.query(QueryLinkedSignerParams(subaccount=subaccount)).data,
            LinkedSignerData,
        )

    def get_isolated_positions(self, subaccount: str) -> IsolatedPositionsData:
        """
        Retrieves the isolated positions for a specific subaccount.

        Args:
            subaccount (str): Identifier of the subaccount (owner's address + subaccount name) sent as a hex string.

        Returns:
            IsolatedPositionsData: A data object containing the isolated positions for the specified subaccount.
        """
        return ensure_data_type(
            self.query(QueryIsolatedPositionsParams(subaccount=subaccount)).data,
            IsolatedPositionsData,
        )

    def _get_subaccount_product_position(
        self, subaccount: str, product_id: int
    ) -> SubaccountPosition:
        summary = self.get_subaccount_info(subaccount)
        try:
            balance = [
                balance
                for balance in summary.spot_balances + summary.perp_balances
                if balance.product_id == product_id
            ][0]
            product = [
                product
                for product in summary.spot_products + summary.perp_products
                if product.product_id == product_id
            ][0]
        except Exception as e:
            raise Exception(f"Invalid product id provided {product_id}. Error: {e}")
        return SubaccountPosition(balance=balance, product=product)

    def get_assets(self) -> AssetsData:
        return ensure_data_type(self._query_v2(f"{self.url_v2}/assets"), list)

    def get_pairs(self, market_type: Optional[MarketType] = None) -> MarketPairsData:
        url = f"{self.url_v2}/pairs"
        if market_type is not None:
            url += f"?market={str(market_type)}"
        return ensure_data_type(self._query_v2(url), list)

    def get_spots_apr(self) -> SpotsAprData:
        return ensure_data_type(self._query_v2(f"{self.url_v2}/apr"), list)

    def get_orderbook(self, ticker_id: str, depth: int) -> Orderbook:
        return ensure_data_type(
            Orderbook.parse_obj(
                self._query_v2(
                    f"{self.url_v2}/orderbook?ticker_id={ticker_id}&depth={depth}"
                )
            ),
            Orderbook,
        )
