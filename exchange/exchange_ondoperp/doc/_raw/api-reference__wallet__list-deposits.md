> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# List Deposits

> Returns deposit history for the authenticated account. For supported assets and deposit steps, see [Funding your account](/funding-your-account).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/wallet/deposits
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
  /v1/wallet/deposits:
    get:
      tags:
        - Wallet
      summary: List Deposits
      description: >-
        Returns deposit history for the authenticated account. For supported
        assets and deposit steps, see [Funding your
        account](/funding-your-account).
      operationId: listDeposits
      responses:
        '200':
          description: List of deposits
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
                          $ref: '#/components/schemas/WalletDeposit'
              example:
                success: true
                result:
                  - coin: USDC
                    size: '1000.00'
                    status: confirmed
                    txid: 0xabc123...
                    fromAddress: '0x054A94b753CBf65D1Bc484F6D41897b48251fbfF'
                    time: '2025-01-15T10:30:00Z'
                    currentConfirmations: 64
                    requiredConfirmations: 64
                    chainId: '1'
                    usdValue: '1000.00'
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
    WalletDeposit:
      type: object
      required:
        - coin
        - size
        - status
        - txid
        - fromAddress
        - time
        - chainId
        - usdValue
      properties:
        coin:
          type: string
          description: Token symbol
          example: USDC
        size:
          type: string
          description: Deposit amount
          example: '100.00'
        status:
          type: string
          description: Deposit status
          enum:
            - pending
            - confirmed
          example: confirmed
        txid:
          type: string
          description: On-chain transaction ID
        fromAddress:
          type: string
          description: Sender address
        time:
          type: string
          format: date-time
          description: Deposit time
        currentConfirmations:
          type: integer
          description: Current number of confirmations
        requiredConfirmations:
          type: integer
          description: Required confirmations for finality
        accountId:
          type: string
          description: Account ID
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
        usdValue:
          type: string
          description: USD value of the deposit
        logIndex:
          type: string
          description: Log index in the transaction
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