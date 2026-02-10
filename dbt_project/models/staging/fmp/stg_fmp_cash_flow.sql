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
        net_income,
        depreciation_and_amortization,
        deferred_income_tax,
        stock_based_compensation,
        change_in_working_capital,
        accounts_receivables,
        inventory,
        accounts_payables,
        other_working_capital,
        other_non_cash_items,
        net_cash_provided_by_operating_activities,
        investments_in_property_plant_and_equipment,
        acquisitions_net,
        purchases_of_investments,
        sales_maturities_of_investments,
        other_investing_activities,
        net_cash_provided_by_investing_activities,
        net_debt_issuance,
        long_term_net_debt_issuance,
        short_term_net_debt_issuance,
        net_stock_issuance,
        net_common_stock_issuance,
        common_stock_issuance,
        common_stock_repurchased,
        net_preferred_stock_issuance,
        net_dividends_paid,
        common_dividends_paid,
        preferred_dividends_paid,
        other_financing_activities,
        net_cash_provided_by_financing_activities,
        effect_of_forex_changes_on_cash,
        net_change_in_cash,
        cash_at_end_of_period,
        cash_at_beginning_of_period,
        operating_cash_flow,
        capital_expenditure,
        free_cash_flow,
        income_taxes_paid,
        interest_paid,
        extracted_at

    from {{ source('balazsillovai30823', 'sp500_cash_flow_statements') }}

)

select * from staging
