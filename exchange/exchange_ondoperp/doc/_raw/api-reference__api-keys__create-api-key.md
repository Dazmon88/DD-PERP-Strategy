> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Create API Key

> Create a new API key. The secret is returned only once.



## OpenAPI

````yaml /api-reference/rest-spec.json post /v1/api_keys
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
  /v1/api_keys:
    post:
      tags:
        - API Keys
      summary: Create API Key
      description: Create a new API key. The secret is returned only once.
      operationId: createApiKey
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ApiKeysCreateRequest'
      responses:
        '200':
          description: Created API key (includes secret)
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/ApiKeyCreateResult'
              example:
                success: true
                result:
                  keyId: ondoKeyId_abc123
                  name: Trading Bot
                  createdAt: '2025-01-01T00:00:00Z'
                  scopes:
                    - trade
                    - transfer
                  secretKey: ondoApiSecret_abc123def456ghi789...
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
                      - bad_query_param
              example:
                success: false
                error: Description of the error
                error_code: bad_query_param
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
    ApiKeysCreateRequest:
      type: object
      required:
        - name
        - scopes
      properties:
        name:
          type: string
          description: Human-readable name for the API key
          example: Trading Bot
        scopes:
          type: array
          items:
            $ref: '#/components/schemas/ApiKeyScope'
          description: Permission scopes for the API key
          example:
            - trade
            - transfer
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
    ApiKeyCreateResult:
      type: object
      required:
        - keyId
        - name
        - createdAt
        - scopes
        - secretKey
      properties:
        keyId:
          type: string
          description: API key ID
        name:
          type: string
          description: Key name
        createdAt:
          type: string
          format: date-time
          description: When the key was created
        scopes:
          type: array
          items:
            $ref: '#/components/schemas/ApiKeyScope'
          description: Permitted scopes
        secretKey:
          type: string
          description: API secret key. Only returned once at creation time.
    ApiKeyScope:
      type: string
      enum:
        - trade
        - transfer
      description: API key permission scope
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