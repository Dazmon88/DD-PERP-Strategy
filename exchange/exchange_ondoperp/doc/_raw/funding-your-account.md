> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Funding Your Account

Ondo Perps supports two forms of collateral: USDC and Ondo Global Markets tokenized equities. Tokenized equity collateral is currently available for whitelisted accounts. Traders interested in access should contact [support@ondoperps.xyz](mailto:support@ondoperps.xyz).

**Accepted Collateral**

| **Asset** | **Description**                | **Haircut** |
| :-------- | :----------------------------- | ----------- |
| **USDC**  | Available to all accounts      | 0%          |
| **SPYON** | Available to approved accounts | 10%         |
| **QQQON** | Available to approved accounts | 10%         |

Deposits are currently supported via Ethereum. Additional networks will be supported in future updates.

For details on using SPYON and QQQON as collateral see Ondo Tokenized Stock Collateral.

**Deposit Addresses**

Ondo Perps is an encrypted offchain exchange and so does not require interaction with any smart-contract bridges to despoit assets. Each account can provision a deposit address that is permanently linked to that account. Any transfers to this address of a supported asset will be credited to the account.

**Pricing**

Deposited tokenized assets are priced using the mark price for the corresponding market on the exchange. A per-asset haircut is applied to account for price volatility, conversion costs, and weekend gap risk. The post-haircut value counts toward your margin balance and functions identically to USDC deposits for the purposes of opening and maintaining positions.
