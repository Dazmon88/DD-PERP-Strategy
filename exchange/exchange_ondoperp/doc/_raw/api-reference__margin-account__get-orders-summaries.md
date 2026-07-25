> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Orders Summaries

> Returns a summary of resting orders, position, and market order margin requirements for each market.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/orders_summaries
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
  /v1/perps/orders_summaries:
    get:
      tags:
        - Margin Account
      summary: Get Orders Summaries
      description: >-
        Returns a summary of resting orders, position, and market order margin
        requirements for each market.
      operationId: getPerpsOrdersSummaries
      responses:
        '200':
          description: Array of per-market order summaries
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
                          $ref: '#/components/schemas/GetOrdersSummariesRes'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    restingOrdersSummary:
                      bidsInitialMargin: '100.00'
                      asksInitialMargin: '80.00'
                      bidsOpenLoss: '5.00'
                      asksOpenLoss: '3.00'
                      bidsBaseSize: '10.00'
                      asksBaseSize: '8.00'
                      bidsMaintenanceMargin: '50.00'
                      asksMaintenanceMargin: '40.00'
                    positionSummary:
                      bidsInitialMargin: '1125.00'
                      asksInitialMargin: '0.00'
                      bidsBaseSize: '10.00'
                      asksBaseSize: '0.00'
                    marketOrderSummary:
                      maxBidQuoteSize: '10000.00'
                      maxBidBaseSize: '43.96'
                      maxAskQuoteSize: '10000.00'
                      maxAskBaseSize: '43.96'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
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
    GetOrdersSummariesRes:
      type: object
      required:
        - market
      properties:
        market:
          type: string
          description: Perps market
          example: AAPL-USD.P
        restingOrdersSummary:
          $ref: '#/components/schemas/OrdersSummary'
        positionSummary:
          $ref: '#/components/schemas/OrdersSummary'
        marketOrderSummary:
          $ref: '#/components/schemas/MarketOrdersSummary'
    OrdersSummary:
      type: object
      properties:
        bidsInitialMargin:
          type: string
          description: Initial margin required for all bid (buy) resting orders
          example: '100.00'
        asksInitialMargin:
          type: string
          description: Initial margin required for all ask (sell) resting orders
          example: '80.00'
        bidsOpenLoss:
          type: string
          description: Unrealized open loss on the bid side that counts toward margin
          example: '5.00'
        asksOpenLoss:
          type: string
          description: Unrealized open loss on the ask side that counts toward margin
          example: '3.00'
        bidsBaseSize:
          type: string
          description: Total base size of all bid resting orders
          example: '10.00'
        asksBaseSize:
          type: string
          description: Total base size of all ask resting orders
          example: '8.00'
        bidsMaintenanceMargin:
          type: string
          description: Maintenance margin required for all bid resting orders
          example: '50.00'
        asksMaintenanceMargin:
          type: string
          description: Maintenance margin required for all ask resting orders
          example: '40.00'
    MarketOrdersSummary:
      type: object
      properties:
        maxBidQuoteSize:
          type: string
          description: Maximum buy market order size in quote currency
          example: '10000.00'
        maxBidBaseSize:
          type: string
          description: Maximum buy market order size in base currency
          example: '5.00'
        maxBidPositionLeverage:
          type: string
          description: Maximum leverage available for a buy market order
          example: '10.0'
        maxAskQuoteSize:
          type: string
          description: Maximum sell market order size in quote currency
          example: '10000.00'
        maxAskBaseSize:
          type: string
          description: Maximum sell market order size in base currency
          example: '5.00'
        maxAskPositionLeverage:
          type: string
          description: Maximum leverage available for a sell market order
          example: '10.0'
  responses:
    Unauthorized:
      description: Authentication required. Provide a valid JWT or API key.
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
                  - api_key_not_found
                  - auth_expired
                  - auth_invalid
                  - auth_missing
                  - failed_to_decode_hex_signature
                  - failed_to_parse_timestamp
                  - signature_mismatch
                  - timestamp_too_far
          example:
            success: false
            error: Description of the error
            error_code: auth_missing
    Forbidden:
      description: Access denied. The authenticated account does not have permission.
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
                  - account_closed
                  - account_not_allowed
                  - forbidden
                  - ip_not_permitted
                  - key_doesnt_have_scope
          example:
            success: false
            error: Description of the error
            error_code: account_not_allowed
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