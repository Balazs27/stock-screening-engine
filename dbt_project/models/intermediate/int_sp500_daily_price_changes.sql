{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}

with price_changes AS (

    select

        ticker,
        date,
        close,
        LAG(close) over (partition by ticker order by date) AS previous_day_close,
        close - LAG(close) over (partition by ticker order by date) AS price_change

    from {{ ref('stg_sp500_stock_prices') }}
    {% if is_incremental() %}
    where date >= (select max(date) - interval '4 days' from {{ this }})
    {% endif %}

)

select * from price_changes
{% if is_incremental() %}
where date >= (select max(date) - interval '3 days' from {{ this }})
{% endif %}
