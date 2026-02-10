with staging as (

    select

        ticker,
        title,
        date,
        content,
        article_tickers,
        image_url,
        article_url,
        author,
        site,
        extracted_at

    from {{ source('balazsillovai30823', 'sp500_fmp_news') }}

)

select * from staging
