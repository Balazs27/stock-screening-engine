{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}

with price_data AS (

    -- Full scan required: SMA-200 needs 199 preceding rows per ticker
    select * from {{ ref('stg_sp500_stock_prices') }}

),
-- Step 1: Calculate Simple Moving Averages (SMAs)
moving_averages AS (

    select
        ticker,
        date,
        close,

        -- Calculate SMAs using window functions
        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) as sma_20,

        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
        ) as sma_50,

        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
        ) as sma_200,

    from price_data
),

relative_strength_index AS (

    select

        ticker,
        timestamp,
        rsi_value,
        window_size,
        timespan,
        series_type,
        date

    from {{ ref('stg_sp500_rsi') }}
    {% if is_incremental() %}
    where date >= (select max(date) - interval '3 days' from {{ this }})
    {% endif %}

),

macd_indicator AS (

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

    from {{ ref('stg_sp500_macd') }}
    {% if is_incremental() %}
    where date >= (select max(date) - interval '3 days' from {{ this }})
    {% endif %}

),

joined AS (

    select

        ma.ticker,
        ma.date,
        ma.close,
        ROUND(ma.sma_20, 2) as sma_20,
        ROUND(ma.sma_50, 2) as sma_50,
        ROUND(ma.sma_200, 2) as sma_200,
        ROUND(rsi.rsi_value, 2) as rsi_value,
        rsi.window_size as rsi_window_size,
        rsi.timespan as rsi_timespan, --unneccesary column but for clarity keeping it here in the int model
        rsi.series_type as rsi_series_type, --unneccesary column but for clarity keeping it here in the int model
        ROUND(macd.macd_value, 4) as macd_value,
        ROUND(macd.signal_value, 4) as macd_signal,
        ROUND(macd.histogram_value, 4) as macd_histogram

    from moving_averages ma
    left join relative_strength_index rsi
    on ma.ticker = rsi.ticker and ma.date = rsi.date
    left join macd_indicator macd
    on ma.ticker = macd.ticker and ma.date = macd.date

)

select * from joined
{% if is_incremental() %}
where date >= (select max(date) - interval '3 days' from {{ this }})
{% endif %}
