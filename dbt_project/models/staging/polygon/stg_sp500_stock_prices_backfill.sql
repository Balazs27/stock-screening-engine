with staging as (

    select

        ticker,
        open,
        high,
        low,
        close,
        volume,
        vwap,
        transactions,
        date
        
    from {{ source('balazsillovai30823', 'sp500_stock_prices_backfill') }}

)

select * from staging