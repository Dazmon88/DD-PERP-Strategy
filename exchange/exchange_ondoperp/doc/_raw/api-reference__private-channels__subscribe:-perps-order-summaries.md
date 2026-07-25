> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Order Summaries

> Subscribe to the `ordersSummariesPerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/ordersSummariesPerps
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
  /ws/ordersSummariesPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Order Summaries'
      description: >-
        Subscribe to the `ordersSummariesPerps` channel. Requires authentication
        (login first).
      operationId: subscribe_ordersSummariesPerps
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - op
                - channel
                - markets
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
                    - ordersSummariesPerps
                  example: ordersSummariesPerps
                  description: Channel for this subscription.
                markets:
                  type: array
                  items:
                    type: string
                  example:
                    - NVDA-USD.P
                  description: Markets to subscribe to. At least one market is required.
            example:
              op: subscribe
              channel: ordersSummariesPerps
              markets:
                - NVDA-USD.P
      responses:
        '200':
          description: Channel update for `ordersSummariesPerps`
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
                      - ordersSummariesPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/OrdersSummary'
components:
  schemas:
    OrdersSummary:
      type: object
      properties:
        market:
          type: string
          example: AAPL-USD.P
        restingOrdersSummary:
          type: object
        positionSummary:
          type: object
        marketOrderSummary:
          type: object

````