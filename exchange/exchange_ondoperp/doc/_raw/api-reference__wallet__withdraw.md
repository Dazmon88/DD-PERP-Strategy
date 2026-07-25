> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Withdraw

> Submit a withdrawal request. Rate limited per account. For the withdrawal process and timing, see [Withdrawals](/withdrawals).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/withdraw
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
  /v1/withdraw:
    post:
      tags:
        - Wallet
      summary: Withdraw
      description: >-
        Submit a withdrawal request. Rate limited per account. For the
        withdrawal process and timing, see [Withdrawals](/withdrawals).
      operationId: withdraw
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - customer_withdrawal_id
                - symbol
                - network
                - amount
                - address
              properties:
                customer_withdrawal_id:
                  type: string
                  description: Unique ID for this withdrawal
                symbol:
                  type: string
                  description: Coin to withdraw (e.g. USDC, SOL)
                network:
                  type: string
                  description: Target network (e.g. ethereum, solana)
                  enum:
                    - avalanche
                    - ethereum
                    - solana
                amount:
                  type: string
                  description: Amount to withdraw
                address:
                  type: string
                  description: Withdrawal destination address
                from:
                  $ref: '#/components/schemas/AccountWalletKey'
      responses:
        '200':
          description: Withdrawal result
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/WithdrawalResult'
              example:
                success: true
                result:
                  withdrawal_status: pending
                  withdrawal_id: w_9f8e7d6c5b4a3210
                  customer_withdrawal_id: my-withdrawal-001
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
                      - bad_withdrawal_address
                      - insufficient_funds
                      - internal_withdrawal_address
                      - invalid_network
                      - invalid_symbol
                      - invalid_withdrawal_network
                      - service_unavailable
                      - transfer_amount_precision_overflow
                      - withdrawal_address_not_found
                      - withdrawal_amount_too_small
                      - withdrawal_duplicate_customer_withdrawal_id
                      - withdrawal_error_insufficient_balance
                      - withdrawal_failed
                      - withdrawal_invalid_amount
                      - withdrawal_limit_exceeded
                      - withdrawal_missing_customer_withdrawal_id
                      - withdrawal_system_error
                      - withdrawal_try_later
              example:
                success: false
                error: Description of the error
                error_code: bad_withdrawal_address
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
    AccountWalletKey:
      type: object
      required:
        - id
        - wallet
      properties:
        id:
          type: string
          description: The account ID
          example: '10458932786832481'
        wallet:
          type: string
          description: The wallet type
          enum:
            - main
            - margin
          example: margin
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
    WithdrawalResult:
      type: object
      required:
        - withdrawal_status
        - withdrawal_id
        - customer_withdrawal_id
      properties:
        withdrawal_status:
          type: string
          description: Status of the withdrawal
          example: pending
          enum:
            - complete
            - failure
            - pending
            - cancelled
            - unknown
        withdrawal_id:
          type: string
          description: Internal withdrawal ID
        customer_withdrawal_id:
          type: string
          description: Customer-provided withdrawal ID
        hash:
          type: string
          description: On-chain transaction hash (when available)
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