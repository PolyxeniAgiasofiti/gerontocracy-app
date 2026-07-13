import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = "database/gerontocracy.db"


TABLE_RULES = {
    "indicators": {
        "required": [
            "indicator_name",
            "country",
            "year",
            "value",
            "unit",
            "source_name",
        ],
        "key": [
            "indicator_name",
            "country",
            "year",
        ],
    },

    "eurostat_demographics": {
        "required": [
            "metric",
            "year",
            "greece",
            "eu",
            "unit",
            "source_name",
        ],
        "key": [
            "metric",
            "year",
        ],
        "expected_rows": 3,
        "ranges": {
            "greece": (0, None),
            "eu": (0, None),
        },
    },

    "housing_market": {
        "required": [
            "metric",
            "year",
            "greece",
            "eu",
            "unit",
            "source_name",
        ],
        "key": [
            "metric",
            "year",
        ],
        "expected_rows": 1,

        # Property-price growth may be negative.
        "ranges": {
            "greece": (-100, 100),
            "eu": (-100, 100),
        },
    },

    "social_protection": {
        "required": [
            "metric",
            "year",
            "greece",
            "unit",
            "source_name",
        ],
        "key": [
            "metric",
            "year",
        ],
        "expected_rows": 2,
        "ranges": {
            "greece": (0, 100),
        },
    },

    "median_age_eu_countries": {
        "required": [
            "country_code",
            "year",
            "median_age",
            "source_name",
        ],
        "key": [
            "country_code",
            "year",
        ],
        "expected_rows": 28,
        "expected_countries": 28,
        "ranges": {
            "median_age": (0, 100),
        },
    },

    "leaving_home_eu_countries": {
        "required": [
            "country_code",
            "year",
            "age",
            "source_name",
        ],
        "key": [
            "country_code",
            "year",
        ],
        "expected_rows": 28,
        "expected_countries": 28,
        "ranges": {
            "age": (0, 100),
        },
    },

    "youth_housing_eu_countries": {
        "required": [
            "country_code",
            "year",
            "overburden_rate",
            "source_name",
        ],
        "key": [
            "country_code",
            "year",
        ],
        "expected_rows": 28,
        "expected_countries": 28,
        "ranges": {
            "overburden_rate": (0, 100),
        },
    },

    "property_price_growth_eu_countries": {
        "required": [
            "country_code",
            "year",
            "property_price_growth",
            "source_name",
        ],
        "key": [
            "country_code",
            "year",
        ],
        "expected_rows": 28,
        "expected_countries": 28,

        # Negative growth is economically valid.
        "ranges": {
            "property_price_growth": (-100, 100),
        },

        "report_allowed_negatives": (
            "property_price_growth"
        ),
    },

    "social_protection_eu_countries": {
        "required": [
            "country_code",
            "year",
            "old_age_share",
            "housing_share",
            "source_name",
        ],
        "key": [
            "country_code",
            "year",
        ],
        "expected_rows": 28,
        "expected_countries": 28,
        "ranges": {
            "old_age_share": (0, 100),
            "housing_share": (0, 100),
        },
    },
}


def add_result(
    results,
    table_name,
    check_name,
    status,
    affected,
    checked,
    details,
):
    results.append(
        {
            "table_name": table_name,
            "check_name": check_name,
            "status": status,
            "affected_rows": int(affected),
            "checked_rows": int(checked),
            "details": details,
        }
    )


def run_quality_checks():
    Path(DB_PATH).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    with sqlite3.connect(DB_PATH) as conn:

        existing_tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }

        for table_name, rules in TABLE_RULES.items():

            # Check whether the table exists.
            if table_name not in existing_tables:
                add_result(
                    results,
                    table_name,
                    "Table exists",
                    "FAIL",
                    1,
                    1,
                    "Table is missing from the SQLite database",
                )
                continue

            df = pd.read_sql_query(
                f'SELECT * FROM "{table_name}"',
                conn,
            )

            row_count = len(df)

            # Check whether the table contains records.
            add_result(
                results,
                table_name,
                "Rows loaded",
                "PASS" if row_count > 0 else "FAIL",
                0 if row_count > 0 else 1,
                row_count,
                f"{row_count} rows loaded",
            )

            # Check required columns.
            required = rules.get(
                "required",
                [],
            )

            missing_columns = [
                column
                for column in required
                if column not in df.columns
            ]

            add_result(
                results,
                table_name,
                "Required columns",
                (
                    "PASS"
                    if not missing_columns
                    else "FAIL"
                ),
                len(missing_columns),
                len(required),
                (
                    "All required columns are present"
                    if not missing_columns
                    else (
                        "Missing columns: "
                        + ", ".join(missing_columns)
                    )
                ),
            )

            # Check missing values only in required columns.
            available_required = [
                column
                for column in required
                if column in df.columns
            ]

            if available_required:
                missing_counts = (
                    df[available_required]
                    .isna()
                    .sum()
                )

                missing_counts = missing_counts[
                    missing_counts > 0
                ]

                missing_total = int(
                    missing_counts.sum()
                )

                if missing_total == 0:
                    missing_details = (
                        "0 missing required values"
                    )
                else:
                    missing_details = "; ".join(
                        f"{column}: {count}"
                        for column, count
                        in missing_counts.items()
                    )

                add_result(
                    results,
                    table_name,
                    "Missing required values",
                    (
                        "PASS"
                        if missing_total == 0
                        else "FAIL"
                    ),
                    missing_total,
                    (
                        row_count
                        * len(available_required)
                    ),
                    missing_details,
                )

            # Check exact duplicate records.
            exact_duplicates = int(
                df.duplicated().sum()
            )

            add_result(
                results,
                table_name,
                "Exact duplicate rows",
                (
                    "PASS"
                    if exact_duplicates == 0
                    else "FAIL"
                ),
                exact_duplicates,
                row_count,
                (
                    f"{exact_duplicates} "
                    "exact duplicate rows"
                ),
            )

            # Check duplicated business keys.
            key = rules.get(
                "key",
                [],
            )

            if (
                key
                and all(
                    column in df.columns
                    for column in key
                )
            ):
                duplicate_key_rows = int(
                    df.duplicated(
                        subset=key,
                        keep=False,
                    ).sum()
                )

                add_result(
                    results,
                    table_name,
                    "Unique business key",
                    (
                        "PASS"
                        if duplicate_key_rows == 0
                        else "FAIL"
                    ),
                    duplicate_key_rows,
                    row_count,
                    (
                        f"{duplicate_key_rows} rows "
                        "share duplicate key values for "
                        + ", ".join(key)
                    ),
                )

            # Check expected number of records.
            expected_rows = rules.get(
                "expected_rows"
            )

            if expected_rows is not None:
                difference = abs(
                    row_count - expected_rows
                )

                add_result(
                    results,
                    table_name,
                    "Expected row count",
                    (
                        "PASS"
                        if row_count == expected_rows
                        else "WARN"
                    ),
                    difference,
                    expected_rows,
                    (
                        f"Expected {expected_rows} rows; "
                        f"found {row_count}"
                    ),
                )

            # Check EU and country coverage.
            expected_countries = rules.get(
                "expected_countries"
            )

            if (
                expected_countries is not None
                and "country_code" in df.columns
            ):
                country_count = int(
                    df["country_code"].nunique(
                        dropna=True
                    )
                )

                add_result(
                    results,
                    table_name,
                    "EU country coverage",
                    (
                        "PASS"
                        if (
                            country_count
                            == expected_countries
                        )
                        else "WARN"
                    ),
                    abs(
                        country_count
                        - expected_countries
                    ),
                    expected_countries,
                    (
                        f"Expected {expected_countries} "
                        "EU/EU-country codes; "
                        f"found {country_count}"
                    ),
                )

            # Check that a source is documented.
            if "source_name" in df.columns:
                blank_sources = int(
                    (
                        df["source_name"].isna()
                        |
                        (
                            df["source_name"]
                            .astype(str)
                            .str.strip()
                            == ""
                        )
                    ).sum()
                )

                add_result(
                    results,
                    table_name,
                    "Source documented",
                    (
                        "PASS"
                        if blank_sources == 0
                        else "FAIL"
                    ),
                    blank_sources,
                    row_count,
                    (
                        f"{blank_sources} rows "
                        "without a source name"
                    ),
                )

            # Check numeric ranges.
            for (
                column,
                bounds,
            ) in rules.get(
                "ranges",
                {},
            ).items():

                if column not in df.columns:
                    continue

                minimum, maximum = bounds

                numeric = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

                invalid_numeric = (
                    df[column].notna()
                    & numeric.isna()
                )

                out_of_range = pd.Series(
                    False,
                    index=df.index,
                )

                if minimum is not None:
                    out_of_range |= (
                        numeric < minimum
                    )

                if maximum is not None:
                    out_of_range |= (
                        numeric > maximum
                    )

                affected = int(
                    (
                        invalid_numeric
                        | out_of_range
                    ).sum()
                )

                if (
                    minimum is not None
                    and maximum is not None
                ):
                    range_text = (
                        f"{minimum} to {maximum}"
                    )
                elif minimum is not None:
                    range_text = (
                        f">= {minimum}"
                    )
                else:
                    range_text = (
                        f"<= {maximum}"
                    )

                add_result(
                    results,
                    table_name,
                    f"Valid range: {column}",
                    (
                        "PASS"
                        if affected == 0
                        else "FAIL"
                    ),
                    affected,
                    row_count,
                    (
                        f"{affected} invalid values; "
                        "accepted range is "
                        f"{range_text}"
                    ),
                )

            # Report valid negative growth rates separately.
            negative_column = rules.get(
                "report_allowed_negatives"
            )

            if (
                negative_column
                and negative_column in df.columns
            ):
                negative_count = int(
                    (
                        pd.to_numeric(
                            df[negative_column],
                            errors="coerce",
                        )
                        < 0
                    ).sum()
                )

                add_result(
                    results,
                    table_name,
                    "Negative values review",
                    "PASS",
                    negative_count,
                    row_count,
                    (
                        f"{negative_count} negative "
                        "growth values found; negative "
                        "growth is valid and is not a "
                        "data-quality error"
                    ),
                )

        quality_df = pd.DataFrame(
            results
        )

        status_order = {
            "FAIL": 0,
            "WARN": 1,
            "PASS": 2,
        }

        quality_df["_order"] = (
            quality_df["status"]
            .map(status_order)
            .fillna(3)
        )

        quality_df = (
            quality_df.sort_values(
                [
                    "_order",
                    "table_name",
                    "check_name",
                ]
            )
            .drop(columns="_order")
            .reset_index(drop=True)
        )

        quality_df.to_sql(
            "quality_results",
            conn,
            if_exists="replace",
            index=False,
        )

    return quality_df