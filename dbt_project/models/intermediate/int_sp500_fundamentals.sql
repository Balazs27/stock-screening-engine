/*{{ config(
    materialized='table',
    tags=['silver', 'fundamentals']
) }}*/

WITH income_stmt AS (
    SELECT * FROM {{ ref('stg_fmp_income_statement') }}
),

balance_sheet AS (
    SELECT * FROM {{ ref('stg_fmp_balance_sheet') }}
),

cash_flow AS (
    SELECT * FROM {{ ref('stg_fmp_cash_flow') }}
),

joined_fundamentals AS (
    SELECT
        -- Identity & Metadata
        i.date,
        i.ticker,
        i.fiscal_year,
        i.period,
        
        -- Income Statement (Profitability)
        i.revenue,
        i.cost_of_revenue,
        i.gross_profit,
        i.operating_income,
        i.net_income,
        i.eps_diluted,
        i.ebitda,
        i.weighted_average_shares_out_diluted,
        
        -- Balance Sheet (Financial Health)
        b.total_assets,
        b.total_current_assets,
        b.cash_and_short_term_investments,
        b.net_receivables,
        b.total_liabilities,
        b.total_current_liabilities,
        b.total_stockholders_equity,
        b.total_debt,
        b.net_debt,
        
        -- Cash Flow (Cash Generation)
        c.operating_cash_flow,
        c.free_cash_flow,
        c.capital_expenditure

    FROM income_stmt i
    INNER JOIN balance_sheet b
        ON i.ticker = b.ticker 
        AND i.date = b.date
        AND i.fiscal_year = b.fiscal_year
    INNER JOIN cash_flow c
        ON i.ticker = c.ticker 
        AND i.date = c.date
        AND i.fiscal_year = c.fiscal_year
    WHERE i.period = 'FY'  -- Annual data only
),

derived_metrics AS (
    SELECT
        *,
        
        -- Profitability Ratios
        CASE 
            WHEN revenue > 0 THEN gross_profit / revenue 
            ELSE NULL 
        END AS gross_margin,
        
        CASE 
            WHEN revenue > 0 THEN operating_income / revenue 
            ELSE NULL 
        END AS operating_margin,
        
        CASE 
            WHEN revenue > 0 THEN net_income / revenue 
            ELSE NULL 
        END AS net_margin,
        
        CASE 
            WHEN total_stockholders_equity > 0 THEN net_income / total_stockholders_equity 
            ELSE NULL 
        END AS return_on_equity,
        
        CASE 
            WHEN total_assets > 0 THEN net_income / total_assets 
            ELSE NULL 
        END AS return_on_assets,
        
        -- Liquidity Ratios
        CASE 
            WHEN total_current_liabilities > 0 THEN total_current_assets / total_current_liabilities 
            ELSE NULL 
        END AS current_ratio,
        
        CASE 
            WHEN total_current_liabilities > 0 
            THEN (cash_and_short_term_investments + net_receivables) / total_current_liabilities 
            ELSE NULL 
        END AS quick_ratio,
        
        -- Leverage Ratios
        CASE 
            WHEN total_stockholders_equity > 0 THEN total_debt / total_stockholders_equity 
            ELSE NULL 
        END AS debt_to_equity,
        
        CASE 
            WHEN total_assets > 0 THEN total_debt / total_assets 
            ELSE NULL 
        END AS debt_to_assets,
        
        -- Cash Flow Metrics
        CASE 
            WHEN revenue > 0 THEN free_cash_flow / revenue 
            ELSE NULL 
        END AS fcf_margin,
        
        CASE 
            WHEN net_income > 0 THEN free_cash_flow / net_income 
            ELSE NULL 
        END AS fcf_to_net_income,
        
        -- Per-Share Metrics
        CASE 
            WHEN weighted_average_shares_out_diluted > 0 THEN revenue / weighted_average_shares_out_diluted 
            ELSE NULL 
        END AS revenue_per_share,
        
        CASE 
            WHEN weighted_average_shares_out_diluted > 0 THEN free_cash_flow / weighted_average_shares_out_diluted 
            ELSE NULL 
        END AS fcf_per_share,
        
        CASE 
            WHEN weighted_average_shares_out_diluted > 0 THEN total_stockholders_equity / weighted_average_shares_out_diluted 
            ELSE NULL 
        END AS book_value_per_share

    FROM joined_fundamentals
),

yoy_growth AS (
    SELECT
        *,
        
        -- Year-over-Year Growth Metrics
        CASE 
            WHEN LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY date) > 0 
            THEN (revenue - LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY date)) 
                 / LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY date)
            ELSE NULL 
        END AS revenue_growth_yoy,
        
        CASE 
            WHEN LAG(net_income, 1) OVER (PARTITION BY ticker ORDER BY date) > 0 
            THEN (net_income - LAG(net_income, 1) OVER (PARTITION BY ticker ORDER BY date)) 
                 / LAG(net_income, 1) OVER (PARTITION BY ticker ORDER BY date)
            ELSE NULL 
        END AS net_income_growth_yoy,
        
        CASE 
            WHEN LAG(eps_diluted, 1) OVER (PARTITION BY ticker ORDER BY date) > 0 
            THEN (eps_diluted - LAG(eps_diluted, 1) OVER (PARTITION BY ticker ORDER BY date)) 
                 / LAG(eps_diluted, 1) OVER (PARTITION BY ticker ORDER BY date)
            ELSE NULL 
        END AS eps_growth_yoy,
        
        CASE 
            WHEN LAG(free_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date) > 0 
            THEN (free_cash_flow - LAG(free_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date)) 
                 / LAG(free_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date)
            ELSE NULL 
        END AS fcf_growth_yoy,
        
        CASE 
            WHEN LAG(operating_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date) > 0 
            THEN (operating_cash_flow - LAG(operating_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date)) 
                 / LAG(operating_cash_flow, 1) OVER (PARTITION BY ticker ORDER BY date)
            ELSE NULL 
        END AS operating_cash_flow_growth_yoy

    FROM derived_metrics
)

SELECT * FROM yoy_growth