> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Export Withdrawals CSV

> Exports the account's withdrawal history as a downloadable CSV for the given time range. Columns: `time` (RFC 3339, UTC), `coin`, `size`, `address`, `status`. For the withdrawal process and timing, see [Withdrawals](/withdrawals).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/wallet/withdrawals/csv
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
  /v1/wallet/withdrawals/csv:
    post:
      tags:
        - Wallet
      summary: Export Withdrawals CSV
      description: >-
        Exports the account's withdrawal history as a downloadable CSV for the
        given time range. Columns: `time` (RFC 3339, UTC), `coin`, `size`,
        `address`, `status`. For the withdrawal process and timing, see
        [Withdrawals](/withdrawals).
      operationId: exportWithdrawalsCsv
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UnixTimeRangeRequest'
      responses:
        '200':
          description: CSV file of withdrawals for the requested time range.
          content:
            text/csv:
              schema:
                type: string
                description: CSV text with a header row followed by one row per withdrawal.
              example: >
                time,coin,size,address,status

                2025-02-20T15:45:00Z,USDC,500.00,0x054A94b753CBf65D1Bc484F6D41897b48251fbfF,complete

                2025-02-18T11:20:00Z,USDC,750.00,0x054A94b753CBf65D1Bc484F6D41897b48251fbfF,pending
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