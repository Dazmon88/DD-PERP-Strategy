> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Subscribe: Perps Liquidation Announcements

> Subscribe to the `liquidationAnnouncementsPerps` channel. Requires authentication (login first).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/liquidationAnnouncementsPerps
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
  /ws/liquidationAnnouncementsPerps:
    post:
      tags:
        - Private Channels
      summary: 'Subscribe: Perps Liquidation Announcements'
      description: >-
        Subscribe to the `liquidationAnnouncementsPerps` channel. Requires
        authentication (login first).
      operationId: subscribe_liquidationAnnouncementsPerps
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
                    - liquidationAnnouncementsPerps
                  example: liquidationAnnouncementsPerps
                  description: Channel for this subscription.
            example:
              op: subscribe
              channel: liquidationAnnouncementsPerps
      responses:
        '200':
          description: Channel update for `liquidationAnnouncementsPerps`
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
                      - liquidationAnnouncementsPerps
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/LiquidationAnnouncement'
components:
  schemas:
    LiquidationAnnouncement:
      type: object
      properties:
        id:
          type: string
        status:
          type: string
          enum:
            - active
            - resolved
        nextOffload:
          type: string
          format: date-time
        orders:
          type: array
          items:
            type: object
            properties:
              market:
                type: string
              side:
                type: string
                enum:
                  - buy
                  - sell
              price:
                type: string
              quantity:
                type: string
              positionSize:
                type: string

````