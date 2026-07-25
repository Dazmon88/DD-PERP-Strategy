> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Trades

> Returns a paginated list of public trades for a market.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/trades
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
  /v1/perps/trades:
    get:
      tags:
        - Market Data
      summary: Get Trades
      description: Returns a paginated list of public trades for a market.
      operationId: getTrades
      parameters:
        - name: market
          in: query
          description: Trading market to query
          required: true
          schema:
            type: string
            example: AAPL-USD.P
        - name: limit
          in: query
          description: Maximum number of results to return
          required: false
          schema:
            type: integer
            example: 100
        - name: cursor
          in: query
          description: Pagination cursor
          required: false
          schema:
            type: string
            example: NQ5WWO3THN3Q====
      responses:
        '200':
          description: Paginated list of trades, most recent first
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
                          $ref: '#/components/schemas/ApiTrade'
                      pageInfo:
                        $ref: '#/components/schemas/PageInfo'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    price: '227.50'
                    size: '5.00'
                    cost: '1137.50'
                    aggressor_side: buy
                    time: '2025-03-05T14:30:00Z'
                    id: 70a37d8f972f2494837f9dba8364cbb4
                pageInfo:
                  nextCursor: NQ5WWO3THN3Q====
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
              example:
                success: false
                error: Description of the error
                error_code: bad_query_param
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
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
    ApiTrade:
      type: object
      required:
        - market
        - price
        - size
        - cost
        - aggressor_side
        - time
        - id
      properties:
        market:
          type: string
          description: Trading market
          example: AAPL-USD.P
        price:
          type: string
          description: Trade price
          example: '1.55'
        size:
          type: string
          description: Trade size in base currency
          example: '5.403'
        cost:
          type: string
          description: Trade cost in quote currency
          example: '8.37465'
        aggressor_side:
          type: string
          description: Side of the aggressing (taker) order
          enum:
            - buy
            - sell
          example: buy
        time:
          type: string
          format: date-time
          description: Time the trade occurred
          example: '2022-06-16T12:35:11.123456Z'
        id:
          type: string
          description: Trade/fill ID
          example: 70a37d8f972f2494837f9dba8364cbb4
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

````