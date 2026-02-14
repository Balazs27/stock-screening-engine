with base as (

    select

        as_of_date,
        ticker,
        company_name,
        sector,
        industry,
        location,
        cik,
        founded_year,
        date_added,
        date_added_year,
        extracted_at

    from {{ ref('stg_sp500_tickers_current') }}

)

select * from base