> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Contracts

> Gets a list of perpetual futures contracts and their current market data. For the list of supported markets, see [Markets](/markets).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/contracts
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
  /v1/perps/contracts:
    get:
      tags:
        - Market Data
      summary: Get Contracts
      description: >-
        Gets a list of perpetual futures contracts and their current market
        data. For the list of supported markets, see [Markets](/markets).
      operationId: getContracts
      parameters:
        - name: sparkline
          in: query
          description: If true, include sparkline price data in the response
          required: false
          schema:
            type: boolean
            example: false
      responses:
        '200':
          description: List of perpetual futures contracts
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
                          $ref: '#/components/schemas/Contract'
              example:
                success: true
                result:
                  - market: AAPL-USD.P
                    productType: perpetual
                    contractType: linear
                    baseCurrency: AAPL
                    quoteCurrency: USDC
                    disabled: false
                    lastPrice: '227.50'
                    baseVolume: '12500.00'
                    quoteVolume: '2843750.00'
                    usdVolume: '2843750.00'
                    bid: '227.40'
                    ask: '227.60'
                    high: '230.00'
                    low: '225.00'
                    openInterest: '2394.23'
                    openInterestUsd: '544683.50'
                    indexPrice: '227.55'
                    indexCurrency: USD
                    fundingRate: '0.0000125'
                    nextFundingRate: '0.0000130'
                    nextFundingRateTimestamp: '2025-03-05T16:00:00Z'
                    makerFee: '0.0002'
                    takerFee: '0.0005'
                    priceChangePercent: '1.12'
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
        '429':
          $ref: '#/components/responses/TooManyRequests'
        '500':
          $ref: '#/components/responses/InternalServerError'
      security:
        - {}
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
    Contract:
      type: object
      required:
        - market
        - productType
        - contractType
        - baseCurrency
        - quoteCurrency
        - disabled
      properties:
        market:
          type: string
          description: Perps market identifier
          example: AAPL-USD.P
        displayName:
          type: string
          description: Human-readable display name for the contract
          example: Apple Inc.
        productType:
          type: string
          description: Type of product
          example: perpetual
        contractType:
          type: string
          description: Type of contract
          example: linear
        baseCurrency:
          type: string
          description: The base currency of the contract
          example: AAPL
        quoteCurrency:
          type: string
          description: The quote currency of the contract
          example: USDC
        disabled:
          type: boolean
          description: If true, the market is currently unavailable for trading
          example: false
        lastPrice:
          type: string
          description: Price of the last trade
          example: '20000.54'
        baseVolume:
          type: string
          description: 24-hour trading volume in base currency
          example: '1089.12'
        quoteVolume:
          type: string
          description: 24-hour trading volume in quote currency
          example: '120400.65'
        usdVolume:
          type: string
          description: 24-hour trading volume in USD
          example: '120400.65'
        bid:
          type: string
          description: Current best bid price
          example: '1500.22'
        ask:
          type: string
          description: Current best ask price
          example: '1600.20'
        high:
          type: string
          description: Highest traded price in the last 24 hours
          example: '1600.20'
        low:
          type: string
          description: Lowest traded price in the last 24 hours
          example: '1400.20'
        openInterest:
          type: string
          description: Open interest in base currency
          example: '2394.2301'
        openInterestUsd:
          type: string
          description: Open interest in USD
          example: '24311.72'
        indexPrice:
          type: string
          description: Current price of the underlying market
          example: '1600.20'
        indexCurrency:
          type: string
          description: Currency of the underlying market
          example: USD
        fundingRate:
          type: string
          description: Funding rate at the last completed funding interval
          example: '0.00152'
        nextFundingRate:
          type: string
          description: Estimated funding rate at the end of the current funding interval
          example: '0.00152'
        nextFundingRateTimestamp:
          type: string
          format: date-time
          description: Timestamp when the next funding payments will occur
          example: '2022-06-16T12:35:10.123456Z'
        makerFee:
          type: string
          description: Fee on a filled resting (maker) order
          example: '0.0002'
        takerFee:
          type: string
          description: Fee on a filled aggressive (taker) order
          example: '0.0005'
        priceChangePercent:
          type: string
          description: Price change as a percentage in the last 24 hours
          example: '-5'
        isClosed:
          type: boolean
          description: >-
            If true, the underlying market is currently closed (e.g. outside
            trading hours for equities)
          example: false
        sparkline:
          $ref: '#/components/schemas/Sparkline'
        tags:
          type: array
          description: Optional tags describing the contract (e.g. category labels)
          items:
            type: string
          example:
            - equity
            - tech
    Sparkline:
      type: object
      properties:
        price:
          type: array
          description: Array of price values for the sparkline
          items:
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
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY-ID

````