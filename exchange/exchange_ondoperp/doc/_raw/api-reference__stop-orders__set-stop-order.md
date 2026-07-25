> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Set Stop Order

> Set a stop order for a particular position defined by market and direction. For how stop orders work, see [Take profit and stop loss](/take-profit-and-stop-loss).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/perps/stop_order
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
    post:
      tags:
        - Stop Orders
      summary: Set Stop Order
      description: >-
        Set a stop order for a particular position defined by market and
        direction. For how stop orders work, see [Take profit and stop
        loss](/take-profit-and-stop-loss).
      operationId: setStopOrder
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SetStopOrderReq'
      responses:
        '200':
          description: Updated stop orders for the market
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/ApiStopOrders'
              example:
                success: true
                result:
                  market: AAPL-USD.P
                  positionDirection: long
                  stopLoss: '200.00'
                  takeProfit: null
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
                      - invalid_market
                      - invalid_stop_order
                      - order_invalid_price
                      - price_over_ui_limit_10MM
                      - stop_order_crosses_mark_price
                      - stop_order_crosses_order_price
                      - stop_order_trigger_price_exceeds_max
                      - stop_order_trigger_price_invalid_increment
                      - stop_order_trigger_price_negative
                      - trading_disabled
              example:
                success: false
                error: Description of the error
                error_code: invalid_market
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
    SetStopOrderReq:
      type: object
      required:
        - market
        - positionDirection
        - type
        - triggerPrice
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
          example: long
        type:
          type: string
          description: The type of stop order to set
          enum:
            - stopLoss
            - takeProfit
          example: stopLoss
        triggerPrice:
          type: string
          description: The trigger price
          example: '9.00'
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