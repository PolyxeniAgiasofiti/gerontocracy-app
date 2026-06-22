import sqlite3
import pandas as pd

DB_PATH = "database/gerontocracy.db"


def run_quality_checks():
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql("SELECT * FROM indicators", conn)

    results = []

    missing_values = df.isna().sum().sum()
    results.append({
        "table_name": "indicators",
        "check_name": "Missing values",
        "status": "PASS" if missing_values == 0 else "FAIL",
        "details": f"{missing_values} missing values found"
    })

    duplicates = df.duplicated(
        subset=["indicator_name", "country", "year", "value"]
    ).sum()

    results.append({
        "table_name": "indicators",
        "check_name": "Duplicate rows",
        "status": "PASS" if duplicates == 0 else "FAIL",
        "details": f"{duplicates} duplicate rows found"
    })

    negative_values = (df["value"] < 0).sum()
    results.append({
        "table_name": "indicators",
        "check_name": "Negative values",
        "status": "PASS" if negative_values == 0 else "FAIL",
        "details": f"{negative_values} negative values found"
    })

    quality_df = pd.DataFrame(results)

    quality_df.to_sql(
        "quality_results",
        conn,
        if_exists="replace",
        index=False
    )

    conn.close()

    return quality_df