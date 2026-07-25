> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Margin Transfers

> Subscribe to the `marginTransfersPerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/marginTransfersPerps
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
  /ws/marginTransfersPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Margin Transfers'
      description: >-
        Subscribe to the `marginTransfersPerps` channel. Requires authentication
        (login first).
      operationId: subscribe_marginTransfersPerps
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
                    - marginTransfersPerps
                  example: marginTransfersPerps
                  description: Channel for this subscription.
            example:
              op: subscribe
              channel: marginTransfersPerps
      responses:
        '200':
          description: Channel update for `marginTransfersPerps`
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
                      - marginTransfersPerps
                  data:
                    $ref: '#/components/schemas/MarginTransfer'
components:
  schemas:
    MarginTransfer:
      type: object
      properties:
        id:
          type: string
        from:
          $ref: '#/components/schemas/AccountWalletKey'
        to:
          $ref: '#/components/schemas/AccountWalletKey'
        amount:
          type: string
          example: '1000.00'
        symbol:
          type: string
          example: USDC
        time:
          type: string
          format: date-time
        type:
          type: integer
          description: Transfer type
    AccountWalletKey:
      type: object
      properties:
        id:
          type: string
          description: Account ID
        wallet:
          type: string
          enum:
            - main
            - margin
          description: Wallet type

````