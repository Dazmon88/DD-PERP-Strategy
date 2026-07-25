> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Export Deposits CSV

> Exports the account's deposit history as a downloadable CSV for the given time range. Columns: `id`, `time` (RFC 3339, UTC), `coin`, `size`, `status`. For supported assets and deposit steps, see [Funding your account](/funding-your-account).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/wallet/deposits/csv
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
  /v1/wallet/deposits/csv:
    post:
      tags:
        - Wallet
      summary: Export Deposits CSV
      description: >-
        Exports the account's deposit history as a downloadable CSV for the
        given time range. Columns: `id`, `time` (RFC 3339, UTC), `coin`, `size`,
        `status`. For supported assets and deposit steps, see [Funding your
        account](/funding-your-account).
      operationId: exportDepositsCsv
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UnixTimeRangeRequest'
      responses:
        '200':
          description: CSV file of deposits for the requested time range.
          content:
            text/csv:
              schema:
                type: string
                description: CSV text with a header row followed by one row per deposit.
              example: |
                id,time,coin,size,status
                0xabc123...,2025-01-15T10:30:00Z,USDC,1000.00,confirmed
                0x9f8e7d...,2025-01-10T08:05:00Z,USDC,250.00,confirmed
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
    UnixTimeRangeRequest:
      type: object
      properties:
        start_time:
          type: integer
          format: int64
          description: Start time as Unix timestamp in seconds
          example: 1666203390
        end_time:
          type: integer
          format: int64
          description: End time as Unix timestamp in seconds
          example: 1709734800
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