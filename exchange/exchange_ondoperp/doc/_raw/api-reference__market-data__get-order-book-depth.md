> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Order Book Depth

> Returns the current order book depth snapshot for a market.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/depth
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
  /v1/perps/depth:
    get:
      tags:
        - Market Data
      summary: Get Order Book Depth
      description: Returns the current order book depth snapshot for a market.
      operationId: getDepth
      parameters:
        - name: market
          in: query
          description: Trading market to query
          required: true
          schema:
            type: string
            example: AAPL-USD.P
        - name: depth
          in: query
          description: >-
            Number of price levels to return per side. Defaults to 10. Maximum
            100.
          required: false
          schema:
            type: integer
            example: 10
            maximum: 100
      responses:
        '200':
          description: Order book snapshot
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/ApiBookSnapshot'
              example:
                success: true
                result:
                  market: AAPL-USD.P
                  time: '2025-03-05T14:30:00Z'
                  bids:
                    - - '227.40'
                      - '100.0'
                    - - '227.30'
                      - '250.0'
                  asks:
                    - - '227.60'
                      - '80.0'
                    - - '227.70'
                      - '150.0'
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
                      - invalid_symbol
              example:
                success: false
                error: Description of the error
                error_code: invalid_market
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security:
        - {}
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
    ApiBookSnapshot:
      type: object
      required:
        - market
        - time
        - bids
        - asks
      properties:
        market:
          type: string
          description: Trading market
          example: AAPL-USD.P
        time:
          type: string
          format: date-time
          description: Snapshot timestamp
          example: '2022-06-16T12:35:11.123456Z'
        bids:
          type: array
          description: Best bid price levels, sorted descending by price
          items:
            $ref: '#/components/schemas/BookLevel'
        asks:
          type: array
          description: Best ask price levels, sorted ascending by price
          items:
            $ref: '#/components/schemas/BookLevel'
    BookLevel:
      type: array
      description: Price level represented as [price, quantity]
      items:
        type: string
      minItems: 2
      maxItems: 2
      example:
        - '1.55'
        - '100.0'
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
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY-ID

````