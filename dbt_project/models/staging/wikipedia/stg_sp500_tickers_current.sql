with latest_date as (

    select max(as_of_date) as max_date
    from {{ ref('stg_sp500_tickers_snapshot') }}

)

select

    s.as_of_date,
    s.ticker,
    s.company_name,
    s.sector,
    s.industry,
    s.location,
    s.date_added,
    s.date_added_year,
    s.cik,
    s.founded_year,
    s.extracted_at

from {{ ref('stg_sp500_tickers_snapshot') }} s
join latest_date l
on s.as_of_date = l.max_date