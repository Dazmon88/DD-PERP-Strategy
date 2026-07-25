> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Orders

> Subscribe to the `ordersPerps` channel. Requires authentication (login first).

Optional `markets` to filter.



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/ordersPerps
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
  /ws/ordersPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Orders'
      description: >-
        Subscribe to the `ordersPerps` channel. Requires authentication (login
        first).


        Optional `markets` to filter.
      operationId: subscribe_ordersPerps
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
                    - ordersPerps
                  example: ordersPerps
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
            example:
              op: subscribe
              channel: ordersPerps
              markets:
                - NVDA-USD.P
      responses:
        '200':
          description: Channel update for `ordersPerps`
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
                      - ordersPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Order'
              example:
                type: update
                channel: ordersPerps
                data:
                  - orderId: 197ec08e001658690721be129e7fa595
                    side: buy
                    price: '227.50'
                    size: '10.00'
                    market: AAPL-USD.P
                    filledSize: '0.00'
                    filledCost: '0.00'
                    fee: '0.00'
                    status: open
                    createdAt: '2025-03-05T14:30:00Z'
                    type: limit
                    timeInForce: GTC
components:
  schemas:
    Order:
      type: object
      properties:
        orderId:
          type: string
          example: 197ec08e001658690721be129e7fa595
        clientOrderId:
          type: string
        parentOrderId:
          type: string
        side:
          type: string
          enum:
            - buy
            - sell
        price:
          type: string
          example: '227.50'
        size:
          type: string
          example: '10.00'
        market:
          type: string
          example: AAPL-USD.P
        filledSize:
          type: string
          example: '0.00'
        lastFillSize:
          type: string
          example: '0.00'
        filledCost:
          type: string
          example: '0.00'
        realizedPnl:
          type: string
        fee:
          type: string
          example: '0.00'
        feeRebate:
          type: string
        status:
          type: string
          enum:
            - open
            - fullyfilled
            - canceled
        createdAt:
          type: string
          format: date-time
        filledAt:
          type: string
          format: date-time
        canceledAt:
          type: string
          format: date-time
        cancelReason:
          type: string
        type:
          type: string
          enum:
            - limit
            - market
        timeInForce:
          type: string
          enum:
            - GTC
            - IOC
            - FOK
        reduceOnly:
          type: boolean
        liquidationId:
          type: string
        closePosition:
          type: boolean
        stopOrderType:
          type: string
        triggerPrice:
          type: string
      example:
        orderId: 197ec08e001658690721be129e7fa595
        side: buy
        price: '227.50'
        size: '10.00'
        market: AAPL-USD.P
        filledSize: '0.00'
        filledCost: '0.00'
        fee: '0.00'
        status: open
        createdAt: '2025-03-05T14:30:00Z'
        type: limit
        timeInForce: GTC

````