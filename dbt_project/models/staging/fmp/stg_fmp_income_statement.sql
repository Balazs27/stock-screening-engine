with staging as (

    select

        ticker,
        date,
        reported_currency,
        cik,
        filing_date,
        accepted_date,
        fiscal_year,
        period,
        revenue,
        cost_of_revenue,
        gross_profit,
        research_and_development_expenses,
        general_and_administrative_expenses,
        selling_and_marketing_expenses,
        selling_general_and_administrative_expenses,
        other_expenses,
        operating_expenses,
        cost_and_expenses,
        net_interest_income,
        interest_income,
        interest_expense,
        depreciation_and_amortization,
        ebitda,
        ebit,
        non_operating_income_excluding_interest,
        operating_income,
        total_other_income_expenses_net,
        income_before_tax,
        income_tax_expense,
        net_income_from_continuing_operations,
        net_income_from_discontinued_operations,
        other_adjustments_to_net_income,
        net_income,
        net_income_deductions,
        bottom_line_net_income,
        eps,
        eps_diluted,
        weighted_average_shares_out,
        weighted_average_shares_out_diluted,
        extracted_at

    from {{ source('balazsillovai30823', 'sp500_income_statements') }}

)

select * from staging
