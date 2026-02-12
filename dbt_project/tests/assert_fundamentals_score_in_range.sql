-- Test: fundamentals_score must be between 0 and 100 (inclusive)
-- Returns rows that violate the constraint (test passes when 0 rows returned)

select

    ticker,
    date,
    fundamentals_score
    
from {{ ref('mart_sp500_fundamental_scores') }}
where fundamentals_score < 0
   or fundamentals_score > 100
   or fundamentals_score is null
