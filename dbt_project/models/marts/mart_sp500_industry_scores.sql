{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'technical_date']
) }}

with companies as (

    select * from {{ ref('dim_sp500_companies_current') }}

),

scores as (

    select * from {{ ref('mart_sp500_composite_scores') }}
    {% if is_incremental() %}
    where technical_date >= (select max(technical_date) - interval '3 days' from {{ this }})
    {% endif %}

),

joined as (

    select

        s.ticker,
        c.company_name,
        c.sector,
        c.industry,
        s.composite_score_equal,
        s.composite_score_technical_bias,
        s.composite_score_fundamental_bias,
        s.technical_score,
        s.fundamentals_score,

        s.technical_date,
        s.fiscal_year,
        s.fiscal_year_start_date,
        s.fiscal_year_end_date,

    from scores s
    left join companies c
    on s.ticker = c.ticker

)

select * from joined