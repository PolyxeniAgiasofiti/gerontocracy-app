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
            "indicator_name": "Youth housing overburden",
            "country": "Greece",
            "comparator": "EU",
            "year": "2024",
            "value": 30.3,
            "unit": "%",
            "source_name": "Eurostat"
        },
        {
            "indicator_name": "Youth housing overburden",
            "country": "EU",
            "comparator": "EU",
            "year": "2024",
            "value": 9.7,
            "unit": "%",
            "source_name": "Eurostat"
        }
    ]

    return pd.DataFrame(data)


def get_leaving_parental_home_from_eurostat():
    dataset_code = "YTH_DEMO_030"
    df = eurostat.get_data_df(dataset_code)

    filtered = df[
        (df["sex"] == "T") &
        (df["geo\\TIME_PERIOD"].isin(["EL", "EU27_2020"]))
    ]

    rows = []

    for _, row in filtered.iterrows():
        geo = row["geo\\TIME_PERIOD"]

        if geo == "EL":
            country = "Greece"
        elif geo == "EU27_2020":
            country = "EU"
        else:
            country = geo

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


def get_all_indicators():
    manual_df = get_manual_appendix_b_indicators()
    parental_home_df = get_leaving_parental_home_from_eurostat()

    return pd.concat([manual_df, parental_home_df], ignore_index=True)