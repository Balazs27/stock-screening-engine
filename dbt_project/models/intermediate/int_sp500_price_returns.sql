{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}

with price_base as (

    select

        ticker,
        date,
        close

    -- Full scan required: FIRST_VALUE (cumulative return) and MAX (drawdown)
    -- need complete price history per ticker
    from {{ ref('stg_sp500_stock_prices') }}

),

returns_calc as (

    select

        ticker,
        date,
        close,

        -- Daily return
        (close / LAG(close) OVER (PARTITION BY ticker ORDER BY date) - 1) AS daily_return,

        -- Cumulative return since first available date
        (close / FIRST_VALUE(close) OVER (PARTITION BY ticker ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1) AS cumulative_return,

        -- Rolling returns
        (close / LAG(close, 30) OVER (PARTITION BY ticker ORDER BY date) - 1) AS rolling_30d_return,

        (close / LAG(close, 90) OVER (PARTITION BY ticker ORDER BY date) - 1) AS rolling_90d_return,
        -- 252 trading days for 1-year return
        (close / LAG(close, 252) OVER (PARTITION BY ticker ORDER BY date) - 1) AS rolling_1y_return,

        -- Running max price for drawdown
        MAX(close) OVER (PARTITION BY ticker ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_max_price

    from price_base

),

final as (

    select

        ticker,
        date,
        close,
        daily_return,
        cumulative_return,
        rolling_30d_return,
        rolling_90d_return,
        rolling_1y_return,

        -- Rolling volatility (30d stddev of daily return)
        -- Computed here because daily_return is an alias from the previous CTE
        STDDEV(daily_return) OVER (PARTITION BY ticker ORDER BY date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS rolling_30d_volatility,

        running_max_price,
        (close / running_max_price - 1) AS drawdown_pct

    from returns_calc

)

select * from final
{% if is_incremental() %}
where date >= (select max(date) - interval '3 days' from {{ this }})
{% endif %}