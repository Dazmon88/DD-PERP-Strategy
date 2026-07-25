> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get SIWE Login Challenge

> Get a Sign-In with Ethereum (ERC-4361) challenge for login.



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/auth/erc-4361/login/get_challenge
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
  /v1/auth/erc-4361/login/get_challenge:
    post:
      tags:
        - Auth
      summary: Get SIWE Login Challenge
      description: Get a Sign-In with Ethereum (ERC-4361) challenge for login.
      operationId: getSIWEChallenge
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginGetChallengeRequest'
      responses:
        '200':
          description: Challenge message for signing
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
                  id: chg_9f8e7d6c5b4a3210
                  message: >-
                    api.ondoperps.xyz wants you to sign in with your Ethereum
                    account:

                    0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18


                    Sign in to Ondo Perps


                    URI: https://api.ondoperps.xyz

                    Version: 1

                    Chain ID: 1

                    Nonce: abc123

                    Issued At: 2025-03-05T14:30:00Z
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
                      - challenge_not_found
              example:
                success: false
                error: Description of the error
                error_code: challenge_not_found
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
components:
  schemas:
    LoginGetChallengeRequest:
      type: object
      required:
        - walletAddress
        - chainId
      properties:
        walletAddress:
          type: string
          description: The wallet address requesting to sign in
          example: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
        chainId:
          type: string
          description: EVM chain ID (1=Ethereum, 43114=Avalanche)
          example: '1'
          enum:
            - '1'
            - '43114'
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

````