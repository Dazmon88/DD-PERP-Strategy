> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Funding Fee Payments

> Get a paginated history of funding fee payments for the authenticated account. For how funding is calculated and applied, see [Funding rates](/funding-rates).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/funding_fees
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
  /v1/perps/funding_fees:
    get:
      tags:
        - Funding Rate
      summary: Get Funding Fee Payments
      description: >-
        Get a paginated history of funding fee payments for the authenticated
        account. For how funding is calculated and applied, see [Funding
        rates](/funding-rates).
      operationId: getFundingFees
      parameters:
        - name: market
          in: query
          description: Trading market to filter by
          required: false
          schema:
            type: string
            example: AAPL-USD.P
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
        - name: startTime
          in: query
          description: Start time filter (UTC milliseconds)
          required: false
          schema:
            type: integer
            example: 1684814400000
        - name: endTime
          in: query
          description: End time filter (UTC milliseconds)
          required: false
          schema:
            type: integer
            example: 1672549200000
      responses:
        '200':
          description: Paginated list of funding fee payments, most recent first
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
                          $ref: '#/components/schemas/FundingFeeTransfer'
                      pageInfo:
                        $ref: '#/components/schemas/PageInfo'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    time: '2025-03-05T12:00:00Z'
                    markPrice: '227.50'
                    positionSize: '10.00'
                    positionDirection: long
                    rate: '0.0000125'
                    payer: long
                    amount: '-0.02844'
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
    FundingFeeTransfer:
      type: object
      required:
        - market
        - time
        - markPrice
        - positionSize
        - positionDirection
        - rate
        - payer
        - amount
      properties:
        market:
          type: string
          description: Market that the fee was paid in
          example: AAPL-USD.P
        time:
          type: string
          format: date-time
          description: The time that the funding fee was paid
          example: '2022-06-16T12:35:10.123456Z'
        markPrice:
          type: string
          description: The mark price at the time the fee was paid
          example: '12.03'
        positionSize:
          type: string
          description: The base size of the position at the time the fee was paid
          example: '1.00'
        positionDirection:
          type: string
          description: The direction of the position at the time the fee was paid
          enum:
            - long
            - short
            - neutral
          example: long
        rate:
          type: string
          description: The funding rate that led to this fee
          example: '0.0000125'
        payer:
          type: string
          description: The side that paid the fee
          enum:
            - long
            - short
            - neutral
          example: long
        amount:
          type: string
          description: >
            The actual amount of USDC transferred. Positive indicates a fee you
            earned, negative a fee you paid.
          example: '-0.16402'
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