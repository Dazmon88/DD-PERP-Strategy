from typing import Optional, Union, List
from nado_protocol.utils.model import NadoBaseModel


class OraclePriceAbove(NadoBaseModel):
    oracle_price_above: str


class OraclePriceBelow(NadoBaseModel):
    oracle_price_below: str


class LastPriceAbove(NadoBaseModel):
    last_price_above: str


class LastPriceBelow(NadoBaseModel):
    last_price_below: str


class MidPriceAbove(NadoBaseModel):
    mid_price_above: str


class MidPriceBelow(NadoBaseModel):
    mid_price_below: str


PriceRequirement = Union[
    OraclePriceAbove,
    OraclePriceBelow,
    LastPriceAbove,
    LastPriceBelow,
    MidPriceAbove,
    MidPriceBelow,
]


class Dependency(NadoBaseModel):
    digest: str
    on_partial_fill: bool


class PriceTriggerData(NadoBaseModel):
    price_requirement: PriceRequirement
    dependency: Optional[Dependency] = None


class TimeTriggerData(NadoBaseModel):
    """Time-based trigger for TWAP orders."""

    interval: int  # interval in seconds between executions
    amounts: Optional[List[str]] = None  # optional custom amounts per execution


class PriceTrigger(NadoBaseModel):
    price_trigger: PriceTriggerData


class TimeTrigger(NadoBaseModel):
    time_trigger: TimeTriggerData


TriggerCriteria = Union[PriceTrigger, TimeTrigger]


class OrderData(NadoBaseModel):
    sender: str
    priceX18: str
    amount: str
    expiration: str
    nonce: str


class TriggerOrderData(NadoBaseModel):
    """
    Data model for details of a trigger order.
    """

    product_id: int
    order: OrderData
    signature: str
    spot_leverage: Optional[bool]
    digest: Optional[str]
    trigger: TriggerCriteria
