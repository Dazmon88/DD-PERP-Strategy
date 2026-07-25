> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Provision Deposit Address

> Provision a new deposit address for a given symbol/chain. For supported assets and deposit steps, see [Funding your account](/funding-your-account).



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/provision_address
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
  /v1/provision_address:
    post:
      tags:
        - Wallet
      summary: Provision Deposit Address
      description: >-
        Provision a new deposit address for a given symbol/chain. For supported
        assets and deposit steps, see [Funding your
        account](/funding-your-account).
      operationId: provisionAddress
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProvisionAddressRequest'
      responses:
        '200':
          description: Provisioned address
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/ProvisionAddressResult'
              example:
                success: true
                result:
                  chain: ethereum
                  accountId: '10458932786832481'
                  symbol: USDC
                  address: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
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
    ProvisionAddressRequest:
      type: object
      required:
        - network
        - symbol
        - deposit_destination
      properties:
        network:
          type: string
          description: Blockchain network
          example: ethereum
          enum:
            - avalanche
            - ethereum
            - solana
        symbol:
          type: string
          description: Token symbol
          example: USDC
        deposit_destination:
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
    ProvisionAddressResult:
      type: object
      required:
        - chain
        - accountId
        - symbol
        - address
      properties:
        chain:
          type: string
          description: Blockchain network
          example: ethereum
        accountId:
          type: string
          description: Account ID
        symbol:
          type: string
          description: Token symbol
          example: USDC
        address:
          type: string
          description: Provisioned deposit address
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