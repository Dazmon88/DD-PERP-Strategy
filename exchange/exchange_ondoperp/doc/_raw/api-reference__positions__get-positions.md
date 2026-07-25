> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Positions

> Returns all open positions for the authenticated account. For how positions and balances work, see [Positions and balances](/positions-balances).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/positions
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
  /v1/perps/positions:
    get:
      tags:
        - Positions
      summary: Get Positions
      description: >-
        Returns all open positions for the authenticated account. For how
        positions and balances work, see [Positions and
        balances](/positions-balances).
      operationId: getPerpsPositions
      responses:
        '200':
          description: List of positions
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
                          $ref: '#/components/schemas/ApiPosition'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    direction: long
                    netQuantity: '10.00'
                    averageEntryPrice: '225.00'
                    usedMargin: '1125.00'
                    unrealizedPnl: '25.00'
                    markPrice: '227.50'
                    liquidationPrice: '180.00'
                    bankruptcyPrice: '170.00'
                    maintenanceMargin: '112.50'
                    notionalValue: '2275.00'
                    leverage: '2.0'
                    netFundingSinceNeutral: '-1.23'
                    returnOnEquity: '0.022'
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
    ApiPosition:
      type: object
      required:
        - market
        - direction
        - netQuantity
        - averageEntryPrice
        - usedMargin
        - unrealizedPnl
        - markPrice
        - liquidationPrice
        - bankruptcyPrice
        - maintenanceMargin
        - notionalValue
        - leverage
        - netFundingSinceNeutral
        - returnOnEquity
      properties:
        market:
          type: string
          description: Perps market
          example: AAPL-USD.P
        direction:
          type: string
          description: Position direction
          enum:
            - long
            - short
            - neutral
          example: short
        netQuantity:
          type: string
          description: Size of the position in base currency
          example: '1.5489'
        averageEntryPrice:
          type: string
          description: Average entry price
          example: '20566.84'
        usedMargin:
          type: string
          description: Margin used for the position
          example: '2566.84'
        unrealizedPnl:
          type: string
          description: >-
            Unrealized PNL relative to the mark price. Positive is profit,
            negative is loss.
          example: '-900.54'
        markPrice:
          type: string
          description: Current mark price
          example: '20000.54'
        liquidationPrice:
          type: string
          description: Price at which the position will be liquidated
          example: '9000.87'
        bankruptcyPrice:
          type: string
          description: Price at which bankruptcy occurs during liquidation
          example: '6000.11'
        maintenanceMargin:
          type: string
          description: Maintenance margin required for this position
          example: '1500.22'
        notionalValue:
          type: string
          description: Notional value of the position
          example: '30000.00'
        leverage:
          type: string
          description: Current effective leverage for this position
          example: '10.0'
        netFundingSinceNeutral:
          type: string
          description: Net funding payments since the position was opened
          example: '-12.34'
        returnOnEquity:
          type: string
          description: Return on equity for this position
          example: '-0.35'
        stopLossTriggerPrice:
          type: string
          description: Triggering price for stop loss order (optional)
          example: '18000.00'
        takeProfitTriggerPrice:
          type: string
          description: Triggering price for take profit order (optional)
          example: '25000.00'
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