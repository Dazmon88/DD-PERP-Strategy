"""
Margin Manager - Comprehensive margin calculations for Nado Protocol.

This module calculates all margin-related metrics including health, margin usage,
leverage, and position-level details. All calculations use oracle prices.

Key Concepts:
- Health Types: Initial (strictest), Maintenance (liquidation), Unweighted (raw)
- Cross Margin: Shared across all positions
- Isolated Margin: Dedicated per position (perp only, USDT only)
- Health = Assets - Liabilities, calculated per balance using oracle_price * weight
"""

from decimal import Decimal
from time import time
from typing import Optional, Union, TYPE_CHECKING
from pydantic import BaseModel
from nado_protocol.engine_client.types.models import (
    SpotProduct,
    PerpProduct,
    SpotProductBalance,
    PerpProductBalance,
    SubaccountHealth,
    IsolatedPosition,
)
from nado_protocol.engine_client.types.query import SubaccountInfoData
from nado_protocol.indexer_client.types.models import IndexerEvent
from nado_protocol.indexer_client.types.query import IndexerAccountSnapshotsParams
from nado_protocol.utils.bytes32 import subaccount_to_hex

if TYPE_CHECKING:
    from nado_protocol.client import NadoClient


TEN_TO_18 = Decimal(10) ** 18


def _from_x18_decimal(value: Union[int, str]) -> Decimal:
    """Convert an x18 fixed-point integer (str or int) to Decimal without precision loss."""
    return Decimal(str(value)) / TEN_TO_18


class HealthMetrics(BaseModel):
    """Initial and maintenance health metrics."""

    initial: Decimal
    maintenance: Decimal


class MarginUsageFractions(BaseModel):
    """Margin usage as a fraction [0, 1]."""

    initial: Decimal
    maintenance: Decimal


class BalanceWithProduct(BaseModel):
    """Balance combined with its product information."""

    product_id: int
    amount: Decimal
    oracle_price: Decimal
    long_weight_initial: Decimal
    long_weight_maintenance: Decimal
    short_weight_initial: Decimal
    short_weight_maintenance: Decimal
    balance_type: str  # "spot" or "perp"
    v_quote_balance: Optional[Decimal] = None

    class Config:
        arbitrary_types_allowed = True


class CrossPositionMetrics(BaseModel):
    """Metrics for a cross margin position."""

    product_id: int
    symbol: str
    position_size: Decimal
    notional_value: Decimal
    est_pnl: Optional[Decimal]  # Estimated PnL (requires indexer data)
    unsettled: Decimal  # Unsettled quote (v_quote_balance)
    margin_used: Decimal
    initial_health: Decimal
    maintenance_health: Decimal
    long_weight_initial: Decimal
    long_weight_maintenance: Decimal
    short_weight_initial: Decimal
    short_weight_maintenance: Decimal

    class Config:
        arbitrary_types_allowed = True


class IsolatedPositionMetrics(BaseModel):
    """Metrics for an isolated margin position."""

    product_id: int
    symbol: str
    position_size: Decimal
    notional_value: Decimal
    net_margin: Decimal
    leverage: Decimal
    initial_health: Decimal
    maintenance_health: Decimal

    class Config:
        arbitrary_types_allowed = True


class AccountSummary(BaseModel):
    """Complete account margin summary."""

    # Overall health
    initial_health: Decimal
    maintenance_health: Decimal
    unweighted_health: Decimal

    # Margin usage [0, 1]
    margin_usage_fraction: Decimal
    maint_margin_usage_fraction: Decimal

    # Available margins
    funds_available: Decimal
    funds_until_liquidation: Decimal

    # Portfolio metrics
    portfolio_value: Decimal
    account_leverage: Decimal

    # Positions
    cross_positions: list[CrossPositionMetrics]
    isolated_positions: list[IsolatedPositionMetrics]
    spot_positions: list[BalanceWithProduct]

    # Spot balances
    total_spot_deposits: Decimal
    total_spot_borrows: Decimal

    class Config:
        arbitrary_types_allowed = True


class MarginManager:
    """
    Comprehensive margin calculator for Nado Protocol.

    Calculates all margin metrics for a subaccount including health, margin usage,
    leverage, and position-level details. Matches TypeScript SDK implementation.
    """

    QUOTE_PRODUCT_ID = 0  # USDT product ID

    def __init__(
        self,
        subaccount_info: SubaccountInfoData,
        isolated_positions: Optional[list[IsolatedPosition]] = None,
        indexer_snapshot_events: Optional[list[IndexerEvent]] = None,
    ):
        """
        Initialize margin manager with subaccount data.

        Args:
            subaccount_info: Subaccount information from engine
            isolated_positions: List of isolated positions (if any)
            indexer_snapshot_events: Optional indexer events for Est. PnL calculations
        """
        self.subaccount_info = subaccount_info
        self.isolated_positions = isolated_positions or []
        self.indexer_events = indexer_snapshot_events or []

    @classmethod
    def from_client(
        cls,
        client: "NadoClient",
        *,
        subaccount: Optional[str] = None,
        subaccount_name: str = "default",
        include_indexer_events: bool = True,
        snapshot_timestamp: Optional[int] = None,
        snapshot_isolated: Optional[bool] = False,
        snapshot_active_only: bool = True,
    ) -> "MarginManager":
        """
        Initialize a MarginManager by fetching data via a NadoClient.

        Args:
            client: Configured Nado client with engine/indexer connectivity.
            subaccount: Optional subaccount hex (bytes32). If omitted, derives the default
                subaccount using the client's signer and ``subaccount_name``.
            subaccount_name: Subaccount suffix (e.g. ``default``) used when deriving the
                subaccount hex. Ignored when ``subaccount`` is provided.
            include_indexer_events: When True (default), fetch indexer snapshot balances
                for estimated PnL calculations.
            snapshot_timestamp: Epoch seconds to request from the indexer. Defaults to
                ``int(time.time())`` when indexer data is requested.
            snapshot_isolated: Passed through to the indexer request to limit snapshots
                to isolated (True), cross (False), or all (None) balances. Defaults to
                ``False`` to match cross-margin behaviour.
            snapshot_active_only: When True (default), enables the indexer's ``active``
                filter so only live balances are returned.

        Returns:
            MarginManager instance populated with fresh engine and optional indexer data.
        """

        engine_client = client.context.engine_client

        resolved_subaccount = subaccount
        if resolved_subaccount is None:
            signer = client.context.signer
            if signer is None:
                raise ValueError(
                    "subaccount must be provided when the client has no signer"
                )
            resolved_subaccount = subaccount_to_hex(signer.address, subaccount_name)

        subaccount_info = engine_client.get_subaccount_info(resolved_subaccount)
        isolated_positions_data = engine_client.get_isolated_positions(
            resolved_subaccount
        )
        isolated_positions = isolated_positions_data.isolated_positions

        indexer_events: list[IndexerEvent] = []
        if include_indexer_events:
            requested_timestamp = snapshot_timestamp or int(time())
            indexer_events = cls._fetch_snapshot_events(
                client,
                resolved_subaccount,
                requested_timestamp,
                snapshot_isolated,
                snapshot_active_only,
            )

        return cls(
            subaccount_info,
            isolated_positions,
            indexer_snapshot_events=indexer_events,
        )

    @staticmethod
    def _fetch_snapshot_events(
        client: "NadoClient",
        subaccount: str,
        timestamp: int,
        isolated: Optional[bool],
        active_only: bool,
    ) -> list[IndexerEvent]:
        snapshot_response = (
            client.context.indexer_client.get_multi_subaccount_snapshots(
                IndexerAccountSnapshotsParams(
                    subaccounts=[subaccount],
                    timestamps=[timestamp],
                    isolated=isolated,
                    active=active_only,
                )
            )
        )

        snapshots_map = snapshot_response.snapshots or {}
        if not snapshots_map:
            return []

        snapshots_for_subaccount = snapshots_map.get(subaccount) or next(
            iter(snapshots_map.values())
        )
        if not snapshots_for_subaccount:
            return []

        latest_key = max(snapshots_for_subaccount.keys(), key=int)
        events = snapshots_for_subaccount.get(latest_key, [])
        return list(events) if events else []

    def calculate_account_summary(self) -> AccountSummary:
        """
        Calculate complete account margin summary.

        Returns:
            AccountSummary with all margin calculations
        """
        # Parse health from subaccount info
        # healths is a list: [initial, maintenance, unweighted]
        initial_health = self._parse_health(self.subaccount_info.healths[0])
        maint_health = self._parse_health(self.subaccount_info.healths[1])
        unweighted_health = self._parse_health(self.subaccount_info.healths[2])

        # Calculate margin usage
        margin_usage = self.calculate_margin_usage_fractions(
            initial_health, maint_health, unweighted_health
        )

        # Process all balances
        spot_balances = self._create_spot_balances()
        perp_balances = self._create_perp_balances()

        # Calculate cross position metrics
        cross_positions: list[CrossPositionMetrics] = []
        for balance in perp_balances:
            if balance.amount != 0:
                cross_metric = self.calculate_cross_position_metrics(balance)
                cross_positions.append(cross_metric)

        # Calculate isolated position metrics
        isolated_position_metrics: list[IsolatedPositionMetrics] = []
        total_iso_net_margin = Decimal(0)
        for iso_pos in self.isolated_positions:
            isolated_metric = self.calculate_isolated_position_metrics(iso_pos)
            isolated_position_metrics.append(isolated_metric)
            total_iso_net_margin += isolated_metric.net_margin

        # Calculate spot metrics
        total_deposits = Decimal(0)
        total_borrows = Decimal(0)
        for balance in spot_balances:
            value = self.calculate_spot_balance_value(balance)
            if value > 0:
                total_deposits += value
            else:
                total_borrows += abs(value)

        # Calculate leverage
        leverage = self.calculate_account_leverage(
            spot_balances + perp_balances, unweighted_health
        )

        # Portfolio value = cross value + isolated net margins
        portfolio_value = unweighted_health + total_iso_net_margin

        return AccountSummary(
            initial_health=initial_health,
            maintenance_health=maint_health,
            unweighted_health=unweighted_health,
            margin_usage_fraction=margin_usage.initial,
            maint_margin_usage_fraction=margin_usage.maintenance,
            funds_available=max(Decimal(0), initial_health),
            funds_until_liquidation=max(Decimal(0), maint_health),
            portfolio_value=portfolio_value,
            account_leverage=leverage,
            cross_positions=cross_positions,
            isolated_positions=isolated_position_metrics,
            spot_positions=spot_balances,
            total_spot_deposits=total_deposits,
            total_spot_borrows=total_borrows,
        )

    def calculate_spot_balance_value(self, balance: BalanceWithProduct) -> Decimal:
        """
        Calculate quote value of a spot balance.

        Formula: amount * oracle_price
        """
        return balance.amount * balance.oracle_price

    def calculate_perp_balance_notional_value(
        self, balance: BalanceWithProduct
    ) -> Decimal:
        """
        Calculate notional value of a perp position.

        Formula: abs(amount * oracle_price)
        """
        return abs(balance.amount * balance.oracle_price)

    def calculate_perp_balance_value(self, balance: BalanceWithProduct) -> Decimal:
        """
        Calculate true quote value of a perp balance (unrealized PnL).

        Formula: (amount * oracle_price) + v_quote_balance
        """
        if balance.v_quote_balance is None:
            raise ValueError("Perp balance must have v_quote_balance")
        return (balance.amount * balance.oracle_price) + balance.v_quote_balance

    def calculate_spot_balance_health(
        self, balance: BalanceWithProduct
    ) -> HealthMetrics:
        """
        Calculate health contribution for a spot balance.

        Formula: amount * oracle_price * weight
        (weight is long_weight if amount >= 0, else short_weight)
        """
        weights = self._get_health_weights(balance)
        value = balance.amount * balance.oracle_price

        return HealthMetrics(
            initial=value * weights.initial, maintenance=value * weights.maintenance
        )

    def calculate_perp_balance_health_without_pnl(
        self, balance: BalanceWithProduct
    ) -> HealthMetrics:
        """
        Calculate perp balance health WITHOUT the impact of unsettled PnL.

        Shows "margin used" by the position, excluding PnL.
        Formula: -1 * abs(notional_value) * (1 - long_weight)
        """
        initial_leverage_adjustment = Decimal(1) - balance.long_weight_initial
        maint_leverage_adjustment = Decimal(1) - balance.long_weight_maintenance

        base_margin_value = abs(balance.amount) * balance.oracle_price

        return HealthMetrics(
            initial=base_margin_value * initial_leverage_adjustment * Decimal(-1),
            maintenance=base_margin_value * maint_leverage_adjustment * Decimal(-1),
        )

    def calculate_cross_position_margin_without_pnl(
        self, balance: BalanceWithProduct
    ) -> Decimal:
        """
        Calculate margin used for a cross position excluding unsettled PnL impact.

        Used in margin manager "Margin Used" column.
        Formula: max(0, -(initial_health - perp_value))
        """
        health_with_pnl = self.calculate_spot_balance_health(balance).initial
        perp_value = self.calculate_perp_balance_value(balance)

        without_unsettled_pnl = health_with_pnl - perp_value
        return max(Decimal(0), -without_unsettled_pnl)

    def calculate_isolated_position_net_margin(
        self, base_balance: BalanceWithProduct, quote_balance: BalanceWithProduct
    ) -> Decimal:
        """
        Calculate net margin in an isolated position.

        Formula: quote_amount + (base_amount * oracle_price + v_quote_balance)
        """
        total_margin = quote_balance.amount
        unsettled_quote = self.calculate_perp_balance_value(base_balance)
        return total_margin + unsettled_quote

    def calculate_isolated_position_leverage(
        self, base_balance: BalanceWithProduct, net_margin: Decimal
    ) -> Decimal:
        """
        Calculate leverage for an isolated position.

        Formula: notional_value / net_margin
        """
        if net_margin == 0:
            return Decimal(0)

        notional_value = self.calculate_perp_balance_notional_value(base_balance)
        return notional_value / net_margin

    def calculate_margin_usage_fractions(
        self, initial_health: Decimal, maint_health: Decimal, unweighted_health: Decimal
    ) -> MarginUsageFractions:
        """
        Calculate margin usage fractions bounded to [0, 1].

        Formula: (unweighted_health - health) / unweighted_health
        Returns 0 if no borrows/perps or unweighted_health is 0.
        """
        if unweighted_health == 0:
            return MarginUsageFractions(initial=Decimal(0), maintenance=Decimal(0))

        if not self._has_borrows_or_perps():
            return MarginUsageFractions(initial=Decimal(0), maintenance=Decimal(0))

        initial_usage = (unweighted_health - initial_health) / unweighted_health
        maint_usage = (unweighted_health - maint_health) / unweighted_health

        # If health is negative, max out margin usage
        return MarginUsageFractions(
            initial=(
                Decimal(1) if initial_health < 0 else min(initial_usage, Decimal(1))
            ),
            maintenance=(
                Decimal(1) if maint_health < 0 else min(maint_usage, Decimal(1))
            ),
        )

    def calculate_account_leverage(
        self, balances: list[BalanceWithProduct], unweighted_health: Decimal
    ) -> Decimal:
        """
        Calculate overall account leverage.

        Formula: sum(abs(unweighted health for non-quote balances)) / unweighted_health
        """
        if unweighted_health == 0:
            return Decimal(0)

        if not self._has_borrows_or_perps():
            return Decimal(0)

        numerator = Decimal(0)
        for balance in balances:
            if balance.product_id == self.QUOTE_PRODUCT_ID:
                continue

            if self._is_zero_health(balance):
                continue

            if balance.balance_type == "spot":
                value = abs(balance.amount * balance.oracle_price)
            else:
                value = self.calculate_perp_balance_notional_value(balance)

            numerator += value

        return numerator / unweighted_health

    def calculate_cross_position_metrics(
        self, balance: BalanceWithProduct
    ) -> CrossPositionMetrics:
        """Calculate all metrics for a cross margin position."""
        notional = self.calculate_perp_balance_notional_value(balance)
        health_metrics = self.calculate_spot_balance_health(balance)
        margin_used = abs(
            self.calculate_perp_balance_health_without_pnl(balance).initial
        )

        # Unsettled = full perp balance value (amount × oracle_price + v_quote_balance)
        # This represents the unrealized PnL
        unsettled = self.calculate_perp_balance_value(balance)

        # Calculate Est. PnL if indexer data is available
        # Formula: (amount × oracle_price) - netEntryUnrealized
        # where netEntryUnrealized excludes funding, fees, slippage
        est_pnl = self._calculate_est_pnl(balance)

        return CrossPositionMetrics(
            product_id=balance.product_id,
            symbol=f"Product_{balance.product_id}",
            position_size=balance.amount,
            notional_value=notional,
            est_pnl=est_pnl,
            unsettled=unsettled,
            margin_used=margin_used,
            initial_health=health_metrics.initial,
            maintenance_health=health_metrics.maintenance,
            long_weight_initial=balance.long_weight_initial,
            long_weight_maintenance=balance.long_weight_maintenance,
            short_weight_initial=balance.short_weight_initial,
            short_weight_maintenance=balance.short_weight_maintenance,
        )

    def _calculate_est_pnl(self, balance: BalanceWithProduct) -> Optional[Decimal]:
        """
        Calculate estimated PnL if indexer snapshot is available.

        Formula: (position_amount × oracle_price) - netEntryUnrealized

        Returns None if indexer data is not available.
        """
        if not self.indexer_events or balance.product_id == self.QUOTE_PRODUCT_ID:
            return None

        for event in self.indexer_events:
            if event.product_id != balance.product_id:
                continue
            if event.isolated:
                continue

            try:
                net_entry_int = int(event.net_entry_unrealized)
            except (TypeError, ValueError):
                continue

            net_entry_unrealized = Decimal(net_entry_int) / Decimal(10**18)

            current_value = balance.amount * balance.oracle_price
            return current_value - net_entry_unrealized

        return None

    def calculate_isolated_position_metrics(
        self, iso_pos: IsolatedPosition
    ) -> IsolatedPositionMetrics:
        """Calculate all metrics for an isolated position."""
        base_balance = self._create_balance_from_isolated(iso_pos, is_base=True)
        quote_balance = self._create_balance_from_isolated(iso_pos, is_base=False)

        net_margin = self.calculate_isolated_position_net_margin(
            base_balance, quote_balance
        )
        leverage = self.calculate_isolated_position_leverage(base_balance, net_margin)
        notional = self.calculate_perp_balance_notional_value(base_balance)

        initial_health = (
            self._parse_health(iso_pos.healths[0]) if iso_pos.healths else Decimal(0)
        )
        maint_health = (
            self._parse_health(iso_pos.healths[1])
            if len(iso_pos.healths) > 1
            else Decimal(0)
        )

        return IsolatedPositionMetrics(
            product_id=base_balance.product_id,
            symbol=f"Product_{base_balance.product_id}",
            position_size=base_balance.amount,
            notional_value=notional,
            net_margin=net_margin,
            leverage=leverage,
            initial_health=initial_health,
            maintenance_health=maint_health,
        )

    # Helper methods

    def _get_health_weights(self, balance: BalanceWithProduct) -> HealthMetrics:
        """Get appropriate weights based on position direction."""
        if balance.amount >= 0:
            return HealthMetrics(
                initial=balance.long_weight_initial,
                maintenance=balance.long_weight_maintenance,
            )
        else:
            return HealthMetrics(
                initial=balance.short_weight_initial,
                maintenance=balance.short_weight_maintenance,
            )

    def _has_borrows_or_perps(self) -> bool:
        """Check if account has any borrows or perp positions."""
        for spot_bal in self.subaccount_info.spot_balances:
            amount = _from_x18_decimal(spot_bal.balance.amount)
            if amount < 0:
                return True

        for perp_bal in self.subaccount_info.perp_balances:
            amount = _from_x18_decimal(perp_bal.balance.amount)
            if amount != 0:
                return True

        return False

    def _is_zero_health(self, balance: BalanceWithProduct) -> bool:
        """Check if product has zero health (long_weight=0, short_weight=2)."""
        return balance.long_weight_initial == 0 and balance.short_weight_initial == 2

    def _parse_health(self, health: SubaccountHealth) -> Decimal:
        """Parse health from SubaccountHealth model."""
        return _from_x18_decimal(health.health)

    def _create_spot_balances(self) -> list[BalanceWithProduct]:
        """Create BalanceWithProduct objects for all spot balances."""
        balances: list[BalanceWithProduct] = []
        for spot_bal, spot_prod in zip(
            self.subaccount_info.spot_balances, self.subaccount_info.spot_products
        ):
            balance = self._create_balance_with_product(spot_bal, spot_prod, "spot")
            balances.append(balance)
        return balances

    def _create_perp_balances(self) -> list[BalanceWithProduct]:
        """Create BalanceWithProduct objects for all perp balances."""
        balances: list[BalanceWithProduct] = []
        for perp_bal, perp_prod in zip(
            self.subaccount_info.perp_balances, self.subaccount_info.perp_products
        ):
            balance = self._create_balance_with_product(perp_bal, perp_prod, "perp")
            balances.append(balance)
        return balances

    def _create_balance_with_product(
        self,
        balance: Union[SpotProductBalance, PerpProductBalance],
        product: Union[SpotProduct, PerpProduct],
        balance_type: str,
    ) -> BalanceWithProduct:
        """Create a BalanceWithProduct from raw balance and product data."""
        amount = _from_x18_decimal(balance.balance.amount)
        oracle_price = _from_x18_decimal(product.oracle_price_x18)

        v_quote = None
        if balance_type == "perp":
            assert isinstance(
                balance, PerpProductBalance
            ), "Perp balances must be PerpProductBalance"
            v_quote = _from_x18_decimal(balance.balance.v_quote_balance)

        return BalanceWithProduct(
            product_id=balance.product_id,
            amount=amount,
            oracle_price=oracle_price,
            long_weight_initial=_from_x18_decimal(product.risk.long_weight_initial_x18),
            long_weight_maintenance=_from_x18_decimal(
                product.risk.long_weight_maintenance_x18
            ),
            short_weight_initial=_from_x18_decimal(
                product.risk.short_weight_initial_x18
            ),
            short_weight_maintenance=_from_x18_decimal(
                product.risk.short_weight_maintenance_x18
            ),
            balance_type=balance_type,
            v_quote_balance=v_quote,
        )

    def _create_balance_from_isolated(
        self, iso_pos: IsolatedPosition, is_base: bool
    ) -> BalanceWithProduct:
        """Create BalanceWithProduct from isolated position data."""
        if is_base:
            perp_balance: PerpProductBalance = iso_pos.base_balance
            perp_product: PerpProduct = iso_pos.base_product
            return self._create_balance_with_product(perp_balance, perp_product, "perp")

        spot_balance: SpotProductBalance = iso_pos.quote_balance
        spot_product: SpotProduct = iso_pos.quote_product
        return self._create_balance_with_product(spot_balance, spot_product, "spot")


def print_account_summary(summary: AccountSummary) -> None:
    """Print formatted account summary matching UI layout."""
    print("\n" + "=" * 80)
    print("MARGIN MANAGER")
    print("=" * 80)

    # Overview
    initial_margin_used = summary.unweighted_health - summary.initial_health
    print("\n━━━ Overview ━━━")
    print(f"Total Equity:              ${summary.portfolio_value:,.2f}")
    print(f"Initial Margin Used:       ${initial_margin_used:,.2f}")
    print(f"Initial Margin Available:  ${summary.funds_available:,.2f}")
    print(f"Leverage:                  {summary.account_leverage:.2f}x")

    # 1. Unified Margin Section
    print("\n━━━ UNIFIED MARGIN ━━━")
    print(f"Margin Usage:              {summary.margin_usage_fraction * 100:.2f}%")
    print(
        f"Maint. Margin Usage:       {summary.maint_margin_usage_fraction * 100:.2f}%"
    )
    print(f"Available Margin:          ${summary.funds_available:,.2f}")
    print(f"Funds Until Liquidation:   ${summary.funds_until_liquidation:,.2f}")

    # USDT0 Balance
    total_unsettled = sum(pos.unsettled for pos in summary.cross_positions)
    cash_balance = summary.total_spot_deposits - summary.total_spot_borrows
    net_balance = cash_balance + total_unsettled

    print("\n┌─ USDT0 Balance")
    print(f"│  Cash Balance:           ${cash_balance:,.2f}")
    print(f"│  Unsettled PnL:          ${total_unsettled:,.2f}")
    print(f"│  Net Balance:            ${net_balance:,.2f}")
    print(f"│  Init. Weight / Margin:  1.00 / ${net_balance:,.2f}")
    print(f"│  Maint. Weight / Margin: 1.00 / ${net_balance:,.2f}")

    # 2. Spot Balances
    print("\n┌─ Balances")
    spot_shown = False
    for spot_pos in summary.spot_positions:
        if spot_pos.amount == 0:
            continue
        spot_shown = True
        balance_type = "Deposit" if spot_pos.amount > 0 else "Borrow"
        value = abs(spot_pos.amount * spot_pos.oracle_price)

        # Use appropriate weight based on position direction
        if spot_pos.amount > 0:  # Deposit (asset)
            init_weight = spot_pos.long_weight_initial
            maint_weight = spot_pos.long_weight_maintenance
        else:  # Borrow (liability)
            init_weight = spot_pos.short_weight_initial
            maint_weight = spot_pos.short_weight_maintenance

        init_margin = value * init_weight
        maint_margin = value * maint_weight

        print(f"│  Product_{spot_pos.product_id} ({balance_type})")
        print(f"│    Balance:                {abs(spot_pos.amount):,.4f}")
        print(f"│    Value:                  ${value:,.2f}")
        print(f"│    Init. Weight / Margin:  {init_weight:.2f} / ${init_margin:,.2f}")
        print(f"│    Maint. Weight / Margin: {maint_weight:.2f} / ${maint_margin:,.2f}")

    if not spot_shown:
        print("│  No spot balances")

    # 3. Perps
    print("\n┌─ Perps")
    if summary.cross_positions:
        for cross_pos in summary.cross_positions:
            position_type = "Long" if cross_pos.position_size > 0 else "Short"
            print(f"│  {cross_pos.symbol} ({position_type} / Cross)")
            print(f"│    Position:             {cross_pos.position_size:,.3f}")
            print(f"│    Notional:             ${cross_pos.notional_value:,.2f}")

            if cross_pos.est_pnl is not None:
                pnl_sign = "+" if cross_pos.est_pnl >= 0 else ""
                print(f"│    Est. PnL:             {pnl_sign}${cross_pos.est_pnl:,.2f}")
            else:
                print(f"│    Est. PnL:             N/A")

            print(f"│    Unsettled:            {cross_pos.unsettled:,.2f} USDT0")

            # Use correct weight based on position direction
            if cross_pos.position_size > 0:  # Long
                init_weight = cross_pos.long_weight_initial
                maint_weight = cross_pos.long_weight_maintenance
            else:  # Short
                init_weight = cross_pos.short_weight_initial
                maint_weight = cross_pos.short_weight_maintenance

            # Margin = notional × |1 - weight|
            # For longs: weight < 1, so (1 - weight) > 0
            # For shorts: weight > 1, so (1 - weight) < 0, we need abs
            init_margin = cross_pos.notional_value * abs(1 - init_weight)
            maint_margin = cross_pos.notional_value * abs(1 - maint_weight)

            print(
                f"│    Init. Weight / Margin:  {init_weight:.2f} / ${init_margin:,.2f}"
            )
            print(
                f"│    Maint. Weight / Margin: {maint_weight:.2f} / ${maint_margin:,.2f}"
            )
    else:
        print("│  No perp positions")

    # Spreads
    print("\n┌─ Spreads")
    print("│  No spreads")

    # 4. Isolated Positions
    print("\n━━━ ISOLATED POSITIONS ━━━")
    total_isolated_margin = sum(pos.net_margin for pos in summary.isolated_positions)
    print(f"Total Margin in Isolated Positions: ${total_isolated_margin:,.2f}")

    if summary.isolated_positions:
        print("\n┌─ Perps")
        for iso_pos in summary.isolated_positions:
            position_type = "Long" if iso_pos.position_size > 0 else "Short"
            print(f"│  {iso_pos.symbol} ({position_type} / Isolated)")
            print(f"│    Position:             {iso_pos.position_size:,.3f}")
            print(f"│    Notional:             ${iso_pos.notional_value:,.2f}")
            print(f"│    Margin:               ${iso_pos.net_margin:,.2f}")
            print(f"│    Leverage:             {iso_pos.leverage:.2f}x")
            print(f"│    Init. Health:         ${iso_pos.initial_health:,.2f}")
            print(f"│    Maint. Health:        ${iso_pos.maintenance_health:,.2f}")
    else:
        print("\n┌─ Perps")
        print("│  No isolated positions")

    print("\n" + "=" * 80)
