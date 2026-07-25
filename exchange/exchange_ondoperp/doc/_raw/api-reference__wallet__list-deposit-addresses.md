> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# List Deposit Addresses

> Returns the list of deposit addresses for the account. For supported assets and deposit steps, see [Funding your account](/funding-your-account).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/wallet/deposit_address/list
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
  /v1/wallet/deposit_address/list:
    post:
      tags:
        - Wallet
      summary: List Deposit Addresses
      description: >-
        Returns the list of deposit addresses for the account. For supported
        assets and deposit steps, see [Funding your
        account](/funding-your-account).
      operationId: listDepositAddresses
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DepositAddressListRequest'
      responses:
        '200':
          description: List of deposit addresses
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
                          $ref: '#/components/schemas/DepositAddress'
              example:
                success: true
                result:
                  - coin: USDC
                    network: ethereum
                    address: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
                    depositDestination:
                      id: '10458932786832481'
                      wallet: margin
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
                      - too_few_items
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
    DepositAddressListRequest:
      type: object
      required:
        - coins
      properties:
        coins:
          type: array
          items:
            type: string
          description: List of token symbols to retrieve deposit addresses for
          example:
            - USDC
        network:
          type: string
          description: Filter by network; omit to list all networks
          example: ethereum
          enum:
            - avalanche
            - ethereum
            - solana
        depositDestination:
          $ref: '#/components/schemas/AccountWalletKey'
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
    DepositAddress:
      type: object
      required:
        - coin
        - network
        - address
        - depositDestination
      properties:
        coin:
          type: string
          description: Token symbol
          example: USDC
        network:
          type: string
          description: Blockchain network
          example: ethereum
          enum:
            - avalanche
            - ethereum
            - solana
        address:
          type: string
          description: Deposit address
        depositDestination:
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