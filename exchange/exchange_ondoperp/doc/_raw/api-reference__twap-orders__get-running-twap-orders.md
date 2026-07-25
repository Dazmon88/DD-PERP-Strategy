> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Running TWAP Orders

> Returns all currently running TWAP orders for the authenticated account. Optionally filter by market. For how TWAP execution works, see [TWAP orders](/time-weighted-average-price).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/twap/orders/running
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
  /v1/perps/twap/orders/running:
    get:
      tags:
        - TWAP Orders
      summary: Get Running TWAP Orders
      description: >-
        Returns all currently running TWAP orders for the authenticated account.
        Optionally filter by market. For how TWAP execution works, see [TWAP
        orders](/time-weighted-average-price).
      operationId: getTWAPRunningOrders
      parameters:
        - name: market
          in: query
          description: Filter by market
          required: false
          schema:
            type: string
            example: AAPL-USD.P
      responses:
        '200':
          description: Array of running TWAP orders
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
                          $ref: '#/components/schemas/TWAPOrderApiResp'
              example:
                success: true
                result:
                  - twapId: twap_70a37d8f972f2494837f9dba8364cbb4
                    market: AAPL-USD.P
                    side: buy
                    startTime: '2025-03-05T14:00:00Z'
                    runningTime: 3600
                    frequency: 60
                    avgFilledPrice: '227.42'
                    filledSize: '10.00'
                    totalSize: '20.00'
                    totalFees: '1.14'
                    orderStatus: running
                    reduceOnly: false
                    successfulOrders: 30
                    failedOrders: 0
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
                      - feature_disabled
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
    TWAPOrderApiResp:
      type: object
      required:
        - twapId
        - market
        - side
        - startTime
        - runningTime
        - frequency
        - avgFilledPrice
        - filledSize
        - totalSize
        - totalFees
        - orderStatus
        - reduceOnly
      properties:
        twapId:
          type: string
          description: TWAP order ID
          example: twap_70a37d8f972f2494837f9dba8364cbb4
        market:
          type: string
          description: Perps market
          example: AAPL-USD.P
        side:
          type: string
          description: Order side
          enum:
            - buy
            - sell
          example: buy
        startTime:
          type: string
          format: date-time
          description: Time the TWAP order was created
          example: '2024-01-04T16:00:00Z'
        finishTime:
          type: string
          format: date-time
          description: >-
            Time the TWAP order completed or was cancelled (omitted if still
            running)
          example: '2024-01-04T17:00:00Z'
        runningTime:
          type: integer
          description: Total duration of the TWAP order in seconds
          example: 3600
        frequency:
          type: integer
          description: Interval between child orders in seconds
          example: 60
        avgFilledPrice:
          type: string
          description: Volume-weighted average fill price across all child orders
          example: '150.25'
        filledSize:
          type: string
          description: Total base size filled across all child orders
          example: '10.00'
        totalSize:
          type: string
          description: Total target base size of the TWAP order
          example: '20.30'
        totalFees:
          type: string
          description: Total fees paid across all child orders
          example: '0.152'
        orderStatus:
          type: string
          description: Status of the TWAP order
          example: running
        reduceOnly:
          type: boolean
          description: Whether child orders are reduce-only
          example: false
        maxPrice:
          type: string
          description: Maximum allowed price for child orders (omitted if not set)
          example: '160.00'
        minPrice:
          type: string
          description: Minimum allowed price for child orders (omitted if not set)
          example: '140.00'
        successfulOrders:
          type: integer
          description: Number of successfully placed child orders (omitted if zero)
          example: 30
        failedOrders:
          type: integer
          description: Number of failed child order placements (omitted if zero)
          example: 0
        twapCancelReason:
          type: integer
          description: >-
            Reason the TWAP order was cancelled (only set if cancelled). Values:
            `0` not cancelled, `1` cancelled by user, `2` cancelled after too
            many failed child orders.
          enum:
            - 0
            - 1
            - 2
          example: 1
        lastChildOrderError:
          type: string
          description: >-
            Error code of the last failed child order (only set for running
            orders, never for historical)
          example: twap_child_order_not_fully_filled
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