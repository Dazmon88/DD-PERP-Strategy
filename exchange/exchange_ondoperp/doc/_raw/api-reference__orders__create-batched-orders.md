> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Create Batched Orders

> Creates multiple orders in a single API call. Some orders may succeed while others fail. The response code is 2XX as long as there is no internal server error. Returns 400 with `error_code=batch_order_empty` if the `orders` array is empty. Returns 400 with `error_code=batch_order_too_many_orders` if too many orders are provided (max 20). For the available order types and their behavior, see [Order types](/order-types).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/perps/orders/batch
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
    post:
      tags:
        - Orders
      summary: Create Batched Orders
      description: >-
        Creates multiple orders in a single API call. Some orders may succeed
        while others fail. The response code is 2XX as long as there is no
        internal server error. Returns 400 with `error_code=batch_order_empty`
        if the `orders` array is empty. Returns 400 with
        `error_code=batch_order_too_many_orders` if too many orders are provided
        (max 20). For the available order types and their behavior, see [Order
        types](/order-types).
      operationId: createBatchOrders
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BatchAddOrderReq'
      responses:
        '200':
          description: Batch order result
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/BatchAddOrderRes'
              example:
                success: true
                result:
                  addedOrders:
                    - orderId: 197ec08e001658690721be129e7fa595
                      side: buy
                      price: '227.50'
                      size: '10.00'
                      market: AAPL-USD.P
                      filledSize: '0.00'
                      lastFillSize: '0.00'
                      filledCost: '0.00'
                      fee: '0.00'
                      status: open
                      createdAt: '2025-03-05T14:30:00Z'
                      type: limit
                  failedOrders: []
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
                      - account_in_liquidation
                      - batch_order_empty
                      - batch_order_too_many_orders
                      - clientOrderID_chars_invalid
                      - clientOrderID_collision
                      - clientOrderID_length_invalid
                      - deprecated_field
                      - insufficient_funds
                      - insufficient_liquidity
                      - insufficient_margin
                      - invalid_market
                      - invalid_market_order_fields
                      - invalid_order_type
                      - invalid_stop_order
                      - invalid_time_in_force
                      - mark_price_not_available
                      - market_orders_disabled
                      - net_position_too_large
                      - order_invalid_price
                      - order_invalid_size
                      - order_matches_against_self
                      - order_negative_price
                      - order_negative_size
                      - order_price_outside_min_max_bounds
                      - order_price_outside_safe_bounds
                      - post_only_has_match
                      - price_over_ui_limit_10MM
                      - redirect
                      - reduce_only_flipping_position
                      - reduce_only_increasing_position
                      - reduce_only_invalid_tif
                      - reduce_only_no_open_position
                      - stop_order_crosses_mark_price
                      - stop_order_crosses_order_price
                      - stop_order_trigger_price_exceeds_max
                      - stop_order_trigger_price_invalid_increment
                      - stop_order_trigger_price_negative
                      - too_many_open_orders
                      - trading_disabled
              example:
                success: false
                error: Description of the error
                error_code: account_in_liquidation
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
    BatchAddOrderReq:
      type: object
      required:
        - orders
      properties:
        orders:
          type: array
          description: >
            Array of order requests. Must have at least 1 element and at most
            20.
          minItems: 1
          maxItems: 20
          items:
            $ref: '#/components/schemas/AddOrderReq'
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
    BatchAddOrderRes:
      type: object
      properties:
        addedOrders:
          type: array
          description: Orders that were successfully added
          items:
            $ref: '#/components/schemas/ApiOrder'
        failedOrders:
          type: array
          description: Orders that were not added and the reason why
          items:
            $ref: '#/components/schemas/ErroredAddOrderReq'
    AddOrderReq:
      type: object
      required:
        - side
        - market
      properties:
        side:
          type: string
          description: buy or sell
          enum:
            - buy
            - sell
          example: buy
        price:
          type: string
          description: >-
            Limit price. Must be aligned with quoteIncrement from /v1/markets.
            Omit for market orders.
          example: '1.55'
        size:
          type: string
          description: >
            Order quantity in base currency. Used for both limit and market
            orders. Must be aligned with baseIncrement from /v1/markets.
          example: '20.30'
        quoteSize:
          type: string
          description: >-
            Order quantity in quote currency. Can only be set for market order
            buys.
          example: '13.0967'
        market:
          type: string
          description: Trading market pair
          example: AAPL-USD.P
        clientOrderId:
          type: string
          description: >
            Optional client-provided order ID. Must be alphanumeric including
            underscores and dashes, and at most 64 characters.
          example: order123
        type:
          type: string
          description: Order type. Defaults to "limit".
          enum:
            - limit
            - market
          example: limit
        timeInForce:
          type: string
          description: >
            "GTC" (Good until cancelled) or "IOC" (Immediate or cancel). Cannot
            be set for market orders. Defaults to "GTC".
          enum:
            - GTC
            - IOC
          example: GTC
        postOnly:
          type: boolean
          description: >
            If true, the order is rejected if it would match at placement.
            Returns 400 with error `post_only_has_match` if it would match.
          example: false
        reduceOnly:
          type: boolean
          description: If true, the order can only reduce an existing position.
          example: false
        takeProfit:
          $ref: '#/components/schemas/StopOrderReq'
        stopLoss:
          $ref: '#/components/schemas/StopOrderReq'
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
    ErroredAddOrderReq:
      type: object
      properties:
        order:
          $ref: '#/components/schemas/AddOrderReq'
        error:
          type: string
          description: Error message explaining why the order failed
          example: insufficient margin
        errorCode:
          type: string
          description: Semantic error code, empty if not a semantic error
          example: insufficient_margin
    StopOrderReq:
      type: object
      required:
        - triggerPrice
      properties:
        triggerPrice:
          type: string
          description: Trigger price for the stop order
          example: '18000.00'
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