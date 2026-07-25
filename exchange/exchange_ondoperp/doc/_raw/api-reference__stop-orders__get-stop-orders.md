> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Stop Orders

> Gets a list of all stop orders for all markets. This section covers Position-Level stop orders only (take-profit and stop-loss attached to open positions). For TP/SL attached to limit orders, see the order creation payload (takeProfit, stopLoss, etc.). For how stop orders work, see [Take profit and stop loss](/take-profit-and-stop-loss).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/stop_order
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
  /v1/perps/stop_order:
    get:
      tags:
        - Stop Orders
      summary: Get Stop Orders
      description: >-
        Gets a list of all stop orders for all markets. This section covers
        Position-Level stop orders only (take-profit and stop-loss attached to
        open positions). For TP/SL attached to limit orders, see the order
        creation payload (takeProfit, stopLoss, etc.). For how stop orders work,
        see [Take profit and stop loss](/take-profit-and-stop-loss).
      operationId: getStopOrders
      responses:
        '200':
          description: List of stop orders across all markets and position directions
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
                          $ref: '#/components/schemas/ApiStopOrders'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    positionDirection: long
                    stopLoss: '200.00'
                    takeProfit: '260.00'
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
    ApiStopOrders:
      type: object
      required:
        - market
        - positionDirection
      properties:
        market:
          type: string
          description: Perps market
          example: AAPL-USD.P
        positionDirection:
          type: string
          description: Position direction this stop order watches
          enum:
            - long
            - short
            - neutral
          example: long
        stopLoss:
          type: string
          nullable: true
          description: Stop loss trigger price, if set
          example: '8.00'
        takeProfit:
          type: string
          nullable: true
          description: Take profit trigger price, if set
          example: '9.00'
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