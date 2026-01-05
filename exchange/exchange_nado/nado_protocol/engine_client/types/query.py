from nado_protocol.utils.enum import StrEnum
from typing import Optional, Union
from pydantic import validator
from nado_protocol.utils.model import NadoBaseModel
from nado_protocol.engine_client.types.models import (
    ApplyDeltaTx,
    Asset,
    EngineStatus,
    IsolatedPosition,
    MarketPair,
    MaxOrderSizeDirection,
    ProductSymbol,
    ResponseStatus,
    SpotApr,
    SpotProduct,
    SubaccountHealth,
    SpotProductBalance,
    PerpProduct,
    SymbolData,
    PerpProductBalance,
    MarketLiquidity,
)


class EngineQueryType(StrEnum):
    """
    Enumeration of the different types of engine queries.
    """

    STATUS = "status"
    CONTRACTS = "contracts"
    NONCES = "nonces"
    ORDER = "order"
    SYMBOLS = "symbols"
    ALL_PRODUCTS = "all_products"
    FEE_RATES = "fee_rates"
    HEALTH_GROUPS = "health_groups"
    LINKED_SIGNER = "linked_signer"
    MARKET_LIQUIDITY = "market_liquidity"
    MARKET_PRICE = "market_price"
    MAX_ORDER_SIZE = "max_order_size"
    MAX_WITHDRAWABLE = "max_withdrawable"
    MAX_NLP_MINTABLE = "max_nlp_mintable"
    SUBACCOUNT_INFO = "subaccount_info"
    SUBACCOUNT_ORDERS = "subaccount_orders"
    ORDERS = "orders"
    ISOLATED_POSITIONS = "isolated_positions"


class QueryStatusParams(NadoBaseModel):
    """
    Parameters for querying the status of the engine.
    """

    type = EngineQueryType.STATUS.value


class QueryContractsParams(NadoBaseModel):
    """
    Parameters for querying the Nado contract addresses.
    """

    type = EngineQueryType.CONTRACTS.value


class QueryNoncesParams(NadoBaseModel):
    """
    Parameters for querying the nonces associated with a specific address.
    """

    type = EngineQueryType.NONCES.value
    address: str


class QueryOrderParams(NadoBaseModel):
    """
    Parameters for querying a specific order using its product_id and digest.
    """

    type = EngineQueryType.ORDER.value
    product_id: int
    digest: str


class QueryIsolatedPositionsParams(NadoBaseModel):
    """
    Parameters for querying the isolated positions of a specific subaccount.
    """

    type = EngineQueryType.ISOLATED_POSITIONS.value
    subaccount: str


QuerySubaccountInfoTx = Union[ApplyDeltaTx]


class QuerySubaccountInfoParams(NadoBaseModel):
    """
    Parameters for querying the subaccount summary from engine, including balances.
    """

    type = EngineQueryType.SUBACCOUNT_INFO.value
    subaccount: str
    txns: Optional[str]
    pre_state: Optional[str]


class QuerySubaccountOpenOrdersParams(NadoBaseModel):
    """
    Parameters for querying open orders associated with a subaccount for a specific product.
    """

    type = EngineQueryType.SUBACCOUNT_ORDERS.value
    product_id: int
    sender: str


class QuerySubaccountMultiProductOpenOrdersParams(NadoBaseModel):
    """
    Parameters for querying open orders associated with a subaccount for provided products.
    """

    type = EngineQueryType.ORDERS.value
    product_ids: list[int]
    sender: str


class QueryMarketLiquidityParams(NadoBaseModel):
    """
    Parameters for querying the market liquidity for a specific product up to a defined depth.
    """

    type = EngineQueryType.MARKET_LIQUIDITY.value
    product_id: int
    depth: int


class QuerySymbolsParams(NadoBaseModel):
    """
    Parameters for querying symbols and product info
    """

    type = EngineQueryType.SYMBOLS.value
    product_type: Optional[str]
    product_ids: Optional[list[int]]


class QueryAllProductsParams(NadoBaseModel):
    """
    Parameters for querying all products available in the engine.
    """

    type = EngineQueryType.ALL_PRODUCTS.value


class QueryMarketPriceParams(NadoBaseModel):
    """
    Parameters for querying the market price of a specific product.
    """

    type = EngineQueryType.MARKET_PRICE.value
    product_id: int


class SpotLeverageSerializerMixin(NadoBaseModel):
    spot_leverage: Optional[bool]

    @validator("spot_leverage")
    def spot_leverage_to_str(cls, v: Optional[bool]) -> Optional[str]:
        return str(v).lower() if v is not None else v


class QueryMaxOrderSizeParams(SpotLeverageSerializerMixin):
    """
    Parameters for querying the maximum order size for a specific product and a given sender.
    """

    type = EngineQueryType.MAX_ORDER_SIZE.value
    sender: str
    product_id: int
    price_x18: str
    direction: MaxOrderSizeDirection
    reduce_only: Optional[bool]
    isolated: Optional[bool]

    @validator("direction")
    def direction_to_str(cls, v: MaxOrderSizeDirection) -> str:
        return v.value

    @validator("reduce_only")
    def reduce_only_to_str(cls, v: Optional[bool]) -> Optional[str]:
        return str(v).lower() if v is not None else v

    @validator("isolated")
    def isolated_to_str(cls, v: Optional[bool]) -> Optional[str]:
        return str(v).lower() if v is not None else v


class QueryMaxWithdrawableParams(SpotLeverageSerializerMixin):
    """
    Parameters for querying the maximum withdrawable amount for a specific product and a given sender.
    """

    type = EngineQueryType.MAX_WITHDRAWABLE.value
    sender: str
    product_id: int


class QueryMaxLpMintableParams(SpotLeverageSerializerMixin):
    """
    Parameters for querying the maximum liquidity that can be minted by a specified sender for a specific product.
    """

    type = EngineQueryType.MAX_NLP_MINTABLE.value
    sender: str
    product_id: int


class QueryFeeRatesParams(NadoBaseModel):
    """
    Parameters for querying the fee rates associated with a specified sender.
    """

    type = EngineQueryType.FEE_RATES.value
    sender: str


class QueryHealthGroupsParams(NadoBaseModel):
    """
    Parameters for querying the health groups in the engine.
    """

    type = EngineQueryType.HEALTH_GROUPS.value


class QueryLinkedSignerParams(NadoBaseModel):
    """
    Parameters for querying the signer linked to a specified subaccount.
    """

    type = EngineQueryType.LINKED_SIGNER.value
    subaccount: str


QueryRequest = Union[
    QueryStatusParams,
    QueryContractsParams,
    QueryNoncesParams,
    QueryOrderParams,
    QuerySubaccountInfoParams,
    QuerySubaccountOpenOrdersParams,
    QuerySubaccountMultiProductOpenOrdersParams,
    QueryMarketLiquidityParams,
    QuerySymbolsParams,
    QueryAllProductsParams,
    QueryMarketPriceParams,
    QueryMaxOrderSizeParams,
    QueryMaxWithdrawableParams,
    QueryMaxLpMintableParams,
    QueryFeeRatesParams,
    QueryHealthGroupsParams,
    QueryLinkedSignerParams,
    QueryIsolatedPositionsParams,
]

StatusData = EngineStatus


class ContractsData(NadoBaseModel):
    """
    Data model for Nado's contract addresses.
    """

    chain_id: str
    endpoint_addr: str


class NoncesData(NadoBaseModel):
    """
    Data model for nonce values for transactions and orders.
    """

    tx_nonce: str
    order_nonce: str


class OrderData(NadoBaseModel):
    """
    Data model for details of an order.
    """

    product_id: int
    sender: str
    price_x18: str
    amount: str
    expiration: str
    nonce: str
    unfilled_amount: str
    digest: str
    placed_at: str


class PreState(NadoBaseModel):
    """
    Model for subaccount state before simulated transactions were applied.
    """

    healths: list[SubaccountHealth]
    health_contributions: list[list[str]]
    spot_balances: list[SpotProductBalance]
    perp_balances: list[PerpProductBalance]


class SubaccountInfoData(NadoBaseModel):
    """
    Model for detailed info about a subaccount, including balances.
    """

    subaccount: str
    exists: bool
    healths: list[SubaccountHealth]
    health_contributions: list[list[str]]
    spot_count: int
    perp_count: int
    spot_balances: list[SpotProductBalance]
    perp_balances: list[PerpProductBalance]
    spot_products: list[SpotProduct]
    perp_products: list[PerpProduct]
    pre_state: Optional[PreState]

    def parse_subaccount_balance(
        self, product_id: int
    ) -> Union[SpotProductBalance, PerpProductBalance]:
        """
        Parses the balance of a subaccount for a given product.

        Args:
            product_id (int): The ID of the product to lookup.

        Returns:
            Union[SpotProductBalance, PerpProductBalance]: The balance of the product in the subaccount.

        Raises:
            ValueError: If the product ID provided is not found.
        """
        for spot_balance in self.spot_balances:
            if spot_balance.product_id == product_id:
                return spot_balance

        for perp_balance in self.perp_balances:
            if perp_balance.product_id == product_id:
                return perp_balance

        raise ValueError(f"Invalid product id provided: {product_id}")


class IsolatedPositionsData(NadoBaseModel):
    """
    Data model for isolated positions of a subaccount.
    """

    isolated_positions: list[IsolatedPosition]


class SubaccountOpenOrdersData(NadoBaseModel):
    """
        Data model encapsulating open orders of a subaccount for a
    specific product.
    """

    sender: str
    orders: list[OrderData]


class ProductOpenOrdersData(NadoBaseModel):
    """
    Data model encapsulating open orders for a product.
    """

    product_id: int
    orders: list[OrderData]


class SubaccountMultiProductsOpenOrdersData(NadoBaseModel):
    """
    Data model encapsulating open orders of a subaccount across multiple products.
    """

    sender: str
    product_orders: list[ProductOpenOrdersData]


class MarketLiquidityData(NadoBaseModel):
    """
    Data model for market liquidity details.
    """

    bids: list[MarketLiquidity]
    asks: list[MarketLiquidity]
    timestamp: str


class AllProductsData(NadoBaseModel):
    """
    Data model for all the products available.
    """

    spot_products: list[SpotProduct]
    perp_products: list[PerpProduct]


class MarketPriceData(NadoBaseModel):
    """
    Data model for the bid and ask prices of a specific product.
    """

    product_id: int
    bid_x18: str
    ask_x18: str


class MaxOrderSizeData(NadoBaseModel):
    """
    Data model for the maximum order size.
    """

    max_order_size: str


class MaxWithdrawableData(NadoBaseModel):
    """
    Data model for the maximum withdrawable amount.
    """

    max_withdrawable: str


class MaxLpMintableData(NadoBaseModel):
    """
    Data model for the maximum liquidity that can be minted.
    """

    max_base_amount: str
    max_quote_amount: str


class FeeRatesData(NadoBaseModel):
    """
    Data model for various fee rates associated with transactions.
    """

    taker_fee_rates_x18: list[str]
    maker_fee_rates_x18: list[str]
    liquidation_sequencer_fee: str
    health_check_sequencer_fee: str
    taker_sequencer_fee: str
    withdraw_sequencer_fees: list[str]


class HealthGroupsData(NadoBaseModel):
    """
    Data model for health group IDs.
    """

    health_groups: list[list[int]]


class LinkedSignerData(NadoBaseModel):
    """
    Data model for the signer linked to a subaccount.
    """

    linked_signer: str


class SymbolsData(NadoBaseModel):
    """
    Data model for the symbols product info
    """

    symbols: dict[str, SymbolData]


ProductSymbolsData = list[ProductSymbol]

QueryResponseData = Union[
    StatusData,
    ContractsData,
    NoncesData,
    OrderData,
    SubaccountInfoData,
    SubaccountOpenOrdersData,
    SubaccountMultiProductsOpenOrdersData,
    MarketLiquidityData,
    SymbolsData,
    AllProductsData,
    MarketPriceData,
    MaxOrderSizeData,
    MaxWithdrawableData,
    MaxLpMintableData,
    FeeRatesData,
    HealthGroupsData,
    LinkedSignerData,
    ProductSymbolsData,
    IsolatedPositionsData,
]


class QueryResponse(NadoBaseModel):
    """
    Represents a response to a query request.

    Attributes:
        status (ResponseStatus): The status of the query response.

        data (Optional[QueryResponseData]): The data returned from the query, or an error message if the query failed.

        error (Optional[str]): The error message, if any error occurred during the query.

        error_code (Optional[int]): The error code, if any error occurred during the query.

        request_type (Optional[str]): Type of the request.
    """

    status: ResponseStatus
    data: Optional[QueryResponseData]
    error: Optional[str]
    error_code: Optional[int]
    request_type: Optional[str]


AssetsData = list[Asset]

MarketPairsData = list[MarketPair]

SpotsAprData = list[SpotApr]
