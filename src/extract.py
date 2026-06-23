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
            "year": "2024",
            "value": float(row["2024"]),
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
            "year": "2024",
            "value": float(row["2024"]),
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
            "year": "2024",
            "greece": 30.7,
            "eu": 26.2,
            "unit": "years",
            "source_name": "Eurostat YTH_DEMO_030"
        },
        {
            "metric": "Youth housing overburden",
            "year": "2024",
            "greece": 30.3,
            "eu": 9.7,
            "unit": "%",
            "source_name": "Eurostat ILC_LVHO07A"
        }
    ]

    return pd.DataFrame(rows)