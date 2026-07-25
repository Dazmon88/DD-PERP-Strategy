> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Symbol Info (TradingView)

> Returns symbol metadata in TradingView UDF format. See https://www.tradingview.com/rest-api-spec/#operation/getSymbolInfo.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/symbol_info
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
  /v1/perps/symbol_info:
    get:
      tags:
        - Market Data
      summary: Get Symbol Info (TradingView)
      description: >-
        Returns symbol metadata in TradingView UDF format. See
        https://www.tradingview.com/rest-api-spec/#operation/getSymbolInfo.
      operationId: getPerpsSymbolInfo
      responses:
        '200':
          description: TradingView symbol info response
          content:
            application/json:
              schema:
                type: object
                description: >-
                  TradingView UDF symbol info response. Contains arrays of
                  values for each symbol.
                properties:
                  s:
                    type: string
                    description: Status
                    example: ok
                  symbol:
                    type: array
                    items:
                      type: string
                  description:
                    type: array
                    items:
                      type: string
                  ticker:
                    type: array
                    items:
                      type: string
                  currency:
                    type: array
                    items:
                      type: string
                  base-currency:
                    type: array
                    items:
                      type: string
                  type:
                    type: array
                    items:
                      type: string
                  session-regular:
                    type: array
                    items:
                      type: string
                  timezone:
                    type: array
                    items:
                      type: string
                  minmovement:
                    type: array
                    items:
                      type: integer
                  pricescale:
                    type: array
                    items:
                      type: integer
                  has-intraday:
                    type: array
                    items:
                      type: boolean
                  has-no-volume:
                    type: array
                    items:
                      type: boolean
                  supported-resolutions:
                    type: array
                    items:
                      type: array
                      items:
                        type: string
              example:
                s: ok
                symbol:
                  - AAPL-USD.P
                  - TSLA-USD.P
                description:
                  - Apple Inc. Perpetual
                  - Tesla Inc. Perpetual
                ticker:
                  - AAPL-USD.P
                  - TSLA-USD.P
                currency:
                  - USDC
                  - USDC
                base-currency:
                  - AAPL
                  - TSLA
                type:
                  - perpetual
                  - perpetual
                session-regular:
                  - 24x7
                  - 24x7
                timezone:
                  - Etc/UTC
                  - Etc/UTC
                minmovement:
                  - 1
                  - 1
                pricescale:
                  - 100
                  - 100
                has-intraday:
                  - true
                  - true
                has-no-volume:
                  - false
                  - false
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