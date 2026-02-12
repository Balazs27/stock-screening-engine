/*{{ config(
    materialized='table',
    tags=['gold', 'fundamentals', 'scoring']
) }} */

WITH fundamentals AS (

    SELECT * FROM {{ ref('int_sp500_fundamentals') }}
    
),

scoring AS (
    SELECT
        ticker,
        date,
        fiscal_year,
        
        -- Raw metrics for reference
        gross_margin,
        operating_margin,
        net_margin,
        return_on_equity,
        return_on_assets,
        current_ratio,
        debt_to_equity,
        fcf_margin,
        fcf_to_net_income,
        revenue_growth_yoy,
        eps_growth_yoy,
        fcf_growth_yoy,
        
        -- Component 1: Profitability Quality (25 pts)
        -- High margins + strong returns = efficient business
        CASE
            WHEN gross_margin > 0.5 AND operating_margin > 0.25 AND net_margin > 0.20 THEN 15
            WHEN gross_margin > 0.4 AND operating_margin > 0.20 AND net_margin > 0.15 THEN 12
            WHEN gross_margin > 0.3 AND operating_margin > 0.15 AND net_margin > 0.10 THEN 9
            WHEN gross_margin > 0.2 AND operating_margin > 0.10 THEN 6
            WHEN gross_margin > 0 AND net_margin > 0 THEN 3
            ELSE 0
        END +
        CASE
            WHEN return_on_equity > 0.20 THEN 10  -- ROE > 20% is excellent
            WHEN return_on_equity > 0.15 THEN 7
            WHEN return_on_equity > 0.10 THEN 5
            WHEN return_on_equity > 0 THEN 2
            ELSE 0
        END as profitability_score,
        
        -- Component 2: Growth Momentum (30 pts) - SLIGHTLY OVERWEIGHTED
        -- Reward strong YoY growth across revenue, EPS, FCF
        CASE
            WHEN revenue_growth_yoy > 0.20 THEN 10  -- 20%+ revenue growth
            WHEN revenue_growth_yoy > 0.15 THEN 8
            WHEN revenue_growth_yoy > 0.10 THEN 6
            WHEN revenue_growth_yoy > 0.05 THEN 4
            WHEN revenue_growth_yoy > 0 THEN 2
            ELSE 0
        END +
        CASE
            WHEN eps_growth_yoy > 0.25 THEN 10  -- 25%+ EPS growth
            WHEN eps_growth_yoy > 0.15 THEN 8
            WHEN eps_growth_yoy > 0.10 THEN 6
            WHEN eps_growth_yoy > 0.05 THEN 4
            WHEN eps_growth_yoy > 0 THEN 2
            ELSE 0
        END +
        CASE
            WHEN fcf_growth_yoy > 0.20 THEN 10  -- 20%+ FCF growth
            WHEN fcf_growth_yoy > 0.15 THEN 8
            WHEN fcf_growth_yoy > 0.10 THEN 6
            WHEN fcf_growth_yoy > 0.05 THEN 4
            WHEN fcf_growth_yoy > 0 THEN 2
            ELSE 0
        END as growth_score,
        
        -- Component 3: Financial Health (25 pts)
        -- Strong balance sheet = resilience
        CASE
            WHEN current_ratio > 2.0 THEN 10  -- Very liquid
            WHEN current_ratio > 1.5 THEN 8
            WHEN current_ratio > 1.0 THEN 6
            WHEN current_ratio > 0.75 THEN 4  -- Apple territory (cash machines can be <1)
            ELSE 2
        END +
        CASE
            WHEN debt_to_equity < 0.3 THEN 10  -- Very low debt
            WHEN debt_to_equity < 0.5 THEN 8
            WHEN debt_to_equity < 1.0 THEN 6
            WHEN debt_to_equity < 2.0 THEN 4
            ELSE 2
        END +
        CASE
            WHEN fcf_margin > 0.25 THEN 5  -- 25%+ FCF margin
            WHEN fcf_margin > 0.20 THEN 4
            WHEN fcf_margin > 0.15 THEN 3
            WHEN fcf_margin > 0.10 THEN 2
            ELSE 1
        END as financial_health_score,
        
        -- Component 4: Cash Quality (20 pts)
        -- FCF > Net Income = real earnings quality
        CASE
            WHEN fcf_to_net_income > 1.2 THEN 15  -- FCF exceeds net income (very good)
            WHEN fcf_to_net_income > 1.0 THEN 12
            WHEN fcf_to_net_income > 0.8 THEN 9
            WHEN fcf_to_net_income > 0.5 THEN 6
            ELSE 3
        END +
        CASE
            WHEN fcf_margin > 0.20 THEN 5
            WHEN fcf_margin > 0.15 THEN 4
            WHEN fcf_margin > 0.10 THEN 3
            ELSE 2
        END as cash_quality_score

    FROM fundamentals
)

SELECT
    ticker,
    date,
    fiscal_year,
    
    -- Component scores
    profitability_score,
    growth_score,
    financial_health_score,
    cash_quality_score,
    
    -- Total fundamentals score (0-100)
    (profitability_score + growth_score + financial_health_score + cash_quality_score) as fundamentals_score,
    
    -- Include raw metrics for reference (I THINK WE CAN SKIP IT)
    gross_margin,
    operating_margin,
    net_margin,
    return_on_equity,
    current_ratio,
    debt_to_equity,
    fcf_margin,
    revenue_growth_yoy,
    eps_growth_yoy,
    fcf_growth_yoy

FROM scoring