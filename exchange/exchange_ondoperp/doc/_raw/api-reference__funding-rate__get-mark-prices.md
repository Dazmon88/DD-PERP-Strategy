> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Mark Prices

> Get the current mark prices for all perpetual futures markets. For how mark prices are derived, see [External pricing derivations](/pricing-derivations).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/mark_prices
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
  /v1/perps/mark_prices:
    get:
      tags:
        - Funding Rate
      summary: Get Mark Prices
      description: >-
        Get the current mark prices for all perpetual futures markets. For how
        mark prices are derived, see [External pricing
        derivations](/pricing-derivations).
      operationId: getMarkPrices
      responses:
        '200':
          description: Map from market to mark price
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        type: object
                        additionalProperties:
                          $ref: '#/components/schemas/MarkPrice'
              example:
                success: true
                result:
                  AAPL-USD.P:
                    market: AAPL-USD.P
                    pair:
                      base: AAPL
                      quote: USD
                    price: '308.019994'
                    markPrice: '308.019994'
                    oraclePrice: '308.01999499999998975'
                    lastExternalPrice: '308.01999499999998975'
                    lastUpdatedTime: '2026-06-05T21:27:11.077320736Z'
                  TSLA-USD.P:
                    market: TSLA-USD.P
                    pair:
                      base: TSLA
                      quote: USD
                    price: '180.25'
                    markPrice: '180.25'
                    oraclePrice: '180.24500000000000001'
                    lastExternalPrice: '180.24500000000000001'
                    lastUpdatedTime: '2026-06-05T21:27:11.077320736Z'
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
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
    MarkPrice:
      type: object
      required:
        - market
        - pair
        - price
        - markPrice
        - oraclePrice
        - lastExternalPrice
        - lastUpdatedTime
      properties:
        market:
          type: string
          description: The market identifier
          example: AAPL-USD.P
        pair:
          type: object
          description: Currency pair
          properties:
            base:
              type: string
              example: AAPL
            quote:
              type: string
              example: USD
        price:
          type: string
          description: Current mark price (alias of `markPrice`)
          example: '308.019994'
        markPrice:
          type: string
          description: >-
            Current mark price used for PnL, margin, and liquidation
            calculations
          example: '308.019994'
        oraclePrice:
          type: string
          description: Latest oracle price for the market
          example: '308.01999499999998975'
        lastExternalPrice:
          type: string
          description: Most recent external reference price observed for the market
          example: '308.01999499999998975'
        lastUpdatedTime:
          type: string
          format: date-time
          description: Time the mark price was last updated
          example: '2026-06-05T21:27:11.077320736Z'
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