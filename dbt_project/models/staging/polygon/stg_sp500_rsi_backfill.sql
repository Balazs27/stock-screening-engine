with staging AS (

    select

        ticker,
        timestamp,
        rsi_value,
        window_size,
        timespan,
        series_type,
        date
        
    from {{ source('balazsillovai30823', 'sp500_rsi_backfill') }}

)

select * from staging
