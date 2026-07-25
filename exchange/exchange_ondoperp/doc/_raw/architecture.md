> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Architecture

Ondo Perps runs as an offchain matching engine with onchain settlement. The two are separate by design: the matching engine optimizes for speed and determinism; the settlement layer handles onchain asset custody.

***

## The Three Components

### Exchange-Engine

The Exchange-Engine housing the matching engine, account manager, order book, position tracking, and liquidation logic. It runs entirely offchain. When a user deposits or withdraws, the exchange-engine queries the chain-core for onchain state, it does not interact with the chain directly.

#### Chain-Engine

The chain-core is the onchain interface. It processes deposits and withdrawals: it watches for incoming onchain transfers, confirms them, and signals the exchange-engine to credit the account. For withdrawals, it executes the onchain transaction and pays gas on behalf of the user.

<Note>
  The chain-core holds no knowledge of internal accounts. It sees only onchain addresses and transfer amounts sweeping deposits into the main hot wallet.
</Note>

#### Attestor Network

The attestor network is the trust layer between the exchange-engine and the chain-core. It distributes the cryptographic secrets each component needs to operate, and serves as the consensus mechanism for blockchain state. Neither component can function fully without it.

***

## Execution Integrity

The matching engine runs inside an SGX (Software Guard Extensions) hardware enclave. SGX creates an isolated memory region that the operating system and the hardware owner cannot read or modify, including Ondo's own infrastructure team.

The enclave produces a cryptographic attestation proving it is running a specific, published binary. Reproducible builds ensure the binary is deterministic: the same source code produces the same binary every time, so the deployed code is independently verifiable against the published source.

The attestation model removes operator trust as a variable. No party, including Ondo, can modify matching logic or access order state while the enclave is running.

***

## Deposit and Withdrawal Flow

**Deposit:**

1. User sends USDC or a supported tokenized equity to their assigned deposit address onchain
2. No bridge required, standard ERC-20 transfer
3. Chain-core detects the transfer and notifies the exchange-engine
4. Exchange-engine credits the user's margin wallet
5. The chain-core sweeps the deposit into its main hot wallet

**Withdrawal:**

1. User requests withdrawal via API
2. Exchange-engine validates against available margin (cannot withdraw collateral backing open positions)
3. Chain-core executes the onchain transfer; Ondo pays gas
4. Withdrawal is marked as finalized when enough confirmations has been reached

<Note>
  Ethereum is live. Additional chains are coming soon. Deposit addresses are chain-specific.
</Note>

***

## Collateral Custody

The chain-core manages an omnibus account that holds collateral. Individual account balances are tracked offchain by the exchange-engine. There is no pooled smart contract governing user funds. The trust guarantee is the SGX attestation, a cryptographic proof that the running binary matches the published source, not onchain contract auditability.
