> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Kline / Candlesticks

> Subscribe to the `kLinePerps` channel.

**Required**: exactly one `markets` entry and a `resolution`.

Valid resolutions: `1`, `5`, `15`, `1H`, `4H`, `1D`, `1W`.



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/kLinePerps
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
  /ws/kLinePerps:
    post:
      tags:
        - Public Channels
      summary: 'Subscribe: Perps Kline / Candlesticks'
      description: |-
        Subscribe to the `kLinePerps` channel.

        **Required**: exactly one `markets` entry and a `resolution`.

        Valid resolutions: `1`, `5`, `15`, `1H`, `4H`, `1D`, `1W`.
      operationId: subscribe_kLinePerps
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - op
                - channel
                - markets
                - resolution
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
                    - kLinePerps
                  example: kLinePerps
                  description: Channel for this subscription.
                markets:
                  type: array
                  items:
                    type: string
                  example:
                    - NVDA-USD.P
                  description: Market to subscribe to. Exactly one market is required.
                resolution:
                  type: string
                  enum:
                    - '1'
                    - '5'
                    - '15'
                    - 1H
                    - 4H
                    - 1D
                    - 1W
                  example: 1H
                  description: Kline resolution.
            example:
              op: subscribe
              channel: kLinePerps
              markets:
                - NVDA-USD.P
              resolution: 1H
      responses:
        '200':
          description: Channel update for `kLinePerps`
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
                      - kLinePerps
                  data:
                    $ref: '#/components/schemas/Kline'
              example:
                type: update
                channel: kLinePerps
                data:
                  m: AAPL-USD.P
                  t: 1709648400
                  s: 1709648340
                  e: 1709648400
                  o: 226.8
                  h: 228.1
                  l: 226.5
                  c: 227.5
                  v: 12345.67
                  x: false
components:
  schemas:
    Kline:
      type: object
      description: Candlestick/kline data point
      properties:
        m:
          type: string
          description: Market
          example: AAPL-USD.P
        t:
          type: integer
          format: int64
          description: Bar timestamp (Unix seconds)
        s:
          type: integer
          format: int64
          description: Interval start (Unix seconds)
        e:
          type: integer
          format: int64
          description: Interval end (Unix seconds)
        o:
          type: number
          description: Open price
          example: 226.8
        h:
          type: number
          description: High price
          example: 228.1
        l:
          type: number
          description: Low price
          example: 226.5
        c:
          type: number
          description: Close price
          example: 227.5
        v:
          type: number
          description: Volume
          example: 12345.67
        x:
          type: boolean
          description: Whether this bar is closed
          example: false

````