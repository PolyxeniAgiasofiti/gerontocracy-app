import pandas as pd
import eurostat


def get_manual_appendix_b_indicators():
    data = [
        {
            "indicator_name": "Median age",
            "country": "Greece",
            "comparator": "EU",
            "year": "2025",
            "value": 47.2,
            "unit": "years",
            "source_name": "Eurostat"
        },
        {
            "indicator_name": "Median age",
            "country": "EU",
            "comparator": "EU",
            "year": "2025",
            "value": 44.9,
            "unit": "years",
            "source_name": "Eurostat"
        },
        {
            "indicator_name": "Residential property price growth",
            "country": "Greece",
            "comparator": "EU",
            "year": "2025",
            "value": 7.7,
            "unit": "%",
            "source_name": "Bank of Greece"
        },
        {
            "indicator_name": "Old-age share of social spending",
            "country": "Greece",
            "comparator": "EU",
            "year": "2023",
            "value": 52.2,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023"
        },
        {
            "indicator_name": "Housing share of social spending",
            "country": "Greece",
            "comparator": "EU",
            "year": "2023",
            "value": 0.7,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023"
        },
    ]

    return pd.DataFrame(data)


def get_leaving_parental_home_from_eurostat():
    df = eurostat.get_data_df("YTH_DEMO_030")

    filtered = df[
        (df["sex"] == "T") &
        (df["geo\\TIME_PERIOD"].isin(["EL", "EU27_2020"]))
    ]

    rows = []

    for _, row in filtered.iterrows():
        geo = row["geo\\TIME_PERIOD"]
        country = "Greece" if geo == "EL" else "EU"

        rows.append({
            "indicator_name": "Leaving parental home",
            "country": country,
            "comparator": "EU",
            "year": "2025",
            "value": float(row["2025"]),
            "unit": "years",
            "source_name": "Eurostat YTH_DEMO_030"
        })

    return pd.DataFrame(rows)


def get_housing_overburden_from_eurostat():
    df = eurostat.get_data_df("ILC_LVHO07A")

    filtered = df[
        (df["unit"] == "PC") &
        (df["rskpovth"] == "TOTAL") &
        (df["age"] == "Y15-29") &
        (df["sex"] == "T") &
        (df["geo\\TIME_PERIOD"].isin(["EL", "EU27_2020"]))
    ]

    rows = []

    for _, row in filtered.iterrows():
        geo = row["geo\\TIME_PERIOD"]
        country = "Greece" if geo == "EL" else "EU"

        rows.append({
            "indicator_name": "Youth housing overburden",
            "country": country,
            "comparator": "EU",
            "year": "2025",
            "value": float(row["2025"]),
            "unit": "%",
            "source_name": "Eurostat ILC_LVHO07A"
        })

    return pd.DataFrame(rows)


def get_all_indicators():
    manual_df = get_manual_appendix_b_indicators()
    parental_home_df = get_leaving_parental_home_from_eurostat()
    housing_df = get_housing_overburden_from_eurostat()

    return pd.concat(
        [manual_df, parental_home_df, housing_df],
        ignore_index=True
    )


def get_eurostat_demographics_dataset():
    rows = [
        {
            "metric": "Median age",
            "year": "2025",
            "greece": 47.2,
            "eu": 44.9,
            "unit": "years",
            "source_name": "Eurostat EQ_POP04"
        },
        {
            "metric": "Leaving parental home",
            "year": "2025",
            "greece": 30.9,
            "eu": 26.3,
            "unit": "years",
            "source_name": "Eurostat YTH_DEMO_030"
        },
        {
            "metric": "Youth housing overburden",
            "year": "2025",
            "greece": 25.6,
            "eu": 9.1,
            "unit": "%",
            "source_name": "Eurostat ILC_LVHO07A"
        }
    ]

    return pd.DataFrame(rows)


def get_housing_market_dataset():
    rows = [
        {
            "metric": "Residential property price growth",
            "year": "2025",
            "greece": 7.7,
            "eu": 5.5,
            "unit": "%",
            "source_name": "Bank of Greece + Eurostat PRC_HPI_A",
            "notes": "Greece value from Bank of Greece; EU comparator from Eurostat PRC_HPI_A."
        }
    ]

    return pd.DataFrame(rows)


def get_social_protection_dataset():
    rows = [
        {
            "metric": "Old-age share of social spending",
            "year": "2023",
            "greece": 52.2,
            "eu": None,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023",
            "notes": "EU comparator not explicitly available in Appendix B / provided references."
        },
        {
            "metric": "Housing share of social spending",
            "year": "2023",
            "greece": 0.7,
            "eu": None,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023",
            "notes": "EU comparator not explicitly available in Appendix B / provided references."
        }
    ]

    return pd.DataFrame(rows)


def get_median_age_eu_countries_dataset():
    rows = [
        {"country_code": "EU27_2020", "year": 2025, "median_age": 44.9, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "AT", "year": 2025, "median_age": 43.8, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "BE", "year": 2025, "median_age": 42.1, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "BG", "year": 2025, "median_age": 47.3, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "CY", "year": 2025, "median_age": 41.0, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "CZ", "year": 2025, "median_age": 44.3, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "DE", "year": 2025, "median_age": 45.5, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "DK", "year": 2025, "median_age": 42.2, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "EE", "year": 2025, "median_age": 42.9, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "EL", "year": 2025, "median_age": 47.2, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "ES", "year": 2025, "median_age": 45.8, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "FI", "year": 2025, "median_age": 43.5, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "FR", "year": 2025, "median_age": 42.8, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "HR", "year": 2025, "median_age": 45.5, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "HU", "year": 2025, "median_age": 44.8, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "IE", "year": 2025, "median_age": 39.6, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "IT", "year": 2025, "median_age": 49.1, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "LT", "year": 2025, "median_age": 44.3, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "LU", "year": 2025, "median_age": 39.8, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "LV", "year": 2025, "median_age": 44.4, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "MT", "year": 2025, "median_age": 40.0, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "NL", "year": 2025, "median_age": 42.6, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "PL", "year": 2025, "median_age": 43.4, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "PT", "year": 2025, "median_age": 47.3, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "RO", "year": 2025, "median_age": 44.1, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "SE", "year": 2025, "median_age": 41.2, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "SI", "year": 2025, "median_age": 45.5, "source_name": "Eurostat EQ_POP04"},
        {"country_code": "SK", "year": 2025, "median_age": 43.0, "source_name": "Eurostat EQ_POP04"},
    ]

    return pd.DataFrame(rows)


def get_leaving_home_eu_countries_dataset():
    rows = [
        {"country_code": "EU27_2020", "year": 2025, "age": 26.3, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "AT", "year": 2025, "age": 25.2, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "BE", "year": 2025, "age": 26.2, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "BG", "year": 2025, "age": 27.9, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "CY", "year": 2025, "age": 27.0, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "CZ", "year": 2025, "age": 25.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "DE", "year": 2025, "age": 24.1, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "DK", "year": 2025, "age": 21.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "EE", "year": 2025, "age": 22.7, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "EL", "year": 2025, "age": 30.9, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "ES", "year": 2025, "age": 30.2, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "FI", "year": 2025, "age": 21.3, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "FR", "year": 2025, "age": 23.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "HR", "year": 2025, "age": 31.5, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "HU", "year": 2025, "age": 27.3, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "IE", "year": 2025, "age": 26.9, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "IT", "year": 2025, "age": 30.2, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "LT", "year": 2025, "age": 22.7, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "LU", "year": 2025, "age": 26.6, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "LV", "year": 2025, "age": 25.7, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "MT", "year": 2025, "age": 27.5, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "NL", "year": 2025, "age": 23.4, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "PL", "year": 2025, "age": 26.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "PT", "year": 2025, "age": 28.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "RO", "year": 2025, "age": 27.4, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "SE", "year": 2025, "age": 23.1, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "SI", "year": 2025, "age": 28.8, "source_name": "Eurostat YTH_DEMO_030"},
        {"country_code": "SK", "year": 2025, "age": 30.9, "source_name": "Eurostat YTH_DEMO_030"},
    ]

    return pd.DataFrame(rows)


def get_youth_housing_overburden_eu_countries_dataset():
    rows = [
        {"country_code": "EU27_2020", "year": 2025, "overburden_rate": 9.1, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "AT", "year": 2025, "overburden_rate": 6.9, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "BE", "year": 2025, "overburden_rate": 6.1, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "BG", "year": 2025, "overburden_rate": 6.9, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "CY", "year": 2025, "overburden_rate": 2.3, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "CZ", "year": 2025, "overburden_rate": 8.4, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "DE", "year": 2025, "overburden_rate": 14.3, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "DK", "year": 2025, "overburden_rate": 26.9, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "EE", "year": 2025, "overburden_rate": 12.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "EL", "year": 2025, "overburden_rate": 25.6, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "ES", "year": 2025, "overburden_rate": 7.2, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "FI", "year": 2025, "overburden_rate": 9.8, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "FR", "year": 2025, "overburden_rate": 7.4, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "HR", "year": 2025, "overburden_rate": 1.5, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "HU", "year": 2025, "overburden_rate": 5.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "IE", "year": 2025, "overburden_rate": 5.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "IT", "year": 2025, "overburden_rate": 4.1, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "LT", "year": 2025, "overburden_rate": 5.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "LU", "year": 2025, "overburden_rate": 9.0, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "LV", "year": 2025, "overburden_rate": 5.9, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "MT", "year": 2025, "overburden_rate": 7.0, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "NL", "year": 2025, "overburden_rate": 12.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "PL", "year": 2025, "overburden_rate": 3.9, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "PT", "year": 2025, "overburden_rate": 7.5, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "RO", "year": 2025, "overburden_rate": 10.0, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "SE", "year": 2025, "overburden_rate": 13.7, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "SI", "year": 2025, "overburden_rate": 3.1, "source_name": "Eurostat ILC_LVHO07A"},
        {"country_code": "SK", "year": 2025, "overburden_rate": 3.3, "source_name": "Eurostat ILC_LVHO07A"},
    ]

    return pd.DataFrame(rows)


def get_property_price_growth_eu_countries_dataset():
    rows = [
        {"country_code": "EU27_2020", "year": 2025, "property_price_growth": 5.5, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "EL", "year": 2025, "property_price_growth": 7.7, "source_name": "Bank of Greece"},
        {"country_code": "AT", "year": 2025, "property_price_growth": 2.6, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "BE", "year": 2025, "property_price_growth": 3.2, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "BG", "year": 2025, "property_price_growth": 14.6, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "CY", "year": 2025, "property_price_growth": 4.5, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "CZ", "year": 2025, "property_price_growth": 10.4, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "DE", "year": 2025, "property_price_growth": 3.2, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "DK", "year": 2025, "property_price_growth": 7.5, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "EE", "year": 2025, "property_price_growth": 5.2, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "ES", "year": 2025, "property_price_growth": 12.7, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "FI", "year": 2025, "property_price_growth": -2.3, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "FR", "year": 2025, "property_price_growth": 0.7, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "HR", "year": 2025, "property_price_growth": 13.9, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "HU", "year": 2025, "property_price_growth": 18.3, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "IE", "year": 2025, "property_price_growth": 7.5, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "IT", "year": 2025, "property_price_growth": 4.0, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "LT", "year": 2025, "property_price_growth": 9.8, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "LU", "year": 2025, "property_price_growth": 1.6, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "LV", "year": 2025, "property_price_growth": 7.6, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "MT", "year": 2025, "property_price_growth": 6.0, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "NL", "year": 2025, "property_price_growth": 8.5, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "PL", "year": 2025, "property_price_growth": 4.9, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "PT", "year": 2025, "property_price_growth": 17.6, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "RO", "year": 2025, "property_price_growth": 5.7, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "SE", "year": 2025, "property_price_growth": 1.0, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "SI", "year": 2025, "property_price_growth": 7.3, "source_name": "Eurostat PRC_HPI_A"},
        {"country_code": "SK", "year": 2025, "property_price_growth": 12.4, "source_name": "Eurostat PRC_HPI_A"},
    ]

    return pd.DataFrame(rows)



def get_social_protection_shares_dataset():
    rows = [
        {
            "metric": "Old-age share of social spending",
            "year": 2023,
            "greece": 52.2,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023"
        },
        {
            "metric": "Housing share of social spending",
            "year": 2023,
            "greece": 0.7,
            "unit": "%",
            "source_name": "ELSTAT ESSPROS 2023"
        }
    ]

    return pd.DataFrame(rows)


EU27_COUNTRY_CODES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI",
    "FR", "DE", "EL", "HU", "IE", "IT", "LV", "LT", "LU",
    "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"
]


def get_social_protection_eu_countries_dataset():
    """
    Retrieve the share of total social-protection benefits allocated to:
    - Old age
    - Housing

    Source: Eurostat SPR_EXP_FUNC, year 2023.
    """

    df = eurostat.get_data_df("SPR_EXP_FUNC")

    geo_column = "geo\\TIME_PERIOD"
    year_column = "2023"

    required_columns = {
        "unit",
        "spfunc",
        geo_column,
        year_column,
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "Missing expected columns in SPR_EXP_FUNC: "
            f"{sorted(missing_columns)}. "
            f"Available columns: {list(df.columns)}"
        )

    # Keep annual data, where the frequency column is available.
    if "freq" in df.columns:
        df = df[df["freq"] == "A"]

    wanted_countries = ["EU27_2020"] + EU27_COUNTRY_CODES

    # PC_SPBEN = percentage share of total social-protection benefits.
    filtered = df[
        (df["unit"] == "PC_SPBEN")
        & (df["spfunc"].isin(["OLD", "HOU"]))
        & (df[geo_column].isin(wanted_countries))
    ][
        [geo_column, "spfunc", year_column]
    ].copy()

    if filtered.empty:
        available_units = sorted(df["unit"].dropna().unique().tolist())
        available_functions = sorted(
            df["spfunc"].dropna().unique().tolist()
        )

        raise ValueError(
            "No 2023 social-protection share records were found. "
            f"Available units: {available_units}. "
            f"Available functions: {available_functions}."
        )

    filtered[year_column] = pd.to_numeric(
        filtered[year_column],
        errors="coerce",
    )

    filtered = filtered.dropna(subset=[year_column])

    result = filtered.pivot_table(
        index=geo_column,
        columns="spfunc",
        values=year_column,
        aggfunc="first",
    ).reset_index()

    # Ensure the columns exist even if Eurostat has a missing value.
    if "OLD" not in result.columns:
        result["OLD"] = pd.NA

    if "HOU" not in result.columns:
        result["HOU"] = pd.NA

    result = result.rename(
        columns={
            geo_column: "country_code",
            "OLD": "old_age_share",
            "HOU": "housing_share",
        }
    )

    result["year"] = 2023
    result["unit"] = "%"
    result["source_name"] = "Eurostat SPR_EXP_FUNC"

    result = result[
        [
            "country_code",
            "year",
            "old_age_share",
            "housing_share",
            "unit",
            "source_name",
        ]
    ]

    # Display EU first and countries alphabetically afterwards.
    result["_eu_first"] = (
        result["country_code"] != "EU27_2020"
    ).astype(int)

    result = (
        result.sort_values(["_eu_first", "country_code"])
        .drop(columns="_eu_first")
        .reset_index(drop=True)
    )

    return result