> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# List Withdrawals

> Returns withdrawal history for the authenticated account. For the withdrawal process and timing, see [Withdrawals](/withdrawals).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/wallet/withdrawals
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
  /v1/wallet/withdrawals:
    get:
      tags:
        - Wallet
      summary: List Withdrawals
      description: >-
        Returns withdrawal history for the authenticated account. For the
        withdrawal process and timing, see [Withdrawals](/withdrawals).
      operationId: listWithdrawals
      responses:
        '200':
          description: List of withdrawals
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
                          $ref: '#/components/schemas/WalletWithdrawal'
              example:
                success: true
                result:
                  - coin: USDC
                    size: '500.00'
                    status: complete
                    address: '0x054A94b753CBf65D1Bc484F6D41897b48251fbfF'
                    withdrawal_id: w_9f8e7d6c5b4a3210
                    txid: 0xdef456...
                    customer_withdrawal_id: my-withdrawal-001
                    time: '2025-02-20T15:45:00Z'
                    usdValue: '500.00'
                    usdFee: '0.00'
                    chainId: '1'
                    from:
                      id: '10458932786832481'
                      wallet: margin
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
    WalletWithdrawal:
      type: object
      required:
        - coin
        - size
        - status
        - address
        - withdrawal_id
        - txid
        - customer_withdrawal_id
        - time
        - chainId
      properties:
        coin:
          type: string
          description: Token symbol
          example: USDC
        size:
          type: string
          description: Withdrawal amount
          example: '100.00'
        status:
          type: string
          description: Withdrawal status
          enum:
            - complete
            - failure
            - pending
            - cancelled
            - unknown
          example: complete
        address:
          type: string
          description: Destination address
        withdrawal_id:
          type: string
          description: Internal withdrawal ID
        txid:
          type: string
          description: On-chain transaction ID
        customer_withdrawal_id:
          type: string
          description: Customer-provided withdrawal ID
        time:
          type: string
          format: date-time
          description: Withdrawal time
        accountId:
          type: string
          description: Account ID
        usdValue:
          type: string
          description: USD value of the withdrawal
        usdFee:
          type: string
          description: USD fee for the withdrawal
        chainId:
          type: string
          description: Chain ID
          enum:
            - avax-c-chain
            - avax-fuji-c-chain
            - eth-mainnet
            - eth-sepolia
            - btc-mainnet
            - btc-testnet
            - sol-mainnet
            - sol-testnet
            - bsc-mainnet
            - bsc-testnet
          example: eth-mainnet
        from:
          $ref: '#/components/schemas/AccountWalletKey'
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