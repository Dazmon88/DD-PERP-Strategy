> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Funding Rates

> Subscribe to the `fundingRatesPerps` channel.

Optional `markets` to filter.



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/fundingRatesPerps
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
  /ws/fundingRatesPerps:
    post:
      tags:
        - Public Channels
      summary: 'Subscribe: Perps Funding Rates'
      description: |-
        Subscribe to the `fundingRatesPerps` channel.

        Optional `markets` to filter.
      operationId: subscribe_fundingRatesPerps
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
                    - fundingRatesPerps
                  example: fundingRatesPerps
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
              channel: fundingRatesPerps
              markets:
                - NVDA-USD.P
      responses:
        '200':
          description: Channel update for `fundingRatesPerps`
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
                      - fundingRatesPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/FundingRate'
components:
  schemas:
    FundingRate:
      type: object
      properties:
        market:
          type: string
          example: AAPL-USD.P
        rate:
          type: string
          example: '0.0000125'
        intervalEnds:
          type: string
          format: date-time
        premiums:
          type: array
          items:
            $ref: '#/components/schemas/PremiumIndexValue'
    PremiumIndexValue:
      type: object
      properties:
        market:
          type: string
        time:
          type: string
          format: date-time
        mark:
          type: string
          description: Mark price
        bid:
          type: string
          description: Best bid
        ask:
          type: string
          description: Best ask
        premiumIndex:
          type: string

````