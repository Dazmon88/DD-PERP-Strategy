> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Orders

> Returns a paginated list of orders matching the given parameters.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/orders
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
  /v1/perps/orders:
    get:
      tags:
        - Orders
      summary: Get Orders
      description: Returns a paginated list of orders matching the given parameters.
      operationId: getOrders
      parameters:
        - name: limit
          in: query
          description: Maximum number of results to return
          required: false
          schema:
            type: integer
            example: 1000
        - name: cursor
          in: query
          description: Pagination cursor
          required: false
          schema:
            type: string
            example: NQ5WWO3THN3Q====
        - name: market
          in: query
          description: Filter by trading market
          required: false
          schema:
            type: string
            example: AAPL-USD.P
        - name: status
          in: query
          description: Filter by order status
          required: false
          schema:
            type: string
            enum:
              - open
              - canceled
              - fullyfilled
            example: open
        - name: startTime
          in: query
          description: Filter orders placed at or after this time (UTC milliseconds)
          required: false
          schema:
            type: integer
            example: 1684814400000
        - name: endTime
          in: query
          description: Filter orders placed at or before this time (UTC milliseconds)
          required: false
          schema:
            type: integer
            example: 1672549200000
      responses:
        '200':
          description: Paginated list of orders, reverse chronological
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
                          $ref: '#/components/schemas/ApiOrder'
                      pageInfo:
                        $ref: '#/components/schemas/PageInfo'
              example:
                success: true
                result:
                  - orderId: 197ec08e001658690721be129e7fa595
                    side: buy
                    price: '227.50'
                    size: '10.00'
                    market: AAPL-USD.P
                    filledSize: '5.00'
                    lastFillSize: '2.50'
                    filledCost: '1137.50'
                    fee: '0.57'
                    status: open
                    createdAt: '2025-03-05T14:30:00Z'
                    type: limit
                    timeInForce: GTC
                    reduceOnly: false
                pageInfo:
                  nextCursor: NQ5WWO3THN3Q====
                  prevCursor: O4ZTGM3RGM2DG===
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
                      - failed_to_parse_timestamp
                      - invalid_cursor
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
    PageInfo:
      type: object
      properties:
        prevCursor:
          type: string
          description: Cursor value to get the previous page of results
          example: O4ZTGM3RGM2DG===
        nextCursor:
          type: string
          description: Cursor value to get the next page of results
          example: NQ5WWO3THN3Q====
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