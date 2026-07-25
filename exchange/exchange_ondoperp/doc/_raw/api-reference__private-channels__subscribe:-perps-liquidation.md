> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Liquidation

> Subscribe to the `liquidationPerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/liquidationPerps
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
  /ws/liquidationPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Liquidation'
      description: >-
        Subscribe to the `liquidationPerps` channel. Requires authentication
        (login first).
      operationId: subscribe_liquidationPerps
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
                    - liquidationPerps
                  example: liquidationPerps
                  description: Channel for this subscription.
            example:
              op: subscribe
              channel: liquidationPerps
      responses:
        '200':
          description: Channel update for `liquidationPerps`
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
                      - liquidationPerps
                  data:
                    $ref: '#/components/schemas/LiquidationEvent'
components:
  schemas:
    LiquidationEvent:
      type: object
      properties:
        id:
          type: string
        time:
          type: string
          format: date-time
        initiatedAt:
          type: string
          format: date-time
        accountId:
          type: string
        status:
          type: string
        insuranceFundUsed:
          type: string
          example: '0.00'
        adl:
          type: boolean
        retryCount:
          type: integer
        triggeringPositions:
          type: array
          items:
            $ref: '#/components/schemas/Position'
        filledQuoteSize:
          type: string
        filledQuantity:
          type: string
        reclaimOrderMargin:
          type: boolean
    Position:
      type: object
      properties:
        market:
          type: string
          example: AAPL-USD.P
        direction:
          type: string
          enum:
            - long
            - short
        netQuantity:
          type: string
          example: '10.00'
        averageEntryPrice:
          type: string
          example: '225.00'
        usedMargin:
          type: string
          example: '1125.00'
        unrealizedPnl:
          type: string
          example: '25.00'
        markPrice:
          type: string
          example: '227.50'
        liquidationPrice:
          type: string
          example: '180.00'
        bankruptcyPrice:
          type: string
          example: '170.00'
        maintenanceMargin:
          type: string
          example: '112.50'
        notionalValue:
          type: string
          example: '2275.00'
        leverage:
          type: string
          example: '2.0'
        netFundingSinceNeutral:
          type: string
          example: '-1.23'
        stopLossTriggerPrice:
          type: string
        takeProfitTriggerPrice:
          type: string
        returnOnEquity:
          type: string
          example: '0.022'

````