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
    -- Step 2: Calculate daily price changes
    price_changes AS (
    
    select

        ticker,
        date,
        close,
        close - LAG(close) over (partition by ticker order by date) as price_change

    from price_data
),

    -- Step 3: Separate gains and losses
    gains_losses AS (
        
        select 

            ticker,
            date,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss

        from price_changes
),

    -- Step 4: Calculate 14-day average gains/losses
    avg_gains_losses AS (
        
        select 

            ticker,
            date,
            AVG(gain) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as avg_gain,
            AVG(loss) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as avg_loss

    from gains_losses
)

-- Step 5: Calculate RSI and combine with SMAs
select 

    ma.ticker,
    ma.date,
    ma.close,
    ma.sma_20,
    ma.sma_30,
    ma.sma_50,
    ma.sma_200,
    CASE 
        WHEN avl.avg_loss = 0 THEN 100
        ELSE 100 - (100 / (1 + (avl.avg_gain / avl.avg_loss)))
    END as rsi_14 --This is incorrect, gives me different value compared to the Polygon API, need to check the formula

from moving_averages ma
left join avg_gains_losses avl using (ticker, date)
