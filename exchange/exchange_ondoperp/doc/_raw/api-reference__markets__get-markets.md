> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Markets

> Returns available trading markets. For the list of supported markets, see [Markets](/markets).

If called with authentication, some fields are updated to reflect account-specific values.



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/markets
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
  /v1/markets:
    get:
      tags:
        - Markets
      summary: Get Markets
      description: >-
        Returns available trading markets. For the list of supported markets,
        see [Markets](/markets).


        If called with authentication, some fields are updated to reflect
        account-specific values.
      operationId: getMarkets
      responses:
        '200':
          description: Markets response
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/MarketsResult'
              example:
                success: true
                result:
                  perps:
                    tradingPairs:
                      - market: AAPL-USD.P
                        baseIncrement: '0.01'
                        quoteIncrement: '0.01'
                  tokenConfig:
                    - id: USDC
                      name: USD Coin
                      decimals: 2
                      tokenDecimals: 6
                      networks: {}
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security: []
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
    MarketsResult:
      type: object
      properties:
        perps:
          type: object
          description: Perpetual futures markets
          properties:
            tradingPairs:
              type: array
              items:
                $ref: '#/components/schemas/PerpsTradingPair'
              description: Available perps trading pairs and their configuration
        tokenConfig:
          type: array
          description: Token configuration for supported assets
          items:
            $ref: '#/components/schemas/TokenConfig'
    PerpsTradingPair:
      type: object
      description: Perpetual futures trading pair configuration
      properties:
        market:
          type: string
          description: Market identifier (e.g. AAPL-USD.P)
          example: AAPL-USD.P
        baseIncrement:
          type: string
          description: Minimum size increment in base currency
          example: '0.01'
        quoteIncrement:
          type: string
          description: Minimum price increment in quote currency
          example: '0.01'
    TokenConfig:
      type: object
      properties:
        id:
          type: string
          description: Token symbol identifier
          example: USDC
        name:
          type: string
          description: Token display name
          example: USD Coin
        decimals:
          type: integer
          description: Display decimals
        tokenDecimals:
          type: integer
          description: On-chain token decimals
        networks:
          type: object
          description: Supported networks and contract addresses
          additionalProperties:
            type: object
            properties:
              contractAddresses:
                type: object
                additionalProperties:
                  type: string
        ucid:
          type: integer
          description: Unified coin ID
        coinGeckoId:
          type: string
        coinGeckoCurrency:
          type: string
        bridgeInfoUrl:
          type: string
        description:
          type: string
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