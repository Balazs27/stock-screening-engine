{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}

with returns as (

    select
    
        ticker,
        date,
        close,
        daily_return,
        cumulative_return,
        rolling_30d_return,
        rolling_90d_return,
        rolling_1y_return,
        rolling_30d_volatility,
        running_max_price,
        drawdown_pct

    from {{ ref('int_sp500_price_returns') }}
    {% if is_incremental() %}
    where date >= (select max(date) - interval '7 days' from {{ this }})
    {% endif %}

),

dim as (

    select

        ticker,
        company_name,
        sector,
        industry

    from {{ ref('dim_sp500_companies_current') }}

),

final as (

    select

        r.ticker,
        r.date,
        r.close,
        r.daily_return,
        r.cumulative_return,
        r.rolling_30d_return,
        r.rolling_90d_return,
        r.rolling_1y_return,
        r.rolling_30d_volatility,
        r.running_max_price,
        r.drawdown_pct,

        d.company_name,
        d.sector,
        d.industry

    from returns r
    left join dim d
        on r.ticker = d.ticker

)

select * from final
