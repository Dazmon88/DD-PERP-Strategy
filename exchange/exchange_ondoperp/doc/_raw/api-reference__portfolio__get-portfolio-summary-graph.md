> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Portfolio Summary Graph

> Returns time-series portfolio snapshots for the authenticated account. Optional query parameter `range` controls the bucket size: 7d (default), 24h, 30d, or all.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/portfolio/summary/graph
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
  /v1/portfolio/summary/graph:
    get:
      tags:
        - Portfolio
      summary: Get Portfolio Summary Graph
      description: >-
        Returns time-series portfolio snapshots for the authenticated account.
        Optional query parameter `range` controls the bucket size: 7d (default),
        24h, 30d, or all.
      operationId: getPortfolioSummaryGraph
      parameters:
        - name: range
          in: query
          description: 'Time range for bucketing: 7d (default), 24h, 30d, or all'
          required: false
          schema:
            type: string
            enum:
              - 7d
              - 24h
              - 30d
              - all
            default: 7d
      responses:
        '200':
          description: Array of portfolio graph points (time-series)
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
                          $ref: '#/components/schemas/PortfolioGraphPoint'
              example:
                success: true
                result:
                  - time: '2025-03-04T00:00:00Z'
                    marginBalance: '4800.00'
                    totalPnL: '180.00'
                    realizedPnl: '200.00'
                    netInvested: '4620.00'
                    fillVolume: '240000.00'
                    allTimeDeposits: '5000.00'
                    allTimeWithdrawals: '500.00'
                  - time: '2025-03-05T00:00:00Z'
                    marginBalance: '4950.00'
                    totalPnL: '232.00'
                    realizedPnl: '250.00'
                    netInvested: '4750.00'
                    fillVolume: '250000.00'
                    allTimeDeposits: '5000.00'
                    allTimeWithdrawals: '500.00'
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
    PortfolioGraphPoint:
      type: object
      description: Single time-series point for portfolio graph
      properties:
        time:
          type: string
          format: date-time
          description: Timestamp of the snapshot
        marginBalance:
          type: string
          description: Margin balance at this time
        totalPnL:
          type: string
          description: Total PnL at this time
        realizedPnl:
          type: string
          description: Realized PnL at this time
        netInvested:
          type: string
          description: Net invested at this time
        fillVolume:
          type: string
          description: Cumulative fill volume at this time
        allTimeDeposits:
          type: string
          description: All-time deposits at this time
        allTimeWithdrawals:
          type: string
          description: All-time withdrawals at this time
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