> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Sandbox Deposit

> Credits the account with funds in sandbox environment only.



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/sandbox_deposit
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
  /v1/sandbox_deposit:
    post:
      tags:
        - Sandbox
      summary: Sandbox Deposit
      description: Credits the account with funds in sandbox environment only.
      operationId: sandboxDeposit
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SandboxDepositRequest'
      responses:
        '200':
          description: Deposit result
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/SandboxDepositResult'
              example:
                success: true
                result:
                  deposit_address: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
                  txn_hash: 0xabc123def456...
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
                      - invalid_network
                      - invalid_symbol
              example:
                success: false
                error: Description of the error
                error_code: invalid_network
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
    SandboxDepositRequest:
      type: object
      required:
        - amount
        - symbol
        - deposit_destination
        - chain_id
      properties:
        amount:
          type: string
          description: Deposit amount as a decimal string
          example: '1000.00'
        symbol:
          type: string
          description: Token symbol
          example: USDC
        deposit_destination:
          $ref: '#/components/schemas/AccountWalletKey'
        chain_id:
          type: string
          description: Chain ID for the deposit
          example: eth-mainnet
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
    SandboxDepositResult:
      type: object
      properties:
        deposit_address:
          type: string
          description: Deposit address used
        txn_hash:
          type: string
          description: Transaction hash of the sandbox deposit
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