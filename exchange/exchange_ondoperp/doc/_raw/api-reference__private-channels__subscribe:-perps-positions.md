> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Positions

> Subscribe to the `positionsPerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/positionsPerps
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
  /ws/positionsPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Positions'
      description: >-
        Subscribe to the `positionsPerps` channel. Requires authentication
        (login first).
      operationId: subscribe_positionsPerps
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
                    - positionsPerps
                  example: positionsPerps
                  description: Channel for this subscription.
            example:
              op: subscribe
              channel: positionsPerps
      responses:
        '200':
          description: Channel update for `positionsPerps`
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
                      - positionsPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Position'
              example:
                type: update
                channel: positionsPerps
                data:
                  - market: AAPL-USD.P
                    direction: long
                    netQuantity: '10.00'
                    averageEntryPrice: '225.00'
                    usedMargin: '1125.00'
                    unrealizedPnl: '25.00'
                    markPrice: '227.50'
                    liquidationPrice: '180.00'
                    bankruptcyPrice: '170.00'
                    maintenanceMargin: '112.50'
                    notionalValue: '2275.00'
                    leverage: '2.0'
                    netFundingSinceNeutral: '-1.23'
                    returnOnEquity: '0.022'
components:
  schemas:
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