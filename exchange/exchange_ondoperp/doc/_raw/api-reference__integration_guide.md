> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Builder Integration Guide

> Walk-through integrating with Ondo Perps as a builder. This guide uses JavaScript in-browser examples

<aside>
  🚧

  **Guide version: 1.0.3** | This guide is actively maintained and may change as the API evolves. Check back for updates.
</aside>

> **Full API reference:** [Ondoperps API Documentation](https://ondoperps.mintlify.app/)

> All endpoints in this guide use the **sandbox** environment. For production, swap the base URL.

Ondo Perps is a tokenized equity perps exchange. Builders who integrate Ondo Perps into their frontend earn incremental fees on every fill they route. Fees are deposited directly into your Ondo Perps margin account.

Your app handles the full user onboarding flow: wallet connection, SIWE auth, deposit, and order placement. Once a user is onboarded, every subsequent order is a single REST call with your builder code attached.

### How It Works

The user's wallet touches two things: SIWE login (to prove identity) and the on-chain deposit. Everything after that is REST calls authenticated by a JWT. Your app manages the session, and orders include your builder code. Incremental fees are attributed automatically on each fill.

### Integration Flow

```text theme={null}
1. Connect wallet       → User approves wallet connection
2. SIWE auth            → User signs challenge, your app gets a JWT
3. Accept TOS           → First login only
4. Deposit USDC         → On-chain transfer (production only; sandbox uses demo funds)
5. Place orders         → REST call with builderCode on every order
6. Earn fees            → Incremental fees credited per fill
```

***

## Step 1: Prerequisites

**Environment:** This guide runs in a browser with an EVM wallet extension installed (MetaMask, Phantom EVM, WalletConnect, etc.). The code uses `window.ethereum`.

**Sandbox access:**

1. Log in at [app.ondoperps-sandbox.xyz](http://app.ondoperps-sandbox.xyz) and get your account ID
2. Contact the Ondo Perps team at [**builders@ondoperps.xyz**](mailto:builders@ondoperps.xyz) with your app's public URL (for CORS allowlisting) and your account ID. You can also notify team of the fees your application will be charging (it will be applied to all user orders placed via your app). Alternatively, you can set desired fees in request body (see below). Please note, that currently builders are capped at 10 bps fee/order
3. You'll receive an invite code and your builder code
4. The team enables API key management for your account
5. Create and manage your API keys from the frontend

**Base URLs:**

| Environment | REST API                            | WebSocket                            |
| ----------- | ----------------------------------- | ------------------------------------ |
| Sandbox     | `https://api.ondoperps-sandbox.xyz` | `wss://api.ondoperps-sandbox.xyz/ws` |
| Production  | `https://api.ondoperps.xyz`         | `wss://api.ondoperps.xyz/ws`         |

***

## Step 2: Set Up Your Client

```jsx theme={null}
const provider = window.ethereum

// Sandbox base URL. For production, use 'api.ondoperps.xyz'
const ondoBase = 'api.ondoperps-sandbox.xyz'
const ondoUrl = `https://${ondoBase}`

// Market to test. Format: {TICKER}-USD.P
// Available markets include: XAU-USD.P, NVDA-USD.P, QQQ-USD.P, AMD-USD.P
const testMarket = 'XAU'
```

### Helper Methods

All authenticated endpoints require `Authorization: Bearer {jwtToken}`. Define these helpers once.

```jsx theme={null}
const parseResponse = (data) => {
  if (!data.success) {
    throw new Error(`Request failed: ${JSON.stringify(data)} (code: ${data.error_code})`)
  }
  return data.result
}

const fetchPost = async (endpoint, data) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}

let jwtToken = ''

const fetchAuthPost = async (endpoint, data) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`,
    },
    body: JSON.stringify(data),
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}

const fetchAuthGet = async (endpoint) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`,
    },
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}
```

***

## Step 3: Authenticate (SIWE)

Ondo Perps uses Sign In With Ethereum ([ERC-4361](https://eips.ethereum.org/EIPS/eip-4361)). The user signs a challenge with their wallet. Your app receives a JWT for all subsequent requests.

### 3a. Connect Wallet

Auth must happen on Ethereum mainnet, regardless of which chain the user deposits on later.

```jsx theme={null}
// Ensure wallet is on Ethereum mainnet
let chainId = await ethereum.request({ method: 'eth_chainId' })

if (chainId !== '0x1') {
  await window.ethereum.request({
    method: 'wallet_switchEthereumChain',
    params: [{ chainId: '0x1' }],
  })
}

// Request the user's account
const accounts = await provider.request({ method: 'eth_requestAccounts' })
const from = accounts[0]
```

### 3b. Define the SIWE Signing Function

```jsx theme={null}
const siweSign = async (siweMessage) => {
  const bytes = new TextEncoder().encode(siweMessage)
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  const msg = `0x${hex}`

  return await provider.request({
    method: 'personal_sign',
    params: [msg, from],
  })
}
```

### 3c. Request and Sign the Challenge

```jsx theme={null}
// Optionally pass builderCode to embed builder data into the JWT.
// Builder code information will then be passed automatically in all requests.
const getChallengeData = {
  walletAddress: from,
  chainId: '1',
  builderCode: "<your builder code here>"
}
const challenge = await fetchPost('/v1/auth/erc-4361/login/get_challenge', getChallengeData)
const signedMessage = await siweSign(challenge.message)
```

The response includes `challenge.id` and `challenge.message`, which you pass to the next two steps.

### 3d. Complete the Challenge and Get Your JWT

```jsx theme={null}
const completeChallengeData = {
  id: challenge.id,
  signature: signedMessage
}
const completeChallenge = await fetchPost('/v1/auth/erc-4361/login/complete_challenge', completeChallengeData)
jwtToken = completeChallenge.token
```

### 3e. Accept Terms (First Login Only)

```jsx theme={null}
await fetchAuthPost('/v1/agreement', {
  termsVersion: 1,
  privacyVersion: 1,
})
```

***

## Step 4: Deposit USDC

### Sandbox

In sandbox, regular deposit flow is optional. You can click through the deposit flow in the [sandbox frontend](https://app.ondoperps-sandbox.xyz). No real funds are needed. Once your account is funded, skip to Step 5: Place Orders.

### Production

Alternatively, use production-like deposit flow, where users deposit USDC on-chain. The flow: request a deposit address from the API, then send an ERC-20 transfer to that address.

Note: this example is written for Sepolia USDC contract, you should use Mainnet USDC contract for Production.

```jsx theme={null}
// Get your account ID
const accountData = await fetchAuthGet('/v1/account')
const accountID = accountData.accountID
```

```jsx theme={null}
// Request a deposit address
const provisionAddressReq = {
  symbol: 'USDC',
  deposit_destination: {
    id: accountID,
    wallet: 'margin',
  },
  network: 'ethereum', // also supports: solana, avalanche
}

const provisioned = await fetchAuthPost('/v1/provision_address', provisionAddressReq)
const depositAddress = provisioned.address
```

```jsx theme={null}
// Switch to the deposit chain (Sepolia for testnet, mainnet for production)
await window.ethereum.request({
  method: 'wallet_switchEthereumChain',
  params: [{ chainId: '0xAA36A7' }], // Sepolia testnet
})

// Send ERC-20 transfer: 50 USDC to the provisioned deposit address
// 0xa9059cbb = transfer(address,uint256) selector
// 0x02faf080 = 50,000,000 (50 USDC with 6 decimals)
const depositNoPrefix = depositAddress.replace(/^0x/i, '')
const sent_tx = await window.ethereum.request({
  method: 'eth_sendTransaction',
  params: [{
    to: '0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8', // Sepolia USDC contract
    from: from,
    data: `0xa9059cbb000000000000000000000000${depositNoPrefix}0000000000000000000000000000000000000000000000000000000002faf080`,
  }],
})

// Poll for transaction confirmation
for (;;) {
  const tx = await window.ethereum.request({
    method: 'eth_getTransactionByHash',
    params: [sent_tx],
  })
  if (tx.blockHash && tx.blockHash !== '') {
    break
  }
  // Wait 2 seconds between polls to avoid rate limiting
  await new Promise(resolve => setTimeout(resolve, 2000))
}

console.log('Deposit confirmed on-chain')
```

**Test funds (Sepolia):**

* USDC faucet: [gho.aave.com/faucet](http://gho.aave.com/faucet)
* ETH faucet: [sepolia-faucet.pk910.de](http://sepolia-faucet.pk910.de)

***

## Step 5: Place Orders

Market names use the format `{TICKER}-USD.P`. Examples: `QQQ-USD.P`, `NVDA-USD.P`, `AMD-USD.P`.

See the [Perps REST API](https://www.notion.so/Perps-REST-API-2ff278059c7f8199b12ef2f7e04e59ca?pvs=21) for the full order schema, batch orders, and cancellation.

### Market Order

```jsx theme={null}
// Optionally pass builderCode.feeRateBps to set desired fees for this order
// (in bps; must be a positive int number) 
// Optionally pass builderCode.code to set builder code if it was not passed to 
// GetChallenge
const marketOrderReq = {
  market: `${testMarket}-USD.P`,
  type: 'market',
  side: 'sell',
  size: '0.01',
  builderCode: {
    feeRateBps: 1,
    code: 'yourCode'
  }
}
const placedMarketOrder = await fetchAuthPost('/v1/perps/orders', marketOrderReq)
```

The response includes `orderId`, `market`, `type`, `side`, `size`, `status`, and `createdAt`. See the [Perps REST API](https://www.notion.so/Perps-REST-API-2ff278059c7f8199b12ef2f7e04e59ca?pvs=21) for the full response schema.

### Check Order Status

```jsx theme={null}
const orderDetails = await fetchAuthGet(`/v1/perps/orders/${placedMarketOrder.orderId}`)
```

### Check Positions

```jsx theme={null}
const positions = await fetchAuthGet('/v1/perps/positions')
```

### Limit Order

```jsx theme={null}
const limitOrderReq = {
  market: `${testMarket}-USD.P`,
  type: 'limit',
  side: 'buy',
  price: '5280',
  size: '0.02',
}
const placedLimitOrder = await fetchAuthPost('/v1/perps/orders', limitOrderReq)
```

Note: depending on market conditions, a limit order at this price may be rejected. Use the current market price as a reference.

> **Builder code:** Add your `builderCode` to every order to earn incremental fees. Contact the Ondo Perps team to get your code activated. Field name subject to change before v1.

***

## Step 6 (Optional): Charting Data

Fetch chart data for TradingView or any charting library. This endpoint does not require authentication.

```jsx theme={null}
const fetchHistory = async (endpoint) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  }).then(response => response.json())
}

const ts = Math.floor(Date.now() / 1000)
const history = await fetchHistory(
  `/v1/perps/history?symbol=${testMarket}USD.P&resolution=15&to=${ts}&countback=2`
)
```

***

## Step 7 (Optional): WebSockets

Subscribe to real-time price updates via WebSocket.

```jsx theme={null}
const wss = new WebSocket(`wss://${ondoBase}/ws`)

wss.addEventListener('message', (event) => {
  const data = event.data
  const obj = JSON.parse(data)
  switch (obj.type) {
    case 'pong':
      console.log('pong received')
      break
    case 'subscribed':
      console.log(`subscribed: ${data}`)
      break
    case 'update':
      console.log(`update: ${data}`)
      break
    default:
      console.error(`unexpected message: ${data}`)
  }
})

wss.addEventListener('open', () => {
  console.log('connected to WS')

  // Send pings every 1 second to keep the connection alive
  let pingInterval = setInterval(() => {
    const ping = {
      op: 'ping',
      id: window.crypto.randomUUID(),
    }
    wss.send(JSON.stringify(ping))
  }, 1000)

  // Subscribe to mark price updates
  const markPriceSub = {
    op: 'subscribe',
    channel: 'markPricesPerps',
    markets: [`${testMarket}-USD.P`],
  }
  wss.send(JSON.stringify(markPriceSub))
})
```

See the [WebSocket API docs](https://www.notion.so/Common-WebSocket-API-2ff278059c7f81c9ac10c8ffeb8b64dc?pvs=21) for all available channels and message formats.

***

## Sandbox vs Production

|            | Sandbox                              | Production                   |
| ---------- | ------------------------------------ | ---------------------------- |
| REST API   | `https://api.ondoperps-sandbox.xyz`  | `https://api.ondoperps.xyz`  |
| WebSocket  | `wss://api.ondoperps-sandbox.xyz/ws` | `wss://api.ondoperps.xyz/ws` |
| Frontend   | `https://app.ondoperps-sandbox.xyz`  | `https://app.ondoperps.xyz`  |
| Funds      | Demo funds (no real money)           | Real USDC deposits           |
| Auth chain | Ethereum mainnet                     | Ethereum mainnet             |
| Endpoints  | Same                                 | Same                         |

All endpoints work identically in both environments. Change the base URL and deposit flow, everything else stays the same.

***

## Full Example

Copy-paste the entire integration in one block. Mirrors Steps 2-7 above.

### Main Flow

```jsx theme={null}
// --- Step 2: Setup ---

const provider = window.ethereum
const ondoBase = 'api.ondoperps-sandbox.xyz'
const ondoUrl = `https://${ondoBase}`
const testMarket = 'XAU'

const parseResponse = (data) => {
  if (!data.success) {
    throw new Error(`Request failed: ${JSON.stringify(data)} (code: ${data.error_code})`)
  }
  return data.result
}

const fetchPost = async (endpoint, data) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}

let jwtToken = ''

const fetchAuthPost = async (endpoint, data) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`,
    },
    body: JSON.stringify(data),
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}

const fetchAuthGet = async (endpoint) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`,
    },
  })
    .then(response => response.json())
    .then(data => parseResponse(data))
}

// --- Step 3: Authenticate (SIWE) ---

let chainId = await ethereum.request({ method: 'eth_chainId' })
if (chainId !== '0x1') {
  await window.ethereum.request({
    method: 'wallet_switchEthereumChain',
    params: [{ chainId: '0x1' }],
  })
}

const accounts = await provider.request({ method: 'eth_requestAccounts' })
const from = accounts[0]

const siweSign = async (siweMessage) => {
  const bytes = new TextEncoder().encode(siweMessage)
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  const msg = `0x${hex}`
  return await provider.request({
    method: 'personal_sign',
    params: [msg, from],
  })
}

const getChallengeData = {
  walletAddress: from,
  chainId: '1',
  builderCode: "<your builder code here>"
}
const challenge = await fetchPost('/v1/auth/erc-4361/login/get_challenge', getChallengeData)
const signedMessage = await siweSign(challenge.message)

const completeChallengeData = {
  id: challenge.id,
  signature: signedMessage,
}
const completeChallenge = await fetchPost('/v1/auth/erc-4361/login/complete_challenge', completeChallengeData)
jwtToken = completeChallenge.token

// Accept terms (first login only)
await fetchAuthPost('/v1/agreement', {
  termsVersion: 1,
  privacyVersion: 1,
})

// --- Step 4: Deposit ---

// Get your account ID
const accountData = await fetchAuthGet('/v1/account')
const accountID = accountData.accountID

// Request a deposit address
const provisionAddressReq = {
  symbol: 'USDC',
  deposit_destination: {
    id: accountID,
    wallet: 'margin',
  },
  network: 'ethereum', // also supports: solana, avalanche
}

const provisioned = await fetchAuthPost('/v1/provision_address', provisionAddressReq)
const depositAddress = provisioned.address

// Switch to the deposit chain (Sepolia for testnet, mainnet for production)
await window.ethereum.request({
  method: 'wallet_switchEthereumChain',
  params: [{ chainId: '0xAA36A7' }], // Sepolia testnet
})

// Send ERC-20 transfer: 50 USDC to the provisioned deposit address
// 0xa9059cbb = transfer(address,uint256) selector
// 0x02faf080 = 50,000,000 (50 USDC with 6 decimals)
const depositNoPrefix = depositAddress.replace(/^0x/i, '')
const sent_tx = await window.ethereum.request({
  method: 'eth_sendTransaction',
  params: [{
    to: '0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8', // Sepolia USDC contract
    from: from,
    data: `0xa9059cbb000000000000000000000000${depositNoPrefix}0000000000000000000000000000000000000000000000000000000002faf080`,
  }],
})

// Poll for transaction confirmation
for (;;) {
  const tx = await window.ethereum.request({
    method: 'eth_getTransactionByHash',
    params: [sent_tx],
  })
  if (tx.blockHash && tx.blockHash !== '') {
    break
  }
  // Wait 2 seconds between polls to avoid rate limiting
  await new Promise(resolve => setTimeout(resolve, 2000))
}

console.log('Deposit confirmed on-chain')

// --- Step 5: Place Orders ---

const marketOrderReq = {
  market: `${testMarket}-USD.P`,
  type: 'market',
  side: 'sell',
  size: '0.01',
}
const placedMarketOrder = await fetchAuthPost('/v1/perps/orders', marketOrderReq)

const orderDetails = await fetchAuthGet(`/v1/perps/orders/${placedMarketOrder.orderId}`)

const positions = await fetchAuthGet('/v1/perps/positions')

// Uncomment to place a limit order:
// const limitOrderReq = {
//   market: `${testMarket}-USD.P`,
//   type: 'limit',
//   side: 'buy',
//   price: '5280',
//   size: '0.02',
// }
// const placedLimitOrder = await fetchAuthPost('/v1/perps/orders', limitOrderReq)

// --- Step 6: Charting Data ---

const fetchHistory = async (endpoint) => {
  return fetch(`${ondoUrl}${endpoint}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  }).then(response => response.json())
}

const ts = Math.floor(Date.now() / 1000)
const history = await fetchHistory(
  `/v1/perps/history?symbol=${testMarket}USD.P&resolution=15&to=${ts}&countback=2`
)
```

### WebSockets

```jsx theme={null}
const ondoBase = 'api.ondoperps-sandbox.xyz'
const testMarket = 'XAU'

const wss = new WebSocket(`wss://${ondoBase}/ws`)

wss.addEventListener('message', (event) => {
  const data = event.data
  const obj = JSON.parse(data)
  switch (obj.type) {
    case 'pong':
      console.log('pong received')
      break
    case 'subscribed':
      console.log(`subscribed: ${data}`)
      break
    case 'update':
      console.log(`update: ${data}`)
      break
    default:
      console.error(`unexpected message: ${data}`)
  }
})

wss.addEventListener('open', () => {
  console.log('connected to WS')

  let pingInterval = setInterval(() => {
    const ping = {
      op: 'ping',
      id: window.crypto.randomUUID(),
    }
    wss.send(JSON.stringify(ping))
  }, 1000)

  const markPriceSub = {
    op: 'subscribe',
    channel: 'markPricesPerps',
    markets: [`${testMarket}-USD.P`],
  }
  wss.send(JSON.stringify(markPriceSub))
})
```

***

## Changelog

| Version | Date       | Changes                                                                                                          |
| ------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| 1.0.0   | 2026-03-09 | Initial release. Sandbox-first guide with SIWE auth, deposit, order placement, charting, and WebSocket examples. |
| 1.0.1   | 2026-03-18 | Added Updated API Docs                                                                                           |
| 1.0.2   | 2026-03-20 | Added builder code in complete invite challenge path                                                             |
| 1.0.3   | 2026-06-01 | Moved builderCode from complete\_challenge to get\_challenge                                                     |
