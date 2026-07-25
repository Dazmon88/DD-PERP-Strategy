> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Account

> Returns account information for the authenticated user.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/account
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
  /v1/account:
    get:
      tags:
        - Account
      summary: Get Account
      description: Returns account information for the authenticated user.
      operationId: getAccount
      responses:
        '200':
          description: Account info
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/AccountInfo'
              example:
                success: true
                result:
                  accountID: '10458932786832481'
                  identifier: '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18'
                  authType: web3
                  accountState: open
                  withdrawalFeeUSD: '1'
                  disabledFunctionality:
                    disableTransfers: false
                    disableWallet: false
                    disableBalance: false
                    disablePerps: false
                    disableAPIKeys: false
                    disableSubaccounts: true
                    disableNetworkLink: true
                    disableReferrals: true
                    disableAlphaStrategies: true
                    disableAlphaStrategiesCreation: true
                    disableWalletLogins: true
                    disableChat: true
                    disableMAC: true
                    disableBasisTradeAccounts: true
                  termsVersion: 2
                  termsUnixSecs: 1704067200
                  privacyVersion: 1
                  privacyUnixSecs: 1704067200
                  marketingConsent: accepted
                  subaccountsLimit: 256
                  cooldownPeriodSecs: 0
                  pointsState: 0
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
                      - account_not_found
              example:
                success: false
                error: Description of the error
                error_code: account_not_found
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
    AccountInfo:
      type: object
      required:
        - accountID
        - identifier
        - authType
        - accountState
        - withdrawalFeeUSD
        - termsVersion
        - termsUnixSecs
        - privacyVersion
        - privacyUnixSecs
        - marketingConsent
      properties:
        accountID:
          type: string
          description: Account ID
          example: '10458932786832481'
        identifier:
          type: string
          description: Account identifier (wallet address or email)
        authType:
          type: string
          description: Authentication type
          enum:
            - web3
            - web2:email_pass
            - web2:google
            - unknown
        accountState:
          type: string
          description: Account state
          enum:
            - open
            - disabled
            - offboarding
            - closed
        withdrawalFeeUSD:
          type: string
          description: Withdrawal fee in USD
        disabledFunctionality:
          $ref: '#/components/schemas/DisabledFunctionality'
        termsVersion:
          type: integer
          description: Terms of service version accepted
        termsUnixSecs:
          type: integer
          description: Unix timestamp when terms were accepted
        privacyVersion:
          type: integer
          description: Privacy policy version accepted
        privacyUnixSecs:
          type: integer
          description: Unix timestamp when privacy policy was accepted
        marketingConsent:
          type: string
          description: Marketing consent value
        subaccountsLimit:
          type: integer
          description: Maximum number of subaccounts this account is allowed to create
          example: 256
        cooldownPeriodSecs:
          type: integer
          description: >-
            Withdrawal-address cooldown duration in seconds. `0` means no
            cooldown is currently active.
          example: 0
        pointsState:
          type: integer
          description: >-
            User-facing state of the points product. The frontend uses this to
            decide whether to render the points link and what content to show.
          enum:
            - 0
            - 1
            - 2
          x-enum-descriptions:
            '0': disabled
            '1': coming soon
            '2': live
          example: 0
    DisabledFunctionality:
      type: object
      properties:
        disableTransfers:
          type: boolean
        disableWallet:
          type: boolean
        disableBalance:
          type: boolean
        disablePerps:
          type: boolean
        disableAPIKeys:
          type: boolean
        disableSubaccounts:
          type: boolean
          description: >-
            If true, subaccount creation and management is disabled for this
            account.
        disableNetworkLink:
          type: boolean
        disableReferrals:
          type: boolean
          description: If true, the referrals feature is disabled for this account.
        disableAlphaStrategies:
          type: boolean
          description: If true, the alpha strategies feature is disabled for this account.
        disableAlphaStrategiesCreation:
          type: boolean
          description: >-
            If true, creation of new alpha strategies is disabled for this
            account.
        disableWalletLogins:
          type: boolean
        disableChat:
          type: boolean
          description: If true, in-app chat is disabled for this account.
        disableMAC:
          type: boolean
          description: If true, multi-asset collateral (MAC) is disabled for this account.
        disableBasisTradeAccounts:
          type: boolean
          description: >-
            If true, basis-trade account creation and management is disabled for
            this account.
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