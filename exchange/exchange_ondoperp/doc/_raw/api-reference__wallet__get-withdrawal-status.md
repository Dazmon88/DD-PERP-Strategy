> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Withdrawal Status

> Get status of one or more withdrawals. For the withdrawal process and timing, see [Withdrawals](/withdrawals).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/get_withdrawal_status
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
  /v1/get_withdrawal_status:
    post:
      tags:
        - Wallet
      summary: Get Withdrawal Status
      description: >-
        Get status of one or more withdrawals. For the withdrawal process and
        timing, see [Withdrawals](/withdrawals).
      operationId: getWithdrawalStatus
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/GetWithdrawalStatusRequest'
      responses:
        '200':
          description: Withdrawal status result
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/WithdrawalStatusResult'
              example:
                success: true
                result:
                  original_request:
                    account_id: '10458932786832481'
                    customer_withdrawal_id: my-withdrawal-001
                    symbol: USDC
                    amount: '100.00'
                    address: '0x054A94b753CBf65D1Bc484F6D41897b48251fbfF'
                    network: ethereum
                  withdrawal_id: w_9f8e7d6c5b4a3210
                  txid: 0xabc123...
                  confirmation_number: 12
                  withdrawal_status: complete
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
    GetWithdrawalStatusRequest:
      type: object
      description: Provide exactly one of withdrawal_id or customer_withdrawal_id
      properties:
        withdrawal_id:
          type: string
          description: The platform-assigned withdrawal ID
          example: w_9f8e7d6c5b4a3210
        customer_withdrawal_id:
          type: string
          description: The user-specified withdrawal ID
          example: my-withdrawal-001
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
    WithdrawalStatusResult:
      type: object
      required:
        - original_request
        - withdrawal_id
        - txid
        - confirmation_number
        - withdrawal_status
      properties:
        original_request:
          type: object
          description: The original withdrawal request
          properties:
            account_id:
              type: string
            customer_withdrawal_id:
              type: string
            symbol:
              type: string
            amount:
              type: string
            address:
              type: string
            network:
              type: string
              enum:
                - avalanche
                - ethereum
                - solana
            from:
              $ref: '#/components/schemas/AccountWalletKey'
        withdrawal_id:
          type: string
          description: Internal withdrawal ID
        txid:
          type: string
          description: On-chain transaction ID
        confirmation_number:
          type: integer
          description: Number of confirmations
        withdrawal_status:
          type: string
          description: Current withdrawal status
          enum:
            - complete
            - failure
            - pending
            - cancelled
            - unknown
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