> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Balance

> Get a summary of the balance for a margin account. For how positions and balances work, see [Positions and balances](/positions-balances).



## OpenAPI

````yaml /api-reference/rest-spec.json get /v1/perps/balance
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
  /v1/perps/balance:
    get:
      tags:
        - Margin Account
      summary: Get Balance
      description: >-
        Get a summary of the balance for a margin account. For how positions and
        balances work, see [Positions and balances](/positions-balances).
      operationId: getPerpsBalance
      responses:
        '200':
          description: Margin account balance summary
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/GenericResponse'
                  - type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/MarginAccountBalanceSummary'
              example:
                success: true
                result:
                  walletBalance: '5000.00'
                  realizedPnl: '250.00'
                  unrealizedPnl: '-50.00'
                  marginBalance: '4950.00'
                  usedMargin: '1125.00'
                  availableMargin: '3825.00'
                  withdrawableMargin: '3825.00'
                  maintenanceMarginRequirement: '112.50'
                  totalMaintenanceMargin: '200.00'
                  marginRatio: '0.04'
                  leverage: '0.46'
                  underLiquidation: false
                  totalFundingPayments: '-5.67'
                  totalTradingFees: '12.34'
                  totalPnL: '232.00'
                  netInvested: '4750.00'
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
    MarginAccountBalanceSummary:
      type: object
      required:
        - walletBalance
        - realizedPnl
        - unrealizedPnl
        - marginBalance
        - usedMargin
        - availableMargin
        - withdrawableMargin
        - maintenanceMarginRequirement
        - totalMaintenanceMargin
        - marginRatio
        - leverage
        - underLiquidation
        - totalFundingPayments
        - totalTradingFees
        - totalPnL
      properties:
        walletBalance:
          type: string
          description: >
            The amount in USDC resulting from transfers in/out, realized PnL,
            and fees. wallet_balance = deposits - withdrawals + realized_pnl +
            trading_fees + funding_rate_fees
          example: '2000'
        realizedPnl:
          type: string
          description: Total realized PNL in USDC
          example: '600'
        unrealizedPnl:
          type: string
          description: The current unrealized PNL in USDC at mark price for open positions
          example: '-500'
        marginBalance:
          type: string
          description: >
            Margin balance in USDC. margin_balance = wallet_balance +
            unrealized_pnl
          example: '1500'
        usedMargin:
          type: string
          description: >
            Amount of used margin in USDC for resting orders and positions.
            used_margin = sum_for_all_markets(max(position_ask +
            resting_orders_ask, position_bid + resting_orders_bid) +
            open_loss_total)
          example: '200'
        availableMargin:
          type: string
          description: >
            Amount of margin in USDC available for new positions.
            available_balance = margin_balance - used_margin. Will not be
            negative.
          example: '1300'
        withdrawableMargin:
          type: string
          description: >
            Amount in USDC available for withdrawal. withdrawable_amount =
            max(0, min(available_balance, wallet_balance))
          example: '100'
        maintenanceMarginRequirement:
          type: string
          description: Total maintenance margin requirement for all open positions
          example: '150'
        totalMaintenanceMargin:
          type: string
          description: >-
            Total maintenance margin requirement for all open positions and
            resting orders
          example: '200'
        marginRatio:
          type: string
          description: >
            Margin ratio (0–100%) indicating liquidation proximity. margin_ratio
            = maintenance_margin / margin_balance. Returns 9999 if margin
            balance is negative or zero.
          example: '0.13'
        leverage:
          type: string
          description: >-
            Effective leverage for the entire account (notional value of all
            positions / margin balance)
          example: '5.0'
        underLiquidation:
          type: boolean
          description: Whether the account is currently under liquidation
          example: false
        totalFundingPayments:
          type: string
          description: Sum of all funding payments applied to this account
          example: '123'
        totalTradingFees:
          type: string
          description: Sum of all trading fees paid. A negative value implies a net rebate.
          example: '123'
        totalPnL:
          type: string
          description: >-
            All-time PnL including realized/unrealized PnL, fees, and funding
            payments
          example: '477'
        netInvested:
          type: string
          description: Net amount invested
          example: '1000'
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