{{ config(
    materialized='table',
    tags=['gold', 'composite']
) }}

WITH technical_scores AS (
    SELECT 
        ticker,
        date,
        technical_score,
        trend_score,
        momentum_score,
        macd_score,
        price_action_score
    FROM {{ ref('mart_sp500_technical_scores') }}
),

fundamentals_scores AS (
    SELECT
        ticker,
        fiscal_year,
        date as fiscal_year_end_date,  -- e.g., 2025-09-27 for Apple FY 2025
        fundamentals_score,
        profitability_score,
        growth_score,
        financial_health_score,
        cash_quality_score
    FROM {{ ref('mart_sp500_fundamental_scores') }}
),

-- Join: Each daily technical score gets the fundamentals for that calendar year
composite AS (
    SELECT
        t.ticker,
        t.date as technical_date,
        t.technical_score,
        
        -- Find the most recent fundamentals available as of this technical date
        f.fundamentals_score,
        f.fiscal_year,
        f.fiscal_year_end_date,
        
        -- Component breakdowns
        t.trend_score,
        t.momentum_score,
        t.macd_score,
        t.price_action_score,
        f.profitability_score,
        f.growth_score,
        f.financial_health_score,
        f.cash_quality_score,
        
        -- Composite score (you decide the weighting)
        -- Option 1: Equal weight (50/50)
        (t.technical_score * 0.5) + (f.fundamentals_score * 0.5) as composite_score_equal,
        
        -- Option 2: Technical bias (60/40)
        (t.technical_score * 0.6) + (f.fundamentals_score * 0.4) as composite_score_technical_bias,
        
        -- Option 3: Fundamentals bias (40/60)
        (t.technical_score * 0.4) + (f.fundamentals_score * 0.6) as composite_score_fundamental_bias,

    FROM technical_scores t
    LEFT JOIN fundamentals_scores f
        ON t.ticker = f.ticker
        AND f.fiscal_year_end_date <= t.date  -- Only use fundamentals that existed on this date

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY t.ticker, t.date 
        ORDER BY f.fiscal_year_end_date DESC  -- Get the MOST RECENT fundamentals
    ) = 1
)

SELECT * FROM composite
ORDER BY ticker, technical_date