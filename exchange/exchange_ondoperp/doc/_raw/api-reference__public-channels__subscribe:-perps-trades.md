> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Trades

> Subscribe to the `tradesPerps` channel.

Optional `markets` and `numPastTrades` (number of historical trades on subscribe).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/tradesPerps
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
  /ws/tradesPerps:
    post:
      tags:
        - Public Channels
      summary: 'Subscribe: Perps Trades'
      description: >-
        Subscribe to the `tradesPerps` channel.


        Optional `markets` and `numPastTrades` (number of historical trades on
        subscribe).
      operationId: subscribe_tradesPerps
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
                    - tradesPerps
                  example: tradesPerps
                  description: Channel for this subscription.
                markets:
                  type: array
                  items:
                    type: string
                  example:
                    - NVDA-USD.P
                  description: >-
                    Markets to filter by. Optional; if omitted, all available
                    markets are used.
                numPastTrades:
                  type: integer
                  example: 50
                  description: Number of historical trades to receive on subscribe.
            example:
              op: subscribe
              channel: tradesPerps
              markets:
                - NVDA-USD.P
              numPastTrades: 50
      responses:
        '200':
          description: Channel update for `tradesPerps`
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
                      - tradesPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Trade'
              example:
                type: update
                channel: tradesPerps
                data:
                  - market: AAPL-USD.P
                    price: '227.50'
                    size: '5.00'
                    cost: '1137.50'
                    aggressor_side: buy
                    time: '2025-03-05T14:30:00Z'
                    id: 70a37d8f972f2494837f9dba8364cbb4
components:
  schemas:
    Trade:
      type: object
      properties:
        market:
          type: string
          example: AAPL-USD.P
        price:
          type: string
          example: '227.50'
        size:
          type: string
          example: '5.00'
        cost:
          type: string
          example: '1137.50'
        aggressor_side:
          type: string
          enum:
            - buy
            - sell
        time:
          type: string
          format: date-time
        id:
          type: string
          example: 70a37d8f972f2494837f9dba8364cbb4
      example:
        market: AAPL-USD.P
        price: '227.50'
        size: '5.00'
        cost: '1137.50'
        aggressor_side: buy
        time: '2025-03-05T14:30:00Z'
        id: 70a37d8f972f2494837f9dba8364cbb4

````