# Margin Manager Implementation Reference

This document maps all margin manager formulas to their source implementations in the nado-web-monorepo and nado-typescript-sdk.

## Formula Source File Mapping

### 1. **Unsettled PnL (Total for USDT0 Balance)**

**Formula**: `sum(amount × oracle_price + v_quote_balance)` for all perp positions

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
unsettled = self.calculate_perp_balance_value(balance)
# = balance.amount × balance.oracle_price + balance.v_quote_balance
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/utils/calcs/subaccount/subaccountInfoCalcs.ts`
  - Lines 33-62, specifically lines 49-54
- **TypeScript SDK**: `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts`
  - Lines 36-42 (`calcPerpBalanceValue`)

**TypeScript Reference**:
```typescript
// subaccountInfoCalcs.ts:49-54
} else if (balance.type === ProductEngineType.PERP) {
  const notional = calcPerpBalanceNotionalValue(balance);
  const value = calcPerpBalanceValue(balance);  // ← THIS

  values.perpNotional = values.perpNotional.plus(notional);
  values.perp = values.perp.plus(value);  // ← totalUnsettledQuote
}

// balanceValue.ts:36-42
export function calcPerpBalanceValue(
  balanceWithProduct: PerpBalanceWithProduct,
): BigDecimal {
  return balanceWithProduct.amount
    .multipliedBy(balanceWithProduct.oraclePrice)
    .plus(balanceWithProduct.vQuoteBalance);
}
```

---

### 2. **Est. PnL (Estimated PnL for each Perp Position)**

**Formula**: `amount × oracle_price - netEntryUnrealized`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
est_pnl = balance.amount × balance.oracle_price - net_entry_unrealized
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/utils/calcs/pnlCalcs.ts`
  - Lines 8-24 (`calcIndexerSummaryUnrealizedPnl`)
  - Lines 76-82 (`calcPnl`)
- **Usage**: `nado-web-monorepo/apps/trade/client/hooks/subaccount/usePerpPositions.ts`
  - Lines 207-210

**TypeScript Reference**:
```typescript
// pnlCalcs.ts:76-82
export function calcPnl(
  positionAmount: BigDecimal,
  price: BigDecimal,
  netEntry: BigDecimal,
) {
  return positionAmount.multipliedBy(price).minus(netEntry);
}

// pnlCalcs.ts:17-21
const unrealizedPnl = calcPnl(
  indexerBalance.state.postBalance.amount,
  oraclePrice,
  indexerBalance.trackedVars.netEntryUnrealized,
);
```

**Important Note**: `netEntryUnrealized` is already in quote (USD/USDT) terms for perps, so NO multiplication by quote price is needed!

---

### 3. **Notional Value**

**Formula**: `abs(amount × oracle_price)`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
notional = abs(balance.amount × balance.oracle_price)
```

**Source Files**:
- **TypeScript SDK**: `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts`
  - Lines 23-29 (`calcPerpBalanceNotionalValue`)

**TypeScript Reference**:
```typescript
// balanceValue.ts:23-29
export function calcPerpBalanceNotionalValue(
  balanceWithProduct: PerpBalanceWithProduct,
): BigDecimal {
  return balanceWithProduct.amount
    .multipliedBy(balanceWithProduct.oraclePrice)
    .abs();
}
```

---

### 4. **Cash Balance (USDT0)**

**Formula**: `primary_quote_balance.amount` (sum of spot deposits - borrows)

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
cash_balance = sum(spot deposits) - sum(spot borrows)
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/pages/Portfolio/subpages/MarginManager/tables/hooks/useMarginManagerQuoteBalanceTable.tsx`
  - Line 49 (`balanceAmount: primaryQuoteBalance.amount`)
- **Calculation**: `nado-web-monorepo/apps/trade/client/utils/calcs/subaccount/subaccountInfoCalcs.ts`
  - Lines 44-48 (spot balance value)

**TypeScript Reference**:
```typescript
// useMarginManagerQuoteBalanceTable.tsx:49
balanceAmount: primaryQuoteBalance.amount,

// subaccountInfoCalcs.ts:44-48
summary.balances.forEach((balance) => {
  if (balance.type === ProductEngineType.SPOT) {
    const value = calcSpotBalanceValue(balance);  // amount × oraclePrice
    values.spot = values.spot.plus(value);
  }
```

---

### 5. **Net Balance (USDT0)**

**Formula**: `Cash Balance + Unsettled PnL`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
net_balance = cash_balance + total_unsettled
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/pages/Portfolio/subpages/MarginManager/tables/hooks/useMarginManagerQuoteBalanceTable.tsx`
  - Lines 31-36

**TypeScript Reference**:
```typescript
// useMarginManagerQuoteBalanceTable.tsx:31-36
const unsettledQuoteUsd = derivedOverview.perp.cross.totalUnsettledQuote;

const netBalanceUsd = unsettledQuoteUsd.plus(
  primaryQuoteBalance.amount,
);
```

---

### 6. **Perp Margin (Initial & Maintenance)**

**Formula**:
- `Initial Margin = notional × abs(1 - init_weight)`
- `Maintenance Margin = notional × abs(1 - maint_weight)`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
init_margin = notional × abs(1 - init_weight)
maint_margin = notional × abs(1 - maint_weight)
```

**Source Files**:
- **Health calculations**: `nado-web-monorepo/apps/trade/client/utils/calcs/healthCalcs.ts`
  - Shows weight application but not explicit margin formula

**Important Notes**:
- The `abs()` is critical for short positions where weight > 1!
- For longs: weight < 1, so (1 - weight) > 0
- For shorts: weight > 1, so (1 - weight) < 0, we need abs

**Example**:
```
BTC Long (100 BTC at $108,000):
- Notional = $10,800,000
- Init Weight = 0.95
- Init Margin = $10,800,000 × (1 - 0.95) = $540,000

ETH Short (-10.5 ETH at $3,800):
- Notional = $40,000
- Init Weight = 1.05
- Init Margin = $40,000 × |1 - 1.05| = $40,000 × 0.05 = $2,000
```

---

### 7. **Margin Usage Fractions**

**Formula**:
- `Initial Margin Usage = (unweighted_health - initial_health) / unweighted_health`
- `Maintenance Margin Usage = (unweighted_health - maintenance_health) / unweighted_health`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
# Using engine health values directly
initial_margin_usage = (unweighted_health - initial_health) / unweighted_health
maint_margin_usage = (unweighted_health - maintenance_health) / unweighted_health
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/utils/calcs/subaccount/subaccountInfoCalcs.ts`
  - Lines 108-144 (`calcSubaccountMarginUsageFractions`)

**TypeScript Reference**:
```typescript
// subaccountInfoCalcs.ts:128-133
const initialMarginUsage = unweightedHealth
  .minus(initialHealth)
  .div(unweightedHealth);
const maintMarginUsage = unweightedHealth
  .minus(maintenanceHealth)
  .div(unweightedHealth);
```

---

### 8. **Available Margin**

**Formula**: `max(0, initial_health)`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
available_margin = max(Decimal(0), initial_health)
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/hooks/subaccount/useSubaccountOverview/getSubaccountOverview.ts`
  - Line 305

**TypeScript Reference**:
```typescript
// getSubaccountOverview.ts:305
fundsAvailableBoundedUsd: BigDecimal.max(0, decimalAdjustedInitialHealth),
```

---

### 9. **Funds Until Liquidation**

**Formula**: `max(0, maintenance_health)`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
funds_until_liquidation = max(Decimal(0), maintenance_health)
```

**Source Files**:
- **Monorepo**: `nado-web-monorepo/apps/trade/client/hooks/subaccount/useSubaccountOverview/getSubaccountOverview.ts`
  - Lines 306-309

**TypeScript Reference**:
```typescript
// getSubaccountOverview.ts:306-309
fundsUntilLiquidationBoundedUsd: BigDecimal.max(
  0,
  decimalAdjustedMaintHealth,
),
```

---

### 10. **Spot Balance Value**

**Formula**: `amount × oracle_price`

**Python Implementation**:
```python
# nado_protocol/utils/margin_manager.py
spot_value = balance.amount × balance.oracle_price
```

**Source Files**:
- **TypeScript SDK**: `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts`
  - Lines 12-16 (`calcSpotBalanceValue`)

**TypeScript Reference**:
```typescript
// balanceValue.ts:12-16
export function calcSpotBalanceValue(
  balanceWithProduct: SpotBalanceWithProduct,
): BigDecimal {
  return balanceWithProduct.amount.multipliedBy(balanceWithProduct.oraclePrice);
}
```

---

## Summary Table

| Formula | Primary Source File | Lines |
|---------|-------------------|-------|
| Unsettled PnL (Total) | `nado-web-monorepo/apps/trade/client/utils/calcs/subaccount/subaccountInfoCalcs.ts` | 49-54 |
| calcPerpBalanceValue | `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts` | 36-42 |
| Est. PnL | `nado-web-monorepo/apps/trade/client/utils/calcs/pnlCalcs.ts` | 76-82 |
| Notional Value | `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts` | 23-29 |
| Cash Balance | `nado-web-monorepo/apps/trade/client/pages/Portfolio/subpages/MarginManager/tables/hooks/useMarginManagerQuoteBalanceTable.tsx` | 49 |
| Net Balance | `nado-web-monorepo/apps/trade/client/pages/Portfolio/subpages/MarginManager/tables/hooks/useMarginManagerQuoteBalanceTable.tsx` | 31-36 |
| Margin Usage | `nado-web-monorepo/apps/trade/client/utils/calcs/subaccount/subaccountInfoCalcs.ts` | 128-133 |
| Available Margin | `nado-web-monorepo/apps/trade/client/hooks/subaccount/useSubaccountOverview/getSubaccountOverview.ts` | 305 |
| Funds Until Liquidation | `nado-web-monorepo/apps/trade/client/hooks/subaccount/useSubaccountOverview/getSubaccountOverview.ts` | 306-309 |
| Spot Balance Value | `nado-typescript-sdk/packages/shared/src/utils/balanceValue.ts` | 12-16 |

---