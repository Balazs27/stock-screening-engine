with staging as (

    select

        ticker,
        timestamp,
        macd_value,
        signal_value,
        histogram_value,
        short_window,
        long_window,
        signal_window,
        timespan,
        series_type,
        date

    from {{ source('balazsillovai30823', 'sp500_macd') }}

)

select * from staging
