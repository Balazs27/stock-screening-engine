with price_changes AS (

    select 

        ticker,
        date,
        close,
        LAG(close) over (partition by ticker order by date) AS previous_day_close,
        close - LAG(close) over (partition by ticker order by date) AS price_change

    from {{ ref('stg_sp500_stock_prices_backfill') }}
    
)

select * from price_changes
