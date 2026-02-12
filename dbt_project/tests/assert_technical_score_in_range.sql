-- Test: technical_score must be between 0 and 100 (inclusive)
-- Returns rows that violate the constraint (test passes when 0 rows returned)

select

    ticker,
    date,
    technical_score
    
from {{ ref('mart_sp500_technical_scores') }}
where technical_score < 0
   or technical_score > 100
   or technical_score is null
