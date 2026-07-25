> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Funding Rate History

> Get the historical funding rates for a market. For how funding is calculated and applied, see [Funding rates](/funding-rates).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/funding_rate_history
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
  /v1/perps/funding_rate_history:
    get:
      tags:
        - Funding Rate
      summary: Get Funding Rate History
      description: >-
        Get the historical funding rates for a market. For how funding is
        calculated and applied, see [Funding rates](/funding-rates).
      operationId: getFundingRateHistory
      parameters:
        - name: market
          in: query
          description: Perps trading market
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
          description: Paginated list of historical funding rates, most recent first
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
                          $ref: '#/components/schemas/FundingRateValue'
                      pageInfo:
                        $ref: '#/components/schemas/PageInfo'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    time: '2025-03-05T12:00:00Z'
                    fundingRate: '0.0000125'
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
                      - invalid_market
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
    FundingRateValue:
      type: object
      required:
        - market
        - time
        - fundingRate
      properties:
        market:
          type: string
          description: Perps trading market
          example: AAPL-USD.P
        time:
          type: string
          format: date-time
          description: The time funding was paid
          example: '2022-06-16T12:35:10.123456Z'
        fundingRate:
          type: string
          description: The funding rate as a fraction
          example: '0.0000125'
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