with price_data AS (

    select * from {{ ref('stg_sp500_stock_prices_backfill') }}

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
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) as sma_30,
        
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
        
        -- Calculate RSI (Relative Strength Index)
        -- RSI = 100 - (100 / (1 + RS)), where RS = Avg Gain / Avg Loss over 14 days
        -- (Simplified - full formula would be longer)
        
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

),

joined AS (

    select

        ma.ticker,
        ma.date,
        ma.close,
        ROUND(ma.sma_20, 2) as sma_20,
        ROUND(ma.sma_30, 2) as sma_30,
        ROUND(ma.sma_50, 2) as sma_50,
        ROUND(ma.sma_200, 2) as sma_200,
        ROUND(rsi.rsi_value, 2) as rsi_value,
        rsi.window_size as rsi_window_size,
        rsi.timespan as rsi_timespan, --unneccesary column but for clarity keeping it here in the int model
        rsi.series_type as rsi_series_type --unneccesary column but for clarity keeping it here in the int model
        
    from moving_averages ma
    left join relative_strength_index rsi
    on ma.ticker = rsi.ticker and ma.date = rsi.date

)

select * from joined
