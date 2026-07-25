> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get SIWE Address Book Challenge

> Get a Sign-In with Ethereum challenge for adding a withdrawal address.



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/auth/erc-4361/address_book/get_challenge
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
  /v1/auth/erc-4361/address_book/get_challenge:
    post:
      tags:
        - Auth
      summary: Get SIWE Address Book Challenge
      description: Get a Sign-In with Ethereum challenge for adding a withdrawal address.
      operationId: getSIWEAddressBookChallenge
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AddressBookGetChallengeRequest'
      responses:
        '200':
          description: Challenge for signing
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/AuthChallengeResult'
              example:
                success: true
                result:
                  id: chg_ab12cd34ef56
                  message: >-
                    Sign this message to add withdrawal address
                    0x054A94b753CBf65D1Bc484F6D41897b48251fbfF to your address
                    book.
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
    AddressBookGetChallengeRequest:
      type: object
      required:
        - walletAddress
        - chainId
        - withdrawalAddress
      properties:
        walletAddress:
          type: string
          description: The wallet address requesting to add a withdrawal address
          example: '0x505D602729B932959935C1efd350Cea74527d3D1'
        chainId:
          type: string
          description: EVM chain ID (1=Ethereum, 43114=Avalanche)
          example: '43114'
          enum:
            - '1'
            - '43114'
        withdrawalAddress:
          type: string
          description: The address to add to the withdrawal address book
          example: '0x054A94b753CBf65D1Bc484F6D41897b48251fbfF'
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
    AuthChallengeResult:
      type: object
      required:
        - id
        - message
      properties:
        id:
          type: string
          description: Challenge ID
          example: abc123
        message:
          type: string
          description: Message to be signed by the wallet
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