> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Candles

> Returns OHLCV candlestick data for a perpetual futures market as an array of objects, each with the full field names `startTime`, `open`, `high`, `low`, `close`, and `volume` (values are strings). If you need the TradingView UDF format instead (parallel `o`/`h`/`l`/`c`/`v` arrays of numbers), use `GET /v1/perps/history` (Get Price History).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/candles
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
  /v1/perps/candles:
    get:
      tags:
        - Market Data
      summary: Get Candles
      description: >-
        Returns OHLCV candlestick data for a perpetual futures market as an
        array of objects, each with the full field names `startTime`, `open`,
        `high`, `low`, `close`, and `volume` (values are strings). If you need
        the TradingView UDF format instead (parallel `o`/`h`/`l`/`c`/`v` arrays
        of numbers), use `GET /v1/perps/history` (Get Price History).
      operationId: getPerpsCandles
      parameters:
        - name: market
          in: query
          description: Perps trading market
          required: true
          schema:
            type: string
            example: AAPL-USD.P
        - name: resolution
          in: query
          description: >-
            Bar resolution. If the string has no "D", "W", or "M" suffix it is
            interpreted as minutes (e.g. 1, 5, 15, 30, 60, 240). Use suffixes
            for daily (e.g. 1D), weekly (1W), or monthly (1M).
          required: true
          schema:
            type: string
            example: '1'
        - name: from
          in: query
          description: Start of the requested time range (Unix timestamp in seconds)
          required: true
          schema:
            type: integer
            example: 1684814400
        - name: to
          in: query
          description: End of the requested time range (Unix timestamp in seconds)
          required: true
          schema:
            type: integer
            example: 1684900800
      responses:
        '200':
          description: Array of OHLCV candles
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        type: array
                        items:
                          $ref: '#/components/schemas/ApiCandle'
              example:
                success: true
                result:
                  - startTime: '2025-03-05T14:00:00Z'
                    open: '226.80'
                    high: '228.10'
                    low: '226.50'
                    close: '227.50'
                    volume: '12345.67'
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
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
components:
  schemas:
    GenericResponse:
      type: object
      required:
        - success
      properties:
        success:
          type: boolean
          description: Whether the request was successful
          example: true
        error:
          type: string
          description: Error message, present only on failure
          example: ''
        error_code:
          type: string
          description: >-
            Semantic error code. See each endpoint's error responses for the
            specific codes it can return.
        deprecated:
          type: string
          description: Deprecation notice, if applicable
          example: ''
    ApiCandle:
      type: object
      required:
        - startTime
        - open
        - high
        - low
        - close
        - volume
      properties:
        startTime:
          type: string
          format: date-time
          description: Start time of the candle
          example: '2024-01-04T16:00:00Z'
        open:
          type: string
          description: Opening price
          example: '150.25'
        high:
          type: string
          description: Highest price during the interval
          example: '152.10'
        low:
          type: string
          description: Lowest price during the interval
          example: '149.80'
        close:
          type: string
          description: Closing price
          example: '151.45'
        volume:
          type: string
          description: Trading volume in base currency during the interval
          example: '1234.56'
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
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY-ID

````