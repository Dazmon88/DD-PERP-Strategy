> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Balance

> Subscribe to the `balancePerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/balancePerps
openapi: 3.0.3
info:
  title: Ondo Perps WebSocket API
  version: '1.0'
  description: >-
    WebSocket API for Ondo Perps: real-time market data, order updates,
    positions, balance, funding, and more.


    ## Connection


    Connect via `wss://api.ondoperps.xyz/ws`. The server enforces a 32 KB max
    message size and a rate limit of 25 requests/second (burst 50).


    ## Authentication


    Public channels (market data) require no authentication. Private channels
    (orders, fills, positions, balance, etc.) require a `login` message first.


    ### JWT Login

    ```json

    {"op": "login", "args": {"token": "<JWT>"}}

    ```


    ### API Key Login

    ```json

    {"op": "login", "args": {"key": "<api_key_id>", "time": "<unix_ms>", "sign":
    "<hex_hmac>"}}

    ```


    Signature: `HMAC-SHA256(api_secret, "ondo_perps_ws_login" + time)`


    ## Heartbeat


    Send `{"op": "ping"}` periodically. The server responds with `{"type":
    "pong"}`. Connections idle for 180 seconds are closed.


    ## Message Format


    ### Client → Server

    All client messages use the `op` field: `ping`, `login`, `subscribe`,
    `unsubscribe`, `sendMessage`.


    ### Server → Client

    All server messages use the `type` field: `pong`, `loggedIn`, `subscribed`,
    `unsubscribed`, `update`, `error`.

    Channel data updates arrive as `{"type": "update", "channel": "<name>",
    "data": <payload>}`.
servers:
  - url: wss://api.ondoperps.xyz
    description: Production
security: []
paths:
  /ws/balancePerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Balance'
      description: >-
        Subscribe to the `balancePerps` channel. Requires authentication (login
        first).
      operationId: subscribe_balancePerps
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - op
                - channel
              properties:
                op:
                  type: string
                  enum:
                    - subscribe
                    - unsubscribe
                  example: subscribe
                  description: Operation type.
                channel:
                  type: string
                  enum:
                    - balancePerps
                  example: balancePerps
                  description: Channel for this subscription.
            example:
              op: subscribe
              channel: balancePerps
      responses:
        '200':
          description: Channel update for `balancePerps`
          content:
            application/json:
              schema:
                type: object
                properties:
                  type:
                    type: string
                    enum:
                      - update
                  channel:
                    type: string
                    enum:
                      - balancePerps
                  data:
                    $ref: '#/components/schemas/Balance'
              example:
                type: update
                channel: balancePerps
                data:
                  walletBalance: '5000.00'
                  realizedPnl: '250.00'
                  unrealizedPnl: '-50.00'
                  marginBalance: '4950.00'
                  usedMargin: '1125.00'
components:
  schemas:
    Balance:
      type: object
      properties:
        walletBalance:
          type: string
          example: '5000.00'
        realizedPnl:
          type: string
          example: '250.00'
        unrealizedPnl:
          type: string
          example: '-50.00'
        marginBalance:
          type: string
          example: '4950.00'
        usedMargin:
          type: string
          example: '1125.00'
        availableMargin:
          type: string
          example: '3825.00'
        withdrawableMargin:
          type: string
          example: '3825.00'
        maintenanceMarginRequirement:
          type: string
          example: '112.50'
        totalMaintenanceMargin:
          type: string
          example: '200.00'
        marginRatio:
          type: string
          example: '0.04'
        leverage:
          type: string
          example: '0.46'
        underLiquidation:
          type: boolean
          example: false
        totalFundingPayments:
          type: string
          example: '-5.67'
        totalTradingFees:
          type: string
          example: '12.34'
        totalPnL:
          type: string
          example: '232.00'
        netInvested:
          type: string
          example: '4750.00'

````