> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Complete SIWE Login

> Complete Sign-In with Ethereum by submitting the signed challenge. Returns JWT.



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/auth/erc-4361/login/complete_challenge
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
  /v1/auth/erc-4361/login/complete_challenge:
    post:
      tags:
        - Auth
      summary: Complete SIWE Login
      description: >-
        Complete Sign-In with Ethereum by submitting the signed challenge.
        Returns JWT.
      operationId: completeSIWEChallenge
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginCompleteChallengeRequest'
      responses:
        '200':
          description: Auth token
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/AuthToken'
              example:
                success: true
                result:
                  identifier: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
                  authType: web3
                  accountId: '10458932786832481'
                  issuedAtSecs: 1709648400
                  expirationSecs: 1709734800
                  token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
                  newAccount: false
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
                      - account_cannot_be_verified
                      - challenge_not_found
                      - invite_code_already_used
                      - invite_code_invalid
              example:
                success: false
                error: Description of the error
                error_code: account_cannot_be_verified
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
components:
  schemas:
    LoginCompleteChallengeRequest:
      type: object
      required:
        - id
        - signature
      properties:
        id:
          type: string
          description: The ID of the login challenge
          example: ub6EabCuCiw9HvYyhsZhWzv8mntMgZ-vDGzZKvvCi_o=
        signature:
          type: string
          description: The signed challenge proving wallet ownership
          example: >-
            8650fc18ca35d1e3c358b566ff786783978dc16519c055ba2085a2345bed89f46719876e3e01cf3bbf94c50f6b5524c3df3d9881386f11910ddb3a15bfade5f21c
        source:
          type: string
          description: Optional source identifier
          example: web
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
    AuthToken:
      type: object
      required:
        - identifier
        - authType
        - accountId
        - issuedAtSecs
        - expirationSecs
        - token
        - newAccount
      properties:
        identifier:
          type: string
          description: Wallet address or email
        authType:
          type: string
          description: Authentication type
          enum:
            - web3
            - web2:email_pass
            - web2:google
            - unknown
        accountId:
          type: string
          description: Account ID
        issuedAtSecs:
          type: integer
          description: Token issue time (Unix seconds)
        expirationSecs:
          type: integer
          description: Token expiration time (Unix seconds)
        token:
          type: string
          description: JWT token
        newAccount:
          type: boolean
          description: True if a new account was created during this login
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