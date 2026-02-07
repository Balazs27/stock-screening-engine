with staging as (

    select

        ticker,
        article_id,
        publisher_name,
        publisher_homepage_url,
        publisher_logo_url,
        title,
        author,
        published_utc,
        article_url,
        tickers,
        image_url,
        description,
        keywords,
        date
        
    from {{ source('balazsillovai30823', 'sp500_news') }}

)

select * from staging