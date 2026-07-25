> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Portfolio Summary

> Returns current portfolio metrics for the authenticated account: margin balance, net invested, PnL, volume metrics, and Sharpe ratios (when enabled and sufficient data).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/portfolio/summary
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
  /v1/portfolio/summary:
    get:
      tags:
        - Portfolio
      summary: Get Portfolio Summary
      description: >-
        Returns current portfolio metrics for the authenticated account: margin
        balance, net invested, PnL, volume metrics, and Sharpe ratios (when
        enabled and sufficient data).
      operationId: getPortfolioSummary
      responses:
        '200':
          description: Portfolio summary with metrics and optional Sharpe ratio data
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/PortfolioSummaryRes'
              example:
                success: true
                result:
                  marginBalance: '4950.00'
                  netInvested: '4750.00'
                  totalPnL: '232.00'
                  realizedPnl: '250.00'
                  volume7d: '15000.00'
                  volume30d: '85000.00'
                  volumeAllTime: '250000.00'
                  sharpe30d:
                    sharpeRatio: '1.85'
                    daysOfData: 30
                    meanDailyROI: '0.0012'
                    stdDevROI: '0.0065'
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
                      - account_not_found
              example:
                success: false
                error: Description of the error
                error_code: account_not_found
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
    PortfolioSummaryRes:
      type: object
      description: Current portfolio metrics and optional Sharpe ratios
      properties:
        marginBalance:
          type: string
          description: Current margin account balance
        netInvested:
          type: string
          description: Net invested amount
        totalPnL:
          type: string
          description: Total unrealized + realized PnL
        realizedPnl:
          type: string
          description: Realized PnL
        volume7d:
          type: string
          description: Trading volume over last 7 days
        volume30d:
          type: string
          description: Trading volume over last 30 days
        volumeAllTime:
          type: string
          description: All-time trading volume
        sharpe30d:
          $ref: '#/components/schemas/SharpeRatioData'
        sharpeAllTime:
          $ref: '#/components/schemas/SharpeRatioData'
    SharpeRatioData:
      type: object
      description: Calculated Sharpe ratio and related metadata
      properties:
        sharpeRatio:
          type: string
          description: Annualized Sharpe ratio
        daysOfData:
          type: integer
          description: Number of days of data used in the calculation
        meanDailyROI:
          type: string
          description: Mean daily return
        stdDevROI:
          type: string
          description: Standard deviation of daily returns
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