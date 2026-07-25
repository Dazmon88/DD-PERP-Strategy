> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Funding Rates

> Get an estimate of the current-interval funding rate in a given market, as well as when the next funding is and what premium index measurements make up the funding rate. For how funding is calculated and applied, see [Funding rates](/funding-rates).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/funding_rates
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
  /v1/perps/funding_rates:
    get:
      tags:
        - Funding Rate
      summary: Get Funding Rates
      description: >-
        Get an estimate of the current-interval funding rate in a given market,
        as well as when the next funding is and what premium index measurements
        make up the funding rate. For how funding is calculated and applied, see
        [Funding rates](/funding-rates).
      operationId: getFundingRates
      parameters:
        - name: market
          in: query
          description: Market to query
          required: true
          schema:
            type: string
            example: AAPL-USD.P
      responses:
        '200':
          description: Current funding rate estimate
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/FundingRate'
              example:
                success: true
                result:
                  market: AAPL-USD.P
                  rate: '0.0000125'
                  intervalEnds: '2025-03-05T16:00:00Z'
                  premiums:
                    - time: '2025-03-05T15:00:00Z'
                      premiumIndex: '0.000025'
                    - time: '2025-03-05T15:30:00Z'
                      premiumIndex: '0.000015'
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
    FundingRate:
      type: object
      required:
        - market
        - rate
        - intervalEnds
      properties:
        market:
          type: string
          description: The market the funding rate applies to
          example: AAPL-USD.P
        rate:
          type: string
          description: The current estimated funding rate
          example: '0.0000125'
        intervalEnds:
          type: string
          format: date-time
          description: >-
            The time the current funding interval ends and the funding rate will
            be paid
          example: '2022-06-16T12:35:10.123456Z'
        premiums:
          type: array
          description: Premium index measurements that make up the funding rate
          items:
            $ref: '#/components/schemas/PremiumIndexValue'
    PremiumIndexValue:
      type: object
      properties:
        time:
          type: string
          format: date-time
          description: Time of the premium index measurement
          example: '2022-06-16T12:00:00Z'
        premiumIndex:
          type: string
          description: The premium index value
          example: '0.000025'
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