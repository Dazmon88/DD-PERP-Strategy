> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get TWAP Order Fills

> Returns all fills for all child orders of a TWAP order. For how TWAP execution works, see [TWAP orders](/time-weighted-average-price).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/twap/order/{orderID}/fills
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
  /v1/perps/twap/order/{orderID}/fills:
    get:
      tags:
        - TWAP Orders
      summary: Get TWAP Order Fills
      description: >-
        Returns all fills for all child orders of a TWAP order. For how TWAP
        execution works, see [TWAP orders](/time-weighted-average-price).
      operationId: getTWAPOrderFills
      parameters:
        - name: orderID
          in: path
          description: TWAP order ID (prefixed with `twap_`)
          required: true
          schema:
            type: string
            example: twap_70a37d8f972f2494837f9dba8364cbb4
      responses:
        '200':
          description: List of fills for all child orders
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
                          $ref: '#/components/schemas/ApiFill'
              example:
                success: true
                result:
                  - id: 70a37d8f972f2494837f9dba8364cbb4
                    orderId: child_abc123
                    parentOrderID: twap_70a37d8f972f2494837f9dba8364cbb4
                    market: AAPL-USD.P
                    price: '227.50'
                    size: '0.33'
                    side: buy
                    filledCost: '75.08'
                    fee: '0.04'
                    time: '2025-03-05T14:01:00Z'
                    isMaker: false
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
                      - feature_disabled
                      - invalid_twap_order_id
                      - missing_twap_order_id
                      - twap_order_not_found
              example:
                success: false
                error: Description of the error
                error_code: feature_disabled
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
    ApiFill:
      type: object
      required:
        - id
        - orderId
        - market
        - price
        - size
        - side
        - filledCost
        - fee
        - time
        - isMaker
      properties:
        id:
          type: string
          description: Fill ID
          example: 70a37d8f972f2494837f9dba8364cbb4
        orderId:
          type: string
          description: Order ID this fill belongs to
          example: 197ec08e001658690721be129e7fa595
        clientOrderId:
          type: string
          description: Client order ID (if set on the order)
          example: order123
        parentOrderID:
          type: string
          description: Parent order ID (e.g. for TWAP child orders)
          example: 70a37d8f972f2494837f9dba8364cbb4
        market:
          type: string
          description: Trading market
          example: AAPL-USD.P
        price:
          type: string
          description: Fill price
          example: '1.55'
        size:
          type: string
          description: Fill quantity in base currency
          example: '5.403'
        side:
          type: string
          description: buy or sell
          enum:
            - buy
            - sell
          example: buy
        direction:
          type: string
          description: >
            Trade direction for perps fills. One of: "open long", "open short",
            "close long", "close short", "flip long to short", "flip short to
            long"
          example: openLong
          enum:
            - openLong
            - openShort
            - closeLong
            - closeShort
            - flipLongToShort
            - flipShortToLong
        filledCost:
          type: string
          description: Total cost of the fill in quote currency
          example: '8.37465'
        fee:
          type: string
          description: Fees incurred on this fill
          example: '0.0837'
        feeRebate:
          type: string
          description: Fee rebate earned on this fill (perps only)
          example: '0.0042'
        pnl:
          type: string
          description: Realized PNL for this fill (perps only)
          example: '1.2345'
        time:
          type: string
          format: date-time
          description: Time the fill occurred
          example: '2022-06-16T12:35:11.123456Z'
        isMaker:
          type: boolean
          description: True if this was a maker (resting) fill
          example: false
        isADL:
          type: boolean
          description: True if this was an auto-deleveraging fill (perps only)
          example: false
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