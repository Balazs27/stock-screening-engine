{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'technical_date'],
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

    {% if is_incremental() %}
    WHERE date >= (SELECT MAX(technical_date) - INTERVAL '3 days' FROM {{ this }})
    {% endif %}

),

fundamentals_base AS (

    SELECT

        ticker,
        fiscal_year,
        date AS fiscal_year_end_date,
        fundamentals_score,
        profitability_score,
        growth_score,
        financial_health_score,
        cash_quality_score

    FROM {{ ref('mart_sp500_fundamental_scores') }}

),

fundamentals_with_periods AS (

    SELECT
        ticker,
        fiscal_year,
        fiscal_year_end_date,
        --DATEADD(day, 1, LAG(fiscal_year_end_date) OVER (PARTITION BY ticker ORDER BY fiscal_year)) AS fiscal_year_start_date,

        LAG(fiscal_year_end_date) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS fiscal_year_start_date,

        fundamentals_score,
        profitability_score,
        growth_score,
        financial_health_score,
        cash_quality_score

    FROM fundamentals_base
),

composite AS (

    SELECT

        t.ticker,
        t.date AS technical_date,
        t.technical_score,

        f.fiscal_year,
        f.fiscal_year_start_date,
        f.fiscal_year_end_date,
        f.fundamentals_score,

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
        (t.technical_score * 0.5) + (f.fundamentals_score * 0.5) AS composite_score_equal,

        -- Option 2: Technical bias (60/40)
        (t.technical_score * 0.6) + (f.fundamentals_score * 0.4) as composite_score_technical_bias,

        -- Option 3: Fundamentals bias (40/60)
        (t.technical_score * 0.4) + (f.fundamentals_score * 0.6) AS composite_score_fundamental_bias

    FROM technical_scores t
    LEFT JOIN fundamentals_with_periods f
    ON t.ticker = f.ticker
    AND t.date BETWEEN f.fiscal_year_start_date
    AND f.fiscal_year_end_date
    
)

SELECT *
FROM composite