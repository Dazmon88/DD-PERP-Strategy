> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Price History (TradingView)

> Returns historical bar data in TradingView UDF format, as required by the TradingView charting library: a single object with parallel arrays keyed `t`, `o`, `h`, `l`, `c`, and `v` (values are numbers), plus a status field `s`. For a standard array-of-objects representation with full field names (`open`, `high`, `low`, `close`, `volume`), use `GET /v1/perps/candles` (Get Candles).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/history
openapi: 3.0.3
info:
  title: Ondo Perps REST API
  version: '1.0'
  description: >-
    REST API for Ondo Perps: account, wallet, deposits/withdrawals, API keys,
    and perpetual futures trading.
servers:
  - url: https://api.ondoperps.xyz
security:
  - BearerAuth: []
paths:
  /v1/perps/history:
    get:
      tags:
        - Market Data
      summary: Get Price History (TradingView)
      description: >-
        Returns historical bar data in TradingView UDF format, as required by
        the TradingView charting library: a single object with parallel arrays
        keyed `t`, `o`, `h`, `l`, `c`, and `v` (values are numbers), plus a
        status field `s`. For a standard array-of-objects representation with
        full field names (`open`, `high`, `low`, `close`, `volume`), use `GET
        /v1/perps/candles` (Get Candles).
      operationId: getPerpsHistory
      parameters:
        - name: symbol
          in: query
          description: TradingView symbol identifier
          required: true
          schema:
            type: string
        - name: resolution
          in: query
          description: Bar resolution
          required: true
          schema:
            type: string
        - name: from
          in: query
          description: Start Unix timestamp
          required: true
          schema:
            type: integer
        - name: to
          in: query
          description: End Unix timestamp
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: TradingView UDF history response
          content:
            application/json:
              schema:
                type: object
                description: >-
                  TradingView UDF history response with parallel arrays of OHLCV
                  data.
                properties:
                  s:
                    type: string
                    description: Status ('ok' or 'no_data')
                    example: ok
                  t:
                    type: array
                    description: Array of Unix timestamps
                    items:
                      type: integer
                  o:
                    type: array
                    description: Array of open prices
                    items:
                      type: number
                  h:
                    type: array
                    description: Array of high prices
                    items:
                      type: number
                  l:
                    type: array
                    description: Array of low prices
                    items:
                      type: number
                  c:
                    type: array
                    description: Array of close prices
                    items:
                      type: number
                  v:
                    type: array
                    description: Array of volumes
                    items:
                      type: number
              example:
                s: ok
                t:
                  - 1709640000
                  - 1709643600
                o:
                  - 226.8
                  - 227.5
                h:
                  - 228.1
                  - 228.5
                l:
                  - 226.5
                  - 227
                c:
                  - 227.5
                  - 228
                v:
                  - 12345.67
                  - 9876.54
        '400':
          description: Bad request. The request was malformed or failed validation.
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    example: false
                  error:
                    type: string
                    description: Human-readable error message
                  error_code:
                    type: string
                    enum:
                      - bad_query_param
              example:
                success: false
                error: Description of the error
                error_code: bad_query_param
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
components:
  responses:
    TooManyRequests:
      description: Rate limit exceeded. Slow down request frequency.
      content:
        application/json:
          schema:
            type: object
            properties:
              success:
                type: boolean
                example: false
              error:
                type: string
                description: Human-readable error message
              error_code:
                type: string
                enum:
                  - too_many_requests
          example:
            success: false
            error: Description of the error
            error_code: too_many_requests
    InternalServerError:
      description: Internal server error.
      content:
        application/json:
          schema:
            type: object
            properties:
              success:
                type: boolean
                example: false
              error:
                type: string
                description: Human-readable error message
              error_code:
                type: string
                enum:
                  - server_is_busy
                  - service_unavailable
                  - unknown
          example:
            success: false
            error: Description of the error
            error_code: unknown
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

````