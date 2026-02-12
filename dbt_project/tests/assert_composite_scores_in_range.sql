-- Test: all composite score variants must be between 0 and 100 (inclusive)
-- Returns rows that violate the constraint (test passes when 0 rows returned)
--These will fail because for not every technical score do we have fundamentals, there for we won't have composite scores!!!!!

select

    ticker,
    technical_date,
    composite_score_equal,
    composite_score_technical_bias,
    composite_score_fundamental_bias

from {{ ref('mart_sp500_composite_scores') }}
where composite_score_equal < 0
   or composite_score_equal > 100
   or composite_score_equal is null
   or composite_score_technical_bias < 0
   or composite_score_technical_bias > 100
   or composite_score_technical_bias is null
   or composite_score_fundamental_bias < 0
   or composite_score_fundamental_bias > 100
   or composite_score_fundamental_bias is null
