> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Login

> Authenticate the WebSocket connection. Required before subscribing to private channels.

**JWT login**: provide `args.token`.

**API key login**: provide `args.key`, `args.time` (Unix milliseconds), and `args.sign` (HMAC-SHA256 of `time + "ondo_perps_ws_login"` using your API secret, hex-encoded).



## OpenAPI

````yaml /api-reference/ws-spec.json post /ws/login
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
  /ws/login:
    post:
      tags:
        - Connection
      summary: Login
      description: >-
        Authenticate the WebSocket connection. Required before subscribing to
        private channels.


        **JWT login**: provide `args.token`.


        **API key login**: provide `args.key`, `args.time` (Unix milliseconds),
        and `args.sign` (HMAC-SHA256 of `time + "ondo_perps_ws_login"` using
        your API secret, hex-encoded).
      operationId: wsLogin
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - op
                - args
              properties:
                op:
                  type: string
                  enum:
                    - login
                  example: login
                  description: Operation type.
                args:
                  $ref: '#/components/schemas/LoginArgs'
            example:
              op: login
              args:
                token: <JWT>
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  type:
                    type: string
                    enum:
                      - loggedIn
                  msg:
                    type: string
              example:
                type: loggedIn
                msg: Login successful
        '400':
          description: Login failed
          content:
            application/json:
              schema:
                type: object
                properties:
                  type:
                    type: string
                    enum:
                      - error
                  msg:
                    type: string
                    enum:
                      - already logged in on this connection
                      - account already has too many connections
components:
  schemas:
    LoginArgs:
      type: object
      description: >-
        Authentication arguments. Use either JWT (token) or API key (key + time
        + sign).
      properties:
        token:
          type: string
          description: JWT token
        key:
          type: string
          description: API key ID
        time:
          type: string
          description: Unix timestamp in milliseconds
        sign:
          type: string
          description: HMAC-SHA256 hex signature

````