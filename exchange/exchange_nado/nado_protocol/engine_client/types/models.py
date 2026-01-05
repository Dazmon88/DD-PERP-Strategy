from typing import Optional, Union
from typing import Annotated
from nado_protocol.utils.enum import StrEnum
from nado_protocol.utils.model import NadoBaseModel
from pydantic import conlist


class ResponseStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class EngineStatus(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"


class ApplyDelta(NadoBaseModel):
    product_id: int
    subaccount: str
    amount_delta: str
    v_quote_delta: str


class ApplyDeltaTx(NadoBaseModel):
    apply_delta: ApplyDelta


class SubaccountHealth(NadoBaseModel):
    assets: str
    liabilities: str
    health: str


class SpotBalance(NadoBaseModel):
    amount: str


class SpotProductBalance(NadoBaseModel):
    product_id: int
    balance: SpotBalance


class PerpBalance(NadoBaseModel):
    amount: str
    v_quote_balance: str
    last_cumulative_funding_x18: str


class PerpProductBalance(NadoBaseModel):
    product_id: int
    balance: PerpBalance


class ProductRisk(NadoBaseModel):
    long_weight_initial_x18: str
    short_weight_initial_x18: str
    long_weight_maintenance_x18: str
    short_weight_maintenance_x18: str
    price_x18: str


class ProductBookInfo(NadoBaseModel):
    size_increment: str
    price_increment_x18: str
    min_size: str
    collected_fees: str


class BaseProduct(NadoBaseModel):
    product_id: int
    oracle_price_x18: str
    risk: ProductRisk
    book_info: ProductBookInfo


class SpotProductConfig(NadoBaseModel):
    token: str
    interest_inflection_util_x18: str
    interest_floor_x18: str
    interest_small_cap_x18: str
    interest_large_cap_x18: str
    withdraw_fee_x18: str
    min_deposit_rate_x18: str


class SpotProductState(NadoBaseModel):
    cumulative_deposits_multiplier_x18: str
    cumulative_borrows_multiplier_x18: str
    total_deposits_normalized: str
    total_borrows_normalized: str


class SpotProduct(BaseProduct):
    config: SpotProductConfig
    state: SpotProductState


class PerpProductState(NadoBaseModel):
    cumulative_funding_long_x18: str
    cumulative_funding_short_x18: str
    available_settle: str
    open_interest: str


class PerpProduct(BaseProduct):
    state: PerpProductState


class MaxOrderSizeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class ProductSymbol(NadoBaseModel):
    product_id: int
    symbol: str


class SymbolData(NadoBaseModel):
    type: str
    product_id: str
    symbol: str
    price_increment_x18: str
    size_increment: str
    min_size: str
    maker_fee_rate_x18: str
    taker_fee_rate_x18: str
    long_weight_initial_x18: str
    long_weight_maintenance_x18: str
    max_open_interest_x18: Optional[str]


class SubaccountPosition(NadoBaseModel):
    balance: Union[PerpProductBalance, SpotProductBalance]
    product: Union[PerpProduct, SpotProduct]


# (price, amount)
MarketLiquidity = Annotated[list, conlist(str, min_items=2, max_items=2)]


class Asset(NadoBaseModel):
    product_id: int
    ticker_id: Optional[str]
    market_type: Optional[str]
    name: str
    symbol: str
    maker_fee: Optional[float]
    taker_fee: Optional[float]
    can_withdraw: bool
    can_deposit: bool


class MarketPair(NadoBaseModel):
    ticker_id: str
    base: str
    quote: str


class SpotApr(NadoBaseModel):
    name: str
    symbol: str
    product_id: int
    deposit_apr: float
    borrow_apr: float
    tvl: float


class Orderbook(NadoBaseModel):
    ticker_id: str
    timestamp: int
    bids: list[MarketLiquidity]
    asks: list[MarketLiquidity]


class MarketType(StrEnum):
    SPOT = "spot"
    PERP = "perp"


class IsolatedPosition(NadoBaseModel):
    subaccount: str
    quote_balance: SpotProductBalance
    base_balance: PerpProductBalance
    quote_product: SpotProduct
    base_product: PerpProduct
    healths: list[SubaccountHealth]
    quote_healths: list
    base_healths: list
