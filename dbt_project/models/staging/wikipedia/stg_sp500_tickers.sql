with staging as (

    select

        ticker,
        security_name as company_name,
        gics_sector as sector,
        gics_sub_industry as industry,
        headquarters_location as location,
        date_added,
        SUBSTRING(date_added, 1, 4)::INT AS date_added_year,
        cik,
        founded_year,
        extracted_at
        
    from {{ source('balazsillovai30823', 'sp500_tickers_lookup') }}

)

select * from staging