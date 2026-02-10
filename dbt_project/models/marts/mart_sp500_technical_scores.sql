WITH technical_features AS (

    SELECT * FROM {{ ref('int_sp500_technical_indicators') }}

),

scoring AS (

    SELECT

        ticker,
        date,
        
        -- Component 1: Trend Confirmation (40 pts)
        CASE 
            WHEN close > sma_20 AND close > sma_50 AND close > sma_200 THEN 40
            WHEN close > sma_20 AND close > sma_50 THEN 30
            WHEN close > sma_20 THEN 20
            WHEN close > sma_50 THEN 10
            ELSE 5
        END as trend_score,
        
        -- Component 2: Momentum Quality (30 pts)
        CASE
            WHEN rsi_value BETWEEN 50 AND 70 THEN 30
            WHEN rsi_value BETWEEN 40 AND 80 THEN 20
            WHEN rsi_value > 70 THEN 15
            WHEN rsi_value BETWEEN 30 AND 40 THEN 10
            WHEN rsi_value < 30 THEN 5
            ELSE 15
        END as momentum_score,
        
        -- Component 3: Price Action (20 pts)
        (close - LAG(close, 20) OVER (PARTITION BY ticker ORDER BY date)) 
            / LAG(close, 20) OVER (PARTITION BY ticker ORDER BY date) * 100 as pct_change_20d,
            
        -- Component 4: MACD Signal (10 pts)
        CASE
            WHEN macd_value > macd_signal AND macd_value > 0 THEN 10
            WHEN macd_value > macd_signal THEN 7
            WHEN macd_value < macd_signal AND macd_value < 0 THEN 3
            ELSE 5
        END as macd_score

    FROM technical_features
)

SELECT
    ticker,
    date,
    trend_score,
    momentum_score,
    macd_score,
    CASE
        WHEN pct_change_20d > 10 THEN 20
        WHEN pct_change_20d > 5 THEN 15
        WHEN pct_change_20d > 0 THEN 10
        WHEN pct_change_20d > -5 THEN 5
        ELSE 0
    END as price_action_score,

    (trend_score + momentum_score + macd_score + price_action_score) as technical_score

FROM scoring