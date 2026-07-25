> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Batch Cancel Orders

> Cancels multiple orders in a single call. Returns results for each order. Provide a comma-separated list of order IDs via the `orderIDs` query parameter. Each entry can be an internal order ID or `client:{clientOrderID}`.




## OpenAPI

````yaml /api-reference/rest-spec.json delete /v1/perps/orders/batch
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
  /v1/perps/orders/batch:
    delete:
      tags:
        - Orders
      summary: Batch Cancel Orders
      description: >
        Cancels multiple orders in a single call. Returns results for each
        order. Provide a comma-separated list of order IDs via the `orderIDs`
        query parameter. Each entry can be an internal order ID or
        `client:{clientOrderID}`.
      operationId: batchCancelOrders
      parameters:
        - name: orderIDs
          in: query
          description: Comma-separated list of order IDs to cancel
          required: true
          schema:
            type: string
            example: abc123,def456
      responses:
        '200':
          description: Batch cancel result
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/BatchCancelResult'
              example:
                success: true
                result:
                  successfulCancels:
                    - orderId: 197ec08e001658690721be129e7fa595
                      side: buy
                      price: '227.50'
                      size: '10.00'
                      market: AAPL-USD.P
                      filledSize: '0.00'
                      lastFillSize: '0.00'
                      filledCost: '0.00'
                      fee: '0.00'
                      status: canceled
                      createdAt: '2025-03-05T14:30:00Z'
                      canceledAt: '2025-03-05T14:35:00Z'
                      type: limit
                  failedCancels: []
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
                      - batch_cancel_empty
                      - batch_cancel_too_many_orders
                      - order_already_canceled
                      - order_already_fully_filled
                      - order_not_found
                      - order_not_in_cancelable_state
                      - trading_disabled
              example:
                success: false
                error: Description of the error
                error_code: batch_cancel_empty
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
    BatchCancelResult:
      type: object
      properties:
        successfulCancels:
          type: array
          description: Orders that were successfully cancelled
          items:
            $ref: '#/components/schemas/ApiOrder'
        failedCancels:
          type: array
          description: Cancel attempts that failed
          items:
            $ref: '#/components/schemas/CancelError'
    ApiOrder:
      type: object
      required:
        - orderId
        - side
        - price
        - size
        - market
        - filledSize
        - lastFillSize
        - filledCost
        - fee
        - status
        - createdAt
        - type
      properties:
        orderId:
          type: string
          description: Internal order ID
          example: 70a37d8f972f2494837f9dba8364cbb4
        clientOrderId:
          type: string
          description: Client-provided order ID (if set)
          example: order123
        parentOrderId:
          type: string
          description: Parent order ID (e.g. for TWAP child orders)
          example: twap_70a37d8f972f2494837f9dba8364cbb4
        side:
          type: string
          description: buy or sell
          enum:
            - buy
            - sell
          example: buy
        price:
          type: string
          description: Limit price
          example: '1.55'
        size:
          type: string
          description: Order quantity in base currency
          example: '20.30'
        market:
          type: string
          description: Trading market
          example: AAPL-USD.P
        filledSize:
          type: string
          description: Quantity of the order that has been filled
          example: '5.403'
        lastFillSize:
          type: string
          description: Quantity filled in the most recent trade
          example: '5.403'
        filledCost:
          type: string
          description: Cost of the filled portion of the order (filledSize × fill price)
          example: '8.37465'
        realizedPnl:
          type: string
          description: Realized PNL for this order (perps only)
          example: '1.2345'
        fee:
          type: string
          description: Fees incurred on this order
          example: '0.0837'
        feeRebate:
          type: string
          description: Fee rebate earned on this order (perps only)
          example: '0.0042'
        status:
          type: string
          description: Order status
          enum:
            - open
            - fullyfilled
            - canceled
            - pending
            - untriggered
          example: open
        createdAt:
          type: string
          format: date-time
          description: Order creation time
          example: '2022-06-16T12:35:11.123456Z'
        filledAt:
          type: string
          format: date-time
          description: Time when the order was fully filled (if applicable)
          example: '2022-06-16T12:35:11.123456Z'
        canceledAt:
          type: string
          format: date-time
          description: Order cancellation time (if cancelled)
          example: '2022-06-16T12:35:11.123456Z'
        cancelReason:
          type: string
          description: >
            Reason the order was cancelled. Possible values: "" (user
            cancelled), "liquidation", "selfmatchprevention",
            "cancelaftertimeout", "startupbadprice", "immediateorcancel"
          example: liquidation
          enum:
            - ''
            - liquidation
            - selfMatchPrevention
            - cancelAfterTimeout
            - startupBadPrice
            - immediateOrCancel
            - cancelAfterTimeoutOnShutdown
            - cancelOnStartup
            - cancelByAdmin
            - positionClosed
            - stopOrderPositionNeutral
            - stopOrderPositionDirectionMismatch
            - stopOrderInLiquidation
            - stopOrderInternalError
        type:
          type: string
          description: Order type
          enum:
            - limit
            - market
            - stopMarket
            - takeProfitMarket
          example: limit
        timeInForce:
          type: string
          description: Time in force (GTC or IOC). Not returned for market orders.
          enum:
            - GTC
            - IOC
          example: GTC
        reduceOnly:
          type: boolean
          description: Whether the order is reduce-only
          example: false
        liquidationId:
          type: string
          description: ID of the liquidation event this order participated in (perps only)
          example: a1b2c3d4e5f60718293a4b5c6d7e8f90
        closePosition:
          type: boolean
          description: True if this is a position-level TP/SL order
          example: false
        stopOrderType:
          type: string
          description: Stop order type (stopLoss or takeProfit), if applicable
          enum:
            - stopLoss
            - takeProfit
        triggerPrice:
          type: string
          description: Trigger price for stop orders
          example: '125.50'
    CancelError:
      type: object
      properties:
        orderId:
          type: string
          description: Order ID that failed to cancel
          example: 70a37d8f972f2494837f9dba8364cbb4
        error:
          type: string
          description: Error message explaining why the cancel failed
          example: order_already_canceled
        errorCode:
          type: string
          description: Semantic error code (empty if not a semantic error)
          example: order_already_canceled
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