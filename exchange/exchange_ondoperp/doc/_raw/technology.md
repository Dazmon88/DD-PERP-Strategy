> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Technology

Ondo Perps runs as a decentralized offchain exchange powered by secure enclave technology, a hardware-based trusted execution environment (TEE) that isolates trading operations from external access or tampering, including by the platform itself. The result is execution speed comparable to a centralized exchange, with custody and integrity guarantees that no single party, including the operators, can override.

## The Three Building Blocks

<CardGroup cols={3}>
  <Card title="Secure enclave" icon="microchip">
    Order matching, margin, liquidations, and wallet logic all execute inside Intel SGX enclaves. Code is encrypted at runtime and invisible to the host OS, cloud provider, and Ondo Perps operators.
  </Card>

  <Card title="Attestor network" icon="network">
    An independent quorum of third-party attestors verifies that the enclave is running the published codebase on genuine SGX hardware. Key material is split across the network, no single party can move funds.
  </Card>

  <Card title="On-chain custody" icon="vault">
    Each account has a permanent onchain deposit address. Deposits are swept into an exchange hot wallet, which initiates withdrawals on user request. All deposits and withdrawals are publicly observable onchain.
  </Card>
</CardGroup>

## How It Works

### Secure Enclave Execution

At the core of the architecture is **Intel SGX (Software Guard Extensions)**, which runs the exchange's critical components, order matching, margin calculations, wallet management, and liquidations, inside an encrypted, hardware-isolated environment. Code running inside the enclave cannot be accessed or modified by:

* The operating system on the host machine.
* The infrastructure provider hosting the machine.
* The exchange operators themselves.

All orders are processed in fully encrypted form. Trade history is only revealed after an order is fully processed, so no actor, including the platform, can observe or interfere with the order flow in transit.

### Decentralized Attestor Network

Integrity is enforced by a decentralized network of independent third-party attestors. Their job is to continuously verify that the enclave is running the **correct, unmodified codebase** on **genuine SGX-enabled hardware**.

* **Distributed key shares:** Secret key material (including any key authorized to move user funds) is split across the attestor network. No single party can reconstruct the master secret or move funds unilaterally.
* **Quorum-gated upgrades:** Any modification to the codebase requires an independent majority of attestors to audit and approve before it takes effect.

### Onchain Custody

User deposits do not live inside the enclave. The flow is:

1. **Per-account deposit address:** Each account provisions a permanent onchain deposit address. Any transfer of a supported asset to that address is credited to the account.
2. **Sweep into the hot wallet:** Deposited funds are swept from deposit addresses into the exchange hot wallet.
3. **Withdrawals:** When you request a withdrawal, the hot wallet initiates the onchain transfer back to your wallet.

Because every deposit and every withdrawal moves through an onchain transfer, the full flow of funds is publicly observable on the underlying blockchain, no operator-controlled internal sub-ledgers in between.

See [Funding your account](https://docs.ondoperps.xyz/funding-your-account) for the supported networks and the deposit-address provisioning flow.

## Performance

Because critical operations execute inside the enclave rather than on-chain, the system does not carry the latency overhead typically associated with on-chain settlement. Order routing, margin updates, and liquidations are processed in real time, with execution speed comparable to a centralized exchange, including during periods of high volatility.

## What This Gives You

Compared with a traditional centralized exchange:

* **No operator front-running:** Operators cannot read your orders before they match.
* **No silent code changes:** Codebase upgrades require independent attestor approval.
* **Publicly observable custody:** Every deposit and withdrawal moves through an onchain transfer, no hidden internal sub-ledgers.

Compared with a fully onchain DEX:

* **CEX-level latency:** Matching, margin, and liquidations are real-time, not bound by block times.
* **Richer order types:** Limit, TP/SL, TWAP, reduce-only, and post-only are all native ([Order types](https://docs.ondoperps.xyz/order-types)).
* **Lower fees with the same trust:** Offchain execution removes per-trade gas costs while preserving on-chain custody.

For users trading tokenized real-world assets, where accurate pricing, fair execution, and reliable collateral handling are foundational, this is the combination the platform is built for.

## Learn More

<CardGroup cols={2}>
  <Card title="Fund your account" icon="wallet" href="/funding-your-account">
    Supported collateral, networks, and contract addresses for deposits.
  </Card>

  <Card title="Mark price protection" icon="shield-check" href="/mark-price-protection">
    How external oracle prices keep liquidations fair and resistant to manipulation.
  </Card>

  <Card title="Liquidations and insurance" icon="droplet" href="/def">
    The multi-layered liquidation process and the insurance fund.
  </Card>

  <Card title="External pricing derivations" icon="dollar-sign" href="/pricing-derivations">
    Where mark prices come from and how indices and futures are synthesized.
  </Card>
</CardGroup>
