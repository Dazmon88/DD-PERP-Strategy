> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Max Order Size

> Get a summary of the maximum order size that can be placed given the current state of the order book and available margin. For how size limits are determined, see [Position size limits](/maximum-position-sizes).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/max_order_size
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
  /v1/perps/max_order_size:
    get:
      tags:
        - Margin Account
      summary: Get Max Order Size
      description: >-
        Get a summary of the maximum order size that can be placed given the
        current state of the order book and available margin. For how size
        limits are determined, see [Position size
        limits](/maximum-position-sizes).
      operationId: getMaxOrderSize
      parameters:
        - name: market
          in: query
          description: Market to estimate max order size for
          required: true
          schema:
            type: string
            example: AAPL-USD.P
        - name: buffer
          in: query
          description: >
            Factor to scale returned sizes to guard against fluctuations between
            calling this endpoint and placing the order. Must be a decimal
            between 0 and 1. Defaults to 0.9.
          required: false
          schema:
            type: string
            example: '0.9'
      responses:
        '200':
          description: Maximum order sizes
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/MaxOrderSizesRes'
              example:
                success: true
                result:
                  percent100:
                    maxBidBaseSize: '43.96'
                    maxAskBaseSize: '43.96'
                  percent75:
                    maxBidBaseSize: '32.97'
                    maxAskBaseSize: '32.97'
                  percent50:
                    maxBidBaseSize: '21.98'
                    maxAskBaseSize: '21.98'
                  percent25:
                    maxBidBaseSize: '10.99'
                    maxAskBaseSize: '10.99'
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
                      - insufficient_margin
                      - invalid_market
              example:
                success: false
                error: Description of the error
                error_code: bad_query_param
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
    MaxOrderSizesRes:
      type: object
      required:
        - percent100
        - percent75
        - percent50
        - percent25
      properties:
        percent100:
          $ref: '#/components/schemas/OrderSizes'
        percent75:
          $ref: '#/components/schemas/OrderSizes'
        percent50:
          $ref: '#/components/schemas/OrderSizes'
        percent25:
          $ref: '#/components/schemas/OrderSizes'
    OrderSizes:
      type: object
      required:
        - maxBidBaseSize
        - maxAskBaseSize
      properties:
        maxBidBaseSize:
          type: string
          description: Allowed buy order size in base asset
          example: '123.4'
        maxAskBaseSize:
          type: string
          description: Allowed ask order size in base asset
          example: '123.4'
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