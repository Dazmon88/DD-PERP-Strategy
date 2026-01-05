from enum import IntEnum
from nado_protocol.utils.enum import StrEnum

from typing import Any, Optional, Union
from nado_protocol.engine_client.types.models import (
    PerpProduct,
    PerpProductBalance,
    SpotProduct,
    SpotProductBalance,
)

from nado_protocol.utils.model import NadoBaseModel


class IndexerEventType(StrEnum):
    LIQUIDATE_SUBACCOUNT = "liquidate_subaccount"
    DEPOSIT_COLLATERAL = "deposit_collateral"
    WITHDRAW_COLLATERAL = "withdraw_collateral"
    SETTLE_PNL = "settle_pnl"
    MATCH_ORDERS = "match_orders"
    MATCH_ORDER_A_M_M = "match_order_a_m_m"
    SWAP_AMM = "swap_a_m_m"
    MINT_NLP = "mint_nlp"
    BURN_NLP = "burn_nlp"
    MANUAL_ASSERT = "manual_assert"
    LINK_SIGNER = "link_signer"
    TRANSFER_QUOTE = "transfer_quote"
    CREATE_ISOLATED_SUBACCOUNT = "create_isolated_subaccount"


class IndexerCandlesticksGranularity(IntEnum):
    ONE_MINUTE = 60
    FIVE_MINUTES = 300
    FIFTEEN_MINUTES = 900
    ONE_HOUR = 3600
    TWO_HOURS = 7200
    FOUR_HOURS = 14400
    ONE_DAY = 86400
    ONE_WEEK = 604800
    FOUR_WEEKS = 2419200


class IndexerBaseModel(NadoBaseModel):
    submission_idx: str
    timestamp: Optional[str]


class IndexerBaseOrder(NadoBaseModel):
    sender: str
    priceX18: str
    amount: str
    expiration: Union[str, int]
    nonce: Union[str, int]


class IndexerOrderFill(IndexerBaseModel):
    digest: str
    base_filled: str
    quote_filled: str
    fee: str


class IndexerHistoricalOrder(IndexerOrderFill):
    subaccount: str
    product_id: int
    amount: str
    price_x18: str
    expiration: str
    nonce: str
    isolated: bool


class IndexerSignedOrder(NadoBaseModel):
    order: IndexerBaseOrder
    signature: str


class IndexerMatch(IndexerOrderFill):
    order: IndexerBaseOrder
    cumulative_fee: str
    cumulative_base_filled: str
    cumulative_quote_filled: str
    isolated: bool


class IndexerMatchOrdersTxData(NadoBaseModel):
    product_id: int
    amm: bool
    taker: IndexerSignedOrder
    maker: IndexerSignedOrder


class IndexerMatchOrdersTx(NadoBaseModel):
    match_orders: IndexerMatchOrdersTxData


class IndexerWithdrawCollateralTxData(NadoBaseModel):
    sender: str
    product_id: int
    amount: str
    nonce: int


class IndexerWithdrawCollateralTx(NadoBaseModel):
    withdraw_collateral: IndexerWithdrawCollateralTxData


class IndexerLiquidateSubaccountTxData(NadoBaseModel):
    sender: str
    liquidatee: str
    mode: int
    health_group: int
    amount: str
    nonce: int


class IndexerLiquidateSubaccountTx(NadoBaseModel):
    liquidate_subaccount: IndexerLiquidateSubaccountTxData


class IndexerMintNlpTxData(NadoBaseModel):
    sender: str
    quote_amount: str
    nonce: int


class IndexerMintNlpTx(NadoBaseModel):
    mint_nlp: IndexerMintNlpTxData


class IndexerBurnNlpTxData(NadoBaseModel):
    sender: str
    nlp_amount: str
    nonce: int


class IndexerBurnNlpTx(NadoBaseModel):
    burn_nlp: IndexerBurnNlpTxData


IndexerTxData = Union[
    IndexerMatchOrdersTx,
    IndexerWithdrawCollateralTx,
    IndexerLiquidateSubaccountTx,
    IndexerMintNlpTx,
    IndexerBurnNlpTx,
]


class IndexerTx(IndexerBaseModel):
    tx: Union[IndexerTxData, Any]


class IndexerSpotProductBalanceData(NadoBaseModel):
    spot: SpotProductBalance


class IndexerPerpProductBalanceData(NadoBaseModel):
    perp: PerpProductBalance


IndexerProductBalanceData = Union[
    IndexerSpotProductBalanceData, IndexerPerpProductBalanceData
]


class IndexerSpotProductData(NadoBaseModel):
    spot: SpotProduct


class IndexerPerpProductData(NadoBaseModel):
    perp: PerpProduct


IndexerProductData = Union[IndexerSpotProductData, IndexerPerpProductData]


class IndexerEventTrackedData(NadoBaseModel):
    net_interest_unrealized: str
    net_interest_cumulative: str
    net_funding_unrealized: str
    net_funding_cumulative: str
    net_entry_unrealized: str
    net_entry_cumulative: str
    quote_volume_cumulative: str


class IndexerEvent(IndexerBaseModel, IndexerEventTrackedData):
    subaccount: str
    product_id: int
    event_type: IndexerEventType
    product: IndexerProductData
    pre_balance: IndexerProductBalanceData
    post_balance: IndexerProductBalanceData
    isolated: bool
    isolated_product_id: Optional[int]


class IndexerProduct(IndexerBaseModel):
    product_id: int
    product: IndexerProductData


class IndexerMarketSnapshot(NadoBaseModel):
    timestamp: int
    cumulative_users: int
    daily_active_users: int
    tvl: str

    # product_id -> cumulative_metric
    cumulative_trades: dict
    cumulative_volumes: dict
    cumulative_trade_sizes: dict
    cumulative_sequencer_fees: dict
    cumulative_maker_fees: dict
    cumulative_liquidation_amounts: dict
    open_interests: dict
    total_deposits: dict
    total_borrows: dict
    funding_rates: dict
    deposit_rates: dict
    borrow_rates: dict
    cumulative_inflows: dict
    cumulative_outflows: dict


class IndexerCandlestick(IndexerBaseModel):
    product_id: int
    granularity: int
    open_x18: str
    high_x18: str
    low_x18: str
    close_x18: str
    volume: str


class IndexerOraclePrice(NadoBaseModel):
    product_id: int
    oracle_price_x18: str
    update_time: str


class IndexerAddressReward(NadoBaseModel):
    product_id: int
    q_score: str
    sum_q_min: str
    uptime: int
    maker_volume: str
    taker_volume: str
    maker_fee: str
    taker_fee: str
    maker_tokens: str
    taker_tokens: str
    taker_referral_tokens: str
    rebates: str


class IndexerGlobalRewards(NadoBaseModel):
    product_id: int
    reward_coefficient: str
    q_scores: str
    maker_volumes: str
    taker_volumes: str
    maker_fees: str
    taker_fees: str
    maker_tokens: str
    taker_tokens: str


class IndexerTokenReward(NadoBaseModel):
    epoch: int
    start_time: str
    period: str
    address_rewards: list[IndexerAddressReward]
    global_rewards: list[IndexerGlobalRewards]


class IndexerMarketMakerData(NadoBaseModel):
    timestamp: str
    maker_fee: str
    uptime: str
    sum_q_min: str
    q_score: str
    maker_share: str
    expected_maker_reward: str


class IndexerMarketMaker(NadoBaseModel):
    address: str
    data: list[IndexerMarketMakerData]


class IndexerLiquidatableAccount(NadoBaseModel):
    subaccount: str
    update_time: int


class IndexerSubaccount(NadoBaseModel):
    id: str
    subaccount: str
    address: str
    subaccount_name: str
    created_at: str
    isolated: bool


class IndexerMerkleProof(NadoBaseModel):
    total_amount: str
    proof: list[str]


class IndexerPayment(NadoBaseModel):
    product_id: int
    idx: str
    timestamp: str
    amount: str
    balance_amount: str
    rate_x18: str
    oracle_price_x18: str


class IndexerTickerInfo(NadoBaseModel):
    ticker_id: str
    base_currency: str
    quote_currency: str
    last_price: float
    base_volume: float
    quote_volume: float
    price_change_percent_24h: float


class IndexerPerpContractInfo(IndexerTickerInfo):
    product_type: str
    contract_price: float
    contract_price_currency: str
    open_interest: float
    open_interest_usd: float
    index_price: float
    mark_price: float
    funding_rate: float
    next_funding_rate_timestamp: int


class IndexerTradeInfo(NadoBaseModel):
    ticker_id: str
    # submission_idx
    trade_id: int
    price: float
    base_filled: float
    quote_filled: float
    timestamp: int
    # side
    trade_type: str


class MarketType(StrEnum):
    SPOT = "spot"
    PERP = "perp"
