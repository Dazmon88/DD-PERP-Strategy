> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Depth Book

> Subscribe to the `depthBooksPerps` channel.

Optional `markets`, `depthLevels` (price grouping), and `limit` (max levels).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/depthBooksPerps
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
  /ws/depthBooksPerps:
    post:
      tags:
        - Public Channels
      summary: 'Subscribe: Perps Depth Book'
      description: >-
        Subscribe to the `depthBooksPerps` channel.


        Optional `markets`, `depthLevels` (price grouping), and `limit` (max
        levels).
      operationId: subscribe_depthBooksPerps
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
                    - depthBooksPerps
                  example: depthBooksPerps
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
                depthLevels:
                  type: string
                  example: '0.01'
                  description: Price grouping level for the depth book.
                limit:
                  type: integer
                  example: 20
                  description: Maximum depth levels to return; 0 for unlimited.
            example:
              op: subscribe
              channel: depthBooksPerps
              markets:
                - NVDA-USD.P
              depthLevels: '0.01'
              limit: 20
      responses:
        '200':
          description: Channel update for `depthBooksPerps`
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
                      - depthBooksPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/BookSnapshot'
components:
  schemas:
    BookSnapshot:
      type: object
      properties:
        market:
          type: string
          example: AAPL-USD.P
        time:
          type: string
          format: date-time
        asks:
          type: array
          items:
            $ref: '#/components/schemas/BookLevel'
        bids:
          type: array
          items:
            $ref: '#/components/schemas/BookLevel'
        depthLevels:
          type: string
          description: Price grouping level (if requested)
      example:
        market: AAPL-USD.P
        time: '2025-03-05T14:30:00Z'
        asks:
          - - '227.60'
            - '80.0'
          - - '227.70'
            - '150.0'
        bids:
          - - '227.40'
            - '100.0'
          - - '227.30'
            - '250.0'
    BookLevel:
      type: array
      description: Price level represented as [price, quantity]
      items:
        type: string
      minItems: 2
      maxItems: 2
      example:
        - '227.50'
        - '100.0'

````