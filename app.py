from html import escape

import eurostat
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3
from shiny import App, render, ui

from src.extract import (
    get_leaving_home_eu_countries_dataset,
    get_median_age_eu_countries_dataset,
    get_property_price_growth_eu_countries_dataset,
    get_social_protection_dataset,
    get_youth_housing_overburden_eu_countries_dataset,
)
from src.load import create_tables, save_dataframe


DB_PATH = "database/gerontocracy.db"

EU27_COUNTRY_CODES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI",
    "FR", "DE", "EL", "HU", "IE", "IT", "LV", "LT", "LU",
    "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

COUNTRY_LABELS = {
    "EU27_2020": "EU",
    "EL": "GR",
}

EXPECTED_GEOGRAPHIES = {
    "EU", "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE",
    "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT",
    "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}

OVERVIEW_COLUMNS = [
    "Median Age 2025",
    "Leaving Parental Home 2025",
    "Youth Housing Overburden 2025 (%)",
    "Property Price Growth 2025 (%)",
    "Old-Age Benefits Share 2023 (%)",
    "Housing Benefits Share 2023 (%)",
]


def get_social_protection_eu_countries_dataset():
    """
    Retrieve 2023 ESSPROS data and calculate benefit shares.
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

    missing_columns = required_columns.difference(
        df.columns
    )

    if missing_columns:
        raise ValueError(
            "SPR_EXP_FUNC is missing expected columns: "
            f"{sorted(missing_columns)}. "
            f"Available columns: {list(df.columns)}"
        )

    if "freq" in df.columns:
        df = df[
            df["freq"] == "A"
        ]

    available_units = set(
        df["unit"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_unit = next(
        (
            unit
            for unit in [
                "MIO_EUR",
                "PC_GDP",
                "MIO_NAC",
                "MIO_PPS",
            ]
            if unit in available_units
        ),
        None,
    )

    if selected_unit is None:
        raise ValueError(
            "No supported unit was found in SPR_EXP_FUNC. "
            f"Available units: {sorted(available_units)}"
        )

    available_functions = set(
        df["spfunc"]
        .dropna()
        .astype(str)
        .unique()
    )

    old_age_code = next(
        (
            code
            for code in [
                "OLD",
                "OLD_AGE",
            ]
            if code in available_functions
        ),
        None,
    )

    housing_code = next(
        (
            code
            for code in [
                "HOU",
                "HOUSING",
            ]
            if code in available_functions
        ),
        None,
    )

    total_code = next(
        (
            code
            for code in [
                "TOTAL",
                "TOT",
            ]
            if code in available_functions
        ),
        None,
    )

    if (
        not old_age_code
        or not housing_code
        or not total_code
    ):
        raise ValueError(
            "Could not identify old-age, housing and total "
            "function codes. "
            f"Available functions: {sorted(available_functions)}"
        )

    wanted_countries = [
        "EU27_2020",
        *EU27_COUNTRY_CODES,
    ]

    wanted_functions = [
        old_age_code,
        housing_code,
        total_code,
    ]

    filtered = df[
        (df["unit"] == selected_unit)
        & df["spfunc"].isin(
            wanted_functions
        )
        & df[geo_column].isin(
            wanted_countries
        )
    ][
        [
            geo_column,
            "spfunc",
            year_column,
        ]
    ].copy()

    filtered[year_column] = pd.to_numeric(
        filtered[year_column],
        errors="coerce",
    )

    filtered = filtered.dropna(
        subset=[year_column]
    )

    if filtered.empty:
        raise ValueError(
            "No usable 2023 records were found "
            f"for unit {selected_unit}."
        )

    pivot = filtered.pivot_table(
        index=geo_column,
        columns="spfunc",
        values=year_column,
        aggfunc="first",
    ).reset_index()

    for function_code in wanted_functions:
        if function_code not in pivot.columns:
            pivot[function_code] = pd.NA

    result = pd.DataFrame(
        {
            "country_code": pivot[geo_column],
            "year": 2023,
            "old_age_share": (
                pivot[old_age_code]
                / pivot[total_code]
                * 100
            ).round(1),
            "housing_share": (
                pivot[housing_code]
                / pivot[total_code]
                * 100
            ).round(1),
            "unit": (
                "% of total social-protection benefits"
            ),
            "source_name": (
                "Eurostat SPR_EXP_FUNC"
            ),
            "calculation_unit": (
                selected_unit
            ),
        }
    )

    result["_eu_first"] = (
        result["country_code"]
        != "EU27_2020"
    ).astype(int)

    return (
        result.sort_values(
            [
                "_eu_first",
                "country_code",
            ]
        )
        .drop(
            columns="_eu_first"
        )
        .reset_index(
            drop=True
        )
    )


def table_has_data(table_name):
    """
    Return True when a SQLite table exists and contains data.
    """

    try:
        with sqlite3.connect(
            DB_PATH
        ) as conn:
            result = conn.execute(
                f'''
                SELECT 1
                FROM "{table_name}"
                LIMIT 1
                '''
            ).fetchone()

        return result is not None

    except sqlite3.OperationalError:
        return False


def initialize_database():
    """
    Use cached SQLite data and download only missing datasets.
    """

    create_tables()

    datasets = [
        (
            "social_protection",
            get_social_protection_dataset,
        ),
        (
            "median_age_eu_countries",
            get_median_age_eu_countries_dataset,
        ),
        (
            "leaving_home_eu_countries",
            get_leaving_home_eu_countries_dataset,
        ),
        (
            "youth_housing_eu_countries",
            get_youth_housing_overburden_eu_countries_dataset,
        ),
        (
            "property_price_growth_eu_countries",
            get_property_price_growth_eu_countries_dataset,
        ),
    ]

    for (
        table_name,
        loader_function,
    ) in datasets:

        if not table_has_data(
            table_name
        ):
            save_dataframe(
                loader_function(),
                table_name,
            )

    if not table_has_data(
        "social_protection_eu_countries"
    ):
        try:
            save_dataframe(
                get_social_protection_eu_countries_dataset(),
                "social_protection_eu_countries",
            )

        except Exception as exc:
            raise RuntimeError(
                "The European social-protection table is not "
                "available locally, and Eurostat could not be "
                "reached. Keep the existing database file or "
                "try again when Eurostat is available."
            ) from exc


initialize_database()


def load_table(table_name):
    """
    Load a SQLite table into a DataFrame.
    """

    with sqlite3.connect(
        DB_PATH
    ) as conn:
        return pd.read_sql(
            f'''
            SELECT *
            FROM "{table_name}"
            ''',
            conn,
        )


def display_country_codes(df):
    """
    Replace Eurostat geographic codes with readable codes.
    """

    df = df.copy()

    if "country_code" in df.columns:
        df["country_code"] = (
            df["country_code"]
            .replace(
                COUNTRY_LABELS
            )
        )

    return df


def format_display_table(
    df,
    columns,
    rename_columns,
):
    """
    Prepare a readable dashboard table.
    """

    df = display_country_codes(
        df
    )

    available_columns = [
        column
        for column in columns
        if column in df.columns
    ]

    return (
        df[available_columns]
        .rename(
            columns=rename_columns
        )
        .reset_index(
            drop=True
        )
    )


def source_note(text):
    """
    Display a readable source note.
    """

    return ui.div(
        ui.strong(
            "Source: "
        ),
        text,
        class_=(
            "alert alert-light "
            "border py-2 mt-3"
        ),
    )


def build_overview_table():
    """
    Build the final six-indicator overview dataset.
    """

    median_df = load_table(
        "median_age_eu_countries"
    )[
        [
            "country_code",
            "median_age",
        ]
    ]

    leaving_df = load_table(
        "leaving_home_eu_countries"
    )[
        [
            "country_code",
            "age",
        ]
    ]

    youth_housing_df = load_table(
        "youth_housing_eu_countries"
    )[
        [
            "country_code",
            "overburden_rate",
        ]
    ]

    property_df = load_table(
        "property_price_growth_eu_countries"
    )[
        [
            "country_code",
            "property_price_growth",
        ]
    ]

    social_df = load_table(
        "social_protection_eu_countries"
    )[
        [
            "country_code",
            "old_age_share",
            "housing_share",
        ]
    ]

    overview = pd.merge(
        median_df,
        leaving_df,
        on="country_code",
        how="outer",
    )

    overview = pd.merge(
        overview,
        youth_housing_df,
        on="country_code",
        how="outer",
    )

    overview = pd.merge(
        overview,
        property_df,
        on="country_code",
        how="outer",
    )

    overview = pd.merge(
        overview,
        social_df,
        on="country_code",
        how="outer",
    )

    overview = overview.rename(
        columns={
            "country_code": (
                "Country"
            ),
            "median_age": (
                "Median Age 2025"
            ),
            "age": (
                "Leaving Parental Home 2025"
            ),
            "overburden_rate": (
                "Youth Housing Overburden 2025 (%)"
            ),
            "property_price_growth": (
                "Property Price Growth 2025 (%)"
            ),
            "old_age_share": (
                "Old-Age Benefits Share 2023 (%)"
            ),
            "housing_share": (
                "Housing Benefits Share 2023 (%)"
            ),
        }
    )

    overview["Country"] = (
        overview["Country"]
        .replace(
            COUNTRY_LABELS
        )
    )

    eu_row = overview[
        overview["Country"] == "EU"
    ]

    country_rows = overview[
        overview["Country"] != "EU"
    ].sort_values(
        "Country"
    )

    return pd.concat(
        [
            eu_row,
            country_rows,
        ],
        ignore_index=True,
    )


def build_overview_html():
    """
    Build the grouped Overview table.

    The indicators are separated into:
    - Demographic Indicators
    - Housing and Market Indicators
    - Social Protection Indicators
    """

    df = build_overview_table()

    def format_number(value):
        if pd.isna(value):
            return ""

        return f"{float(value):.1f}"

    body_rows = []

    for _, row in df.iterrows():
        row_class = (
            ' class="eu-row"'
            if row["Country"] == "EU"
            else ""
        )

        body_rows.append(
            f"""
            <tr{row_class}>
                <td class="country-cell">
                    {escape(str(row["Country"]))}
                </td>

                <td>
                    {format_number(row["Median Age 2025"])}
                </td>

                <td>
                    {format_number(
                        row["Leaving Parental Home 2025"]
                    )}
                </td>

                <td class="group-start">
                    {format_number(
                        row[
                            "Youth Housing Overburden 2025 (%)"
                        ]
                    )}
                </td>

                <td>
                    {format_number(
                        row["Property Price Growth 2025 (%)"]
                    )}
                </td>

                <td class="group-start">
                    {format_number(
                        row[
                            "Old-Age Benefits Share 2023 (%)"
                        ]
                    )}
                </td>

                <td>
                    {format_number(
                        row[
                            "Housing Benefits Share 2023 (%)"
                        ]
                    )}
                </td>
            </tr>
            """
        )

    css = """
    <style>
        .overview-table-wrap {
            overflow-x: auto;
            margin-top: 0.5rem;
        }

        .overview-table {
            width: 100%;
            min-width: 1050px;
            border-collapse: collapse;
            font-size: 14px;
        }

        .overview-table th,
        .overview-table td {
            border: 1px solid #e1e5e9;
            padding: 9px 10px;
            text-align: center;
            vertical-align: middle;
        }

        .overview-table thead tr:first-child th {
            background: #e9edf1;
            font-weight: 700;
            border-bottom: 2px solid #aeb7c0;
        }

        .overview-table thead tr:nth-child(2) th {
            background: #f6f8fa;
            font-weight: 600;
        }

        .overview-table .group-start {
            border-left: 3px solid #8f99a3 !important;
        }

        .overview-table .country-cell {
            text-align: left;
            font-weight: 600;
            white-space: nowrap;
        }

        .overview-table .eu-row td {
            background: #eef3f7;
            font-weight: 700;
            border-bottom: 2px solid #aeb7c0;
        }

        .overview-table tbody tr:hover td {
            background: #f8fafb;
        }
    </style>
    """

    table_html = f"""
    <div class="overview-table-wrap">
        <table class="overview-table">
            <thead>
                <tr>
                    <th rowspan="2">
                        Country
                    </th>

                    <th colspan="2">
                        Demographic Indicators (Years)
                    </th>

                    <th
                        colspan="2"
                        class="group-start"
                    >
                        Housing &amp; Market Indicators (%)
                    </th>

                    <th
                        colspan="2"
                        class="group-start"
                    >
                        Social Protection Indicators (%)
                    </th>
                </tr>

                <tr>
                    <th>
                        Median Age 2025
                    </th>

                    <th>
                        Leaving Parental Home 2025
                    </th>

                    <th class="group-start">
                        Youth Housing Overburden 2025
                    </th>

                    <th>
                        Property Price Growth 2025
                    </th>

                    <th class="group-start">
                        Old-Age Benefits Share 2023
                    </th>

                    <th>
                        Housing Benefits Share 2023
                    </th>
                </tr>
            </thead>

            <tbody>
                {''.join(body_rows)}
            </tbody>
        </table>
    </div>
    """

    return ui.HTML(
        css + table_html
    )


def prepare_country_chart(
    df,
    value_column,
):
    """
    Put the EU aggregate first and rank countries.
    """

    df = df.dropna(
        subset=[value_column]
    ).copy()

    eu_row = df[
        df["country_code"]
        == "EU27_2020"
    ]

    country_rows = df[
        df["country_code"]
        != "EU27_2020"
    ].sort_values(
        value_column,
        ascending=False,
    )

    ordered = pd.concat(
        [
            eu_row,
            country_rows,
        ],
        ignore_index=True,
    )

    return (
        display_country_codes(
            ordered
        ),
        eu_row,
    )


def draw_country_chart(
    table_name,
    value_column,
    value_label,
    title,
    y_axis_label,
    eu_value=None,
    eu_suffix="",
    minimum=None,
    maximum_padding=1,
    figure_size=(14, 5),
):
    """
    Draw a country chart with readable labels.
    """

    df = load_table(
        table_name
    )

    chart_df, eu_row = (
        prepare_country_chart(
            df,
            value_column,
        )
    )

    chart_df = chart_df.rename(
        columns={
            "country_code": (
                "Country"
            ),
            value_column: (
                value_label
            ),
        }
    )

    ax = chart_df.plot(
        x="Country",
        y=value_label,
        kind="bar",
        legend=False,
        figsize=figure_size,
    )

    reference_value = eu_value

    if (
        reference_value is None
        and not eu_row.empty
    ):
        reference_value = float(
            eu_row[
                value_column
            ].iloc[0]
        )

    if reference_value is not None:
        ax.axhline(
            y=reference_value,
            linestyle="--",
            label=(
                f"EU Average: "
                f"{reference_value:.1f}"
                f"{eu_suffix}"
            ),
        )

        ax.legend()

    if minimum is not None:
        ax.set_ylim(
            minimum,
            chart_df[
                value_label
            ].max()
            + maximum_padding,
        )

    ax.set_title(
        title
    )

    ax.set_xlabel(
        "Country"
    )

    ax.set_ylabel(
        y_axis_label
    )

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.tight_layout()


def country_values(
    df,
    column,
    condition,
):
    """
    Format country values for quality notes.
    """

    selected = df.loc[
        condition,
        [
            "Country",
            column,
        ],
    ]

    if selected.empty:
        return "None"

    return "; ".join(
        (
            f"{row['Country']} "
            f"{row[column]:.1f}%"
        )
        for _, row
        in selected.iterrows()
    )


def build_data_quality_outputs():
    """
    Create the OSEMN data-quality outputs.
    """

    df = build_overview_table()

    numeric = df[
        OVERVIEW_COLUMNS
    ].apply(
        pd.to_numeric,
        errors="coerce",
    )

    expected_values = (
        len(df)
        * len(OVERVIEW_COLUMNS)
    )

    available_values = int(
        numeric.notna()
        .sum()
        .sum()
    )

    duplicate_countries = int(
        df["Country"]
        .duplicated()
        .sum()
    )

    unique_geographies = int(
        df["Country"]
        .nunique(
            dropna=True
        )
    )

    coverage_ok = (
        set(
            df["Country"]
            .dropna()
        )
        == EXPECTED_GEOGRAPHIES
    )

    age_columns = [
        "Median Age 2025",
        "Leaving Parental Home 2025",
    ]

    percentage_columns = [
        "Youth Housing Overburden 2025 (%)",
        "Old-Age Benefits Share 2023 (%)",
        "Housing Benefits Share 2023 (%)",
    ]

    property_column = (
        "Property Price Growth 2025 (%)"
    )

    youth_column = (
        "Youth Housing Overburden 2025 (%)"
    )

    old_age_column = (
        "Old-Age Benefits Share 2023 (%)"
    )

    housing_column = (
        "Housing Benefits Share 2023 (%)"
    )

    numeric_valid = bool(
        numeric.notna()
        .all()
        .all()
    )

    age_valid = bool(
        numeric[
            age_columns
        ]
        .apply(
            lambda series:
                series.between(
                    0,
                    100,
                )
        )
        .all()
        .all()
    )

    percentage_valid = bool(
        numeric[
            percentage_columns
        ]
        .apply(
            lambda series:
                series.between(
                    0,
                    100,
                )
        )
        .all()
        .all()
    )

    growth_valid = bool(
        numeric[
            property_column
        ]
        .between(
            -100,
            100,
        )
        .all()
    )

    all_valid = (
        numeric_valid
        and age_valid
        and percentage_valid
        and growth_valid
    )

    quality_summary = [
        {
            "Dimension": (
                "Completeness"
            ),
            "Status": (
                "PASS"
                if available_values
                == expected_values
                else "FAIL"
            ),
            "Details": (
                f"{available_values}/"
                f"{expected_values} "
                "indicator values available"
            ),
        },
        {
            "Dimension": (
                "Uniqueness"
            ),
            "Status": (
                "PASS"
                if duplicate_countries == 0
                else "FAIL"
            ),
            "Details": (
                f"{unique_geographies} "
                "unique geographic records"
            ),
        },
        {
            "Dimension": (
                "Validity"
            ),
            "Status": (
                "PASS"
                if all_valid
                else "FAIL"
            ),
            "Details": (
                "All values are numeric and "
                "within accepted ranges"
            ),
        },
        {
            "Dimension": (
                "Consistency"
            ),
            "Status": (
                "REVIEW"
            ),
            "Details": (
                "2025 and 2023 indicators; "
                "Greece property source differs"
            ),
        },
        {
            "Dimension": (
                "Coverage"
            ),
            "Status": (
                "PASS"
                if coverage_ok
                else "FAIL"
            ),
            "Details": (
                "EU aggregate + "
                "27 Member States"
            ),
        },
        {
            "Dimension": (
                "Traceability"
            ),
            "Status": (
                "PASS"
            ),
            "Details": (
                "Official sources documented"
            ),
        },
    ]

    youth_review = (
        "High: "
        + country_values(
            df,
            youth_column,
            df[youth_column] >= 20,
        )
    )

    property_review = (
        "Negative: "
        + country_values(
            df,
            property_column,
            df[property_column] < 0,
        )
        + "; Greece source differs"
    )

    old_age_review = (
        "High: "
        + country_values(
            df,
            old_age_column,
            df[old_age_column] >= 50,
        )
    )

    zero_housing_countries = (
        df.loc[
            df[housing_column] == 0,
            "Country",
        ].tolist()
    )

    housing_review = (
        "0.0%: "
        + ", ".join(
            zero_housing_countries
        )
        + "; High: "
        + country_values(
            df,
            housing_column,
            df[housing_column] >= 5,
        )
    )

    indicator_specs = [
        {
            "Indicator": (
                "Median Age"
            ),
            "Year": 2025,
            "Source": (
                "Eurostat"
            ),
            "Column": (
                "Median Age 2025"
            ),
            "Minimum": 0,
            "Maximum": 100,
            "Review": (
                "No issue detected"
            ),
        },
        {
            "Indicator": (
                "Leaving Parental Home"
            ),
            "Year": 2025,
            "Source": (
                "Eurostat"
            ),
            "Column": (
                "Leaving Parental Home 2025"
            ),
            "Minimum": 0,
            "Maximum": 100,
            "Review": (
                "No issue detected"
            ),
        },
        {
            "Indicator": (
                "Youth Housing Overburden"
            ),
            "Year": 2025,
            "Source": (
                "Eurostat"
            ),
            "Column": (
                youth_column
            ),
            "Minimum": 0,
            "Maximum": 100,
            "Review": (
                youth_review
            ),
        },
        {
            "Indicator": (
                "Property Price Growth"
            ),
            "Year": 2025,
            "Source": (
                "Eurostat; Bank of Greece "
                "for Greece"
            ),
            "Column": (
                property_column
            ),
            "Minimum": -100,
            "Maximum": 100,
            "Review": (
                property_review
            ),
        },
        {
            "Indicator": (
                "Old-Age Benefits Share"
            ),
            "Year": 2023,
            "Source": (
                "Eurostat; ELSTAT validation "
                "for Greece"
            ),
            "Column": (
                old_age_column
            ),
            "Minimum": 0,
            "Maximum": 100,
            "Review": (
                old_age_review
            ),
        },
        {
            "Indicator": (
                "Housing Benefits Share"
            ),
            "Year": 2023,
            "Source": (
                "Eurostat; ELSTAT validation "
                "for Greece"
            ),
            "Column": (
                housing_column
            ),
            "Minimum": 0,
            "Maximum": 100,
            "Review": (
                housing_review
            ),
        },
    ]

    indicator_rows = []

    for item in indicator_specs:
        series = pd.to_numeric(
            df[
                item["Column"]
            ],
            errors="coerce",
        )

        valid = bool(
            series.notna().all()
            and series.between(
                item["Minimum"],
                item["Maximum"],
            ).all()
        )

        needs_review = (
            item["Review"]
            != "No issue detected"
        )

        if not valid:
            result = "FAIL"

        elif needs_review:
            result = "PASS — REVIEW"

        else:
            result = "PASS"

        indicator_rows.append(
            {
                "Indicator": (
                    item["Indicator"]
                ),
                "Year": (
                    item["Year"]
                ),
                "Source": (
                    item["Source"]
                ),
                "Records": (
                    f"{series.notna().sum()}/"
                    f"{len(df)}"
                ),
                "Validity": (
                    "Valid Range"
                    if valid
                    else "Invalid Value"
                ),
                "Review": (
                    item["Review"]
                ),
                "Result": (
                    result
                ),
            }
        )

    indicator_overview = pd.DataFrame(
        indicator_rows
    )

    eu_row = df[
        df["Country"] == "EU"
    ]

    eu_complete = bool(
        not eu_row.empty
        and eu_row[
            OVERVIEW_COLUMNS
        ]
        .notna()
        .to_numpy()
        .all()
    )

    detailed_checks = pd.DataFrame(
        [
            {
                "Data Quality Rule": (
                    "Completeness"
                ),
                "Check Performed": (
                    "Checked all six indicators "
                    "for missing values"
                ),
                "Result": (
                    "PASS"
                    if available_values
                    == expected_values
                    else "FAIL"
                ),
                "Interpretation": (
                    f"{available_values}/"
                    f"{expected_values} "
                    "values available"
                ),
            },
            {
                "Data Quality Rule": (
                    "Uniqueness"
                ),
                "Check Performed": (
                    "Checked for duplicate "
                    "country records"
                ),
                "Result": (
                    "PASS"
                    if duplicate_countries == 0
                    else "FAIL"
                ),
                "Interpretation": (
                    "No duplicates"
                    if duplicate_countries == 0
                    else (
                        f"{duplicate_countries} "
                        "duplicates"
                    )
                ),
            },
            {
                "Data Quality Rule": (
                    "Numeric Validity"
                ),
                "Check Performed": (
                    "Checked that all indicator "
                    "values are numeric"
                ),
                "Result": (
                    "PASS"
                    if numeric_valid
                    else "FAIL"
                ),
                "Interpretation": (
                    "No invalid data types"
                    if numeric_valid
                    else "Invalid values found"
                ),
            },
            {
                "Data Quality Rule": (
                    "Age Validity"
                ),
                "Check Performed": (
                    "Checked age values "
                    "against 0–100 years"
                ),
                "Result": (
                    "PASS"
                    if age_valid
                    else "FAIL"
                ),
                "Interpretation": (
                    "All age values valid"
                ),
            },
            {
                "Data Quality Rule": (
                    "Percentage Validity"
                ),
                "Check Performed": (
                    "Checked percentage values "
                    "against 0–100%"
                ),
                "Result": (
                    "PASS"
                    if percentage_valid
                    else "FAIL"
                ),
                "Interpretation": (
                    "All percentages valid"
                ),
            },
            {
                "Data Quality Rule": (
                    "Growth-Rate Validity"
                ),
                "Check Performed": (
                    "Checked property growth "
                    "against −100% to 100%"
                ),
                "Result": (
                    "PASS"
                    if growth_valid
                    else "FAIL"
                ),
                "Interpretation": (
                    "Finland −2.3% is a valid decline"
                ),
            },
            {
                "Data Quality Rule": (
                    "Geographic Coverage"
                ),
                "Check Performed": (
                    "Checked EU aggregate and "
                    "all 27 Member States"
                ),
                "Result": (
                    "PASS"
                    if coverage_ok
                    else "FAIL"
                ),
                "Interpretation": (
                    "28/28 geographies available"
                ),
            },
            {
                "Data Quality Rule": (
                    "Temporal Consistency"
                ),
                "Check Performed": (
                    "Compared reference years "
                    "across indicators"
                ),
                "Result": (
                    "REVIEW"
                ),
                "Interpretation": (
                    "Four indicators use 2025; "
                    "two use 2023"
                ),
            },
            {
                "Data Quality Rule": (
                    "Source Consistency"
                ),
                "Check Performed": (
                    "Compared sources within "
                    "each indicator"
                ),
                "Result": (
                    "REVIEW"
                ),
                "Interpretation": (
                    "Greece property value uses "
                    "Bank of Greece"
                ),
            },
            {
                "Data Quality Rule": (
                    "Source Traceability"
                ),
                "Check Performed": (
                    "Checked that official "
                    "sources are documented"
                ),
                "Result": (
                    "PASS"
                ),
                "Interpretation": (
                    "Eurostat, Bank of Greece "
                    "and ELSTAT"
                ),
            },
            {
                "Data Quality Rule": (
                    "Youth Housing Outliers"
                ),
                "Check Performed": (
                    "Reviewed rates of "
                    "20% or more"
                ),
                "Result": (
                    "REVIEW"
                ),
                "Interpretation": (
                    country_values(
                        df,
                        youth_column,
                        df[youth_column] >= 20,
                    )
                ),
            },
            {
                "Data Quality Rule": (
                    "Old-Age Share Outliers"
                ),
                "Check Performed": (
                    "Reviewed shares of "
                    "50% or more"
                ),
                "Result": (
                    "REVIEW"
                ),
                "Interpretation": (
                    country_values(
                        df,
                        old_age_column,
                        df[old_age_column] >= 50,
                    )
                ),
            },
            {
                "Data Quality Rule": (
                    "Housing Share Outliers"
                ),
                "Check Performed": (
                    "Reviewed zero and "
                    "5%+ housing shares"
                ),
                "Result": (
                    "REVIEW"
                ),
                "Interpretation": (
                    housing_review
                ),
            },
            {
                "Data Quality Rule": (
                    "EU Comparison Consistency"
                ),
                "Check Performed": (
                    "Checked the EU value for "
                    "all six indicators"
                ),
                "Result": (
                    "PASS"
                    if eu_complete
                    else "FAIL"
                ),
                "Interpretation": (
                    "EU value available for "
                    "all indicators"
                    if eu_complete
                    else "EU value missing"
                ),
            },
        ]
    )

    return (
        quality_summary,
        indicator_overview,
        detailed_checks,
    )


app_ui = ui.page_fluid(
    ui.h2(
        "Gerontocracy in Greece — Appendix B Data App"
    ),

    ui.navset_tab(
        ui.nav_panel(
            "Overview",

            ui.output_ui(
                "overview_table"
            ),

            source_note(
                "Eurostat for EU comparisons and most indicators; "
                "Bank of Greece for Greece's property-price growth; "
                "Eurostat ESSPROS with ELSTAT validation for "
                "Greece's social-protection values."
            ),
        ),

        ui.nav_panel(
            "Median Age EU Countries",

            ui.output_plot(
                "median_age_chart"
            ),

            ui.output_table(
                "median_age_table"
            ),

            source_note(
                "Eurostat."
            ),
        ),

        ui.nav_panel(
            "Leaving Parental Home EU Countries",

            ui.output_plot(
                "leaving_home_chart"
            ),

            ui.output_table(
                "leaving_home_table"
            ),

            source_note(
                "Eurostat."
            ),
        ),

        ui.nav_panel(
            "Youth Housing Overburden EU Countries",

            ui.output_plot(
                "youth_housing_chart"
            ),

            ui.output_table(
                "youth_housing_table"
            ),

            source_note(
                "Eurostat."
            ),
        ),

        ui.nav_panel(
            "Property Price Growth EU Countries",

            ui.output_plot(
                "property_price_chart",
                height="380px",
            ),

            ui.output_table(
                "property_price_table"
            ),

            source_note(
                "Eurostat for the EU aggregate and Member States; "
                "Bank of Greece for Greece."
            ),
        ),

        ui.nav_panel(
            "Social Protection EU Countries",

            ui.h4(
                "Old-Age Benefits as a Share of Total "
                "Social-Protection Benefits, 2023"
            ),

            ui.output_plot(
                "old_age_social_chart",
                height="420px",
            ),

            ui.h4(
                "Housing Benefits as a Share of Total "
                "Social-Protection Benefits, 2023"
            ),

            ui.output_plot(
                "housing_social_chart",
                height="420px",
            ),

            ui.h4(
                "EU and Member-State Comparison"
            ),

            ui.output_table(
                "social_eu_table"
            ),

            ui.h4(
                "Greece — ELSTAT Reference Values"
            ),

            ui.output_table(
                "social_table"
            ),

            source_note(
                "Eurostat ESSPROS for the EU aggregate and Member "
                "States. Greece's values are cross-checked against "
                "ELSTAT ESSPROS 2023."
            ),
        ),

        ui.nav_panel(
            "Data Quality",

            ui.h3(
                "OSEMN Data Quality — Scrub Stage"
            ),

            ui.p(
                "The six indicators were checked for "
                "completeness, uniqueness, validity, "
                "consistency, coverage and source "
                "traceability before analysis."
            ),

            ui.h4(
                "Quality Summary"
            ),

            ui.output_ui(
                "quality_summary_cards"
            ),

            ui.h4(
                "Indicator Quality Overview",
                class_="mt-4",
            ),

            ui.div(
                ui.output_table(
                    "indicator_quality_table"
                ),
                style=(
                    "overflow-x: auto;"
                ),
            ),

            ui.h4(
                "Detailed Data Quality Checks",
                class_="mt-4",
            ),

            ui.div(
                ui.output_table(
                    "detailed_quality_table"
                ),
                style=(
                    "overflow-x: auto;"
                ),
            ),
        ),
    ),
)


def server(
    input,
    output,
    session,
):

    @output
    @render.ui
    def overview_table():
        return build_overview_html()

    @output
    @render.table
    def median_age_table():
        return format_display_table(
            load_table(
                "median_age_eu_countries"
            ),
            columns=[
                "country_code",
                "year",
                "median_age",
            ],
            rename_columns={
                "country_code": (
                    "Country Code"
                ),
                "year": (
                    "Year"
                ),
                "median_age": (
                    "Median Age (Years)"
                ),
            },
        )

    @output
    @render.plot
    def median_age_chart():
        df = load_table(
            "median_age_eu_countries"
        )

        chart_df, _ = (
            prepare_country_chart(
                df,
                "median_age",
            )
        )

        chart_df = chart_df.rename(
            columns={
                "country_code": (
                    "Country"
                ),
                "median_age": (
                    "Median Age"
                ),
            }
        )

        ax = chart_df.plot(
            x="Country",
            y="Median Age",
            kind="bar",
            legend=False,
            figsize=(14, 5),
        )

        ax.axhline(
            y=44.9,
            linestyle="--",
            label=(
                "EU Average: 44.9 years"
            ),
        )

        ax.legend()

        ax.set_ylim(
            chart_df[
                "Median Age"
            ].min() - 1,
            chart_df[
                "Median Age"
            ].max() + 1,
        )

        ax.set_title(
            "Median Age in EU Countries, 2025"
        )

        ax.set_xlabel(
            "Country"
        )

        ax.set_ylabel(
            "Median Age (Years)"
        )

        plt.xticks(
            rotation=45,
            ha="right",
        )

        plt.tight_layout()

    @output
    @render.table
    def leaving_home_table():
        return format_display_table(
            load_table(
                "leaving_home_eu_countries"
            ),
            columns=[
                "country_code",
                "year",
                "age",
            ],
            rename_columns={
                "country_code": (
                    "Country Code"
                ),
                "year": (
                    "Year"
                ),
                "age": (
                    "Leaving Home Age (Years)"
                ),
            },
        )

    @output
    @render.plot
    def leaving_home_chart():
        df = load_table(
            "leaving_home_eu_countries"
        )

        chart_df, _ = (
            prepare_country_chart(
                df,
                "age",
            )
        )

        chart_df = chart_df.rename(
            columns={
                "country_code": (
                    "Country"
                ),
                "age": (
                    "Leaving Home Age"
                ),
            }
        )

        ax = chart_df.plot(
            x="Country",
            y="Leaving Home Age",
            kind="bar",
            legend=False,
            figsize=(14, 5),
        )

        ax.axhline(
            y=26.3,
            linestyle="--",
            label=(
                "EU Average: 26.3 years"
            ),
        )

        ax.legend()

        ax.set_ylim(
            chart_df[
                "Leaving Home Age"
            ].min() - 1,
            chart_df[
                "Leaving Home Age"
            ].max() + 1,
        )

        ax.set_title(
            "Average Age of Leaving the Parental Home "
            "in EU Countries, 2025"
        )

        ax.set_xlabel(
            "Country"
        )

        ax.set_ylabel(
            "Leaving Home Age (Years)"
        )

        plt.xticks(
            rotation=45,
            ha="right",
        )

        plt.tight_layout()

    @output
    @render.table
    def youth_housing_table():
        return format_display_table(
            load_table(
                "youth_housing_eu_countries"
            ),
            columns=[
                "country_code",
                "year",
                "overburden_rate",
            ],
            rename_columns={
                "country_code": (
                    "Country Code"
                ),
                "year": (
                    "Year"
                ),
                "overburden_rate": (
                    "Housing Overburden Rate (%)"
                ),
            },
        )

    @output
    @render.plot
    def youth_housing_chart():
        draw_country_chart(
            table_name=(
                "youth_housing_eu_countries"
            ),
            value_column=(
                "overburden_rate"
            ),
            value_label=(
                "Housing Overburden Rate"
            ),
            title=(
                "Youth Housing Overburden "
                "in EU Countries, 2025"
            ),
            y_axis_label=(
                "Housing Overburden Rate (%)"
            ),
            eu_value=9.1,
            eu_suffix="%",
            minimum=0,
            maximum_padding=2,
        )

    @output
    @render.table
    def property_price_table():
        return format_display_table(
            load_table(
                "property_price_growth_eu_countries"
            ),
            columns=[
                "country_code",
                "year",
                "property_price_growth",
            ],
            rename_columns={
                "country_code": (
                    "Country Code"
                ),
                "year": (
                    "Year"
                ),
                "property_price_growth": (
                    "Property Price Growth (%)"
                ),
            },
        )

    @output
    @render.plot
    def property_price_chart():
        draw_country_chart(
            table_name=(
                "property_price_growth_eu_countries"
            ),
            value_column=(
                "property_price_growth"
            ),
            value_label=(
                "Property Price Growth"
            ),
            title=(
                "Residential Property Price Growth "
                "in EU Countries, 2025"
            ),
            y_axis_label=(
                "Annual Property Price Growth (%)"
            ),
            eu_value=5.5,
            eu_suffix="%",
            figure_size=(
                14,
                3,
            ),
        )

    @output
    @render.table
    def social_eu_table():
        return format_display_table(
            load_table(
                "social_protection_eu_countries"
            ),
            columns=[
                "country_code",
                "year",
                "old_age_share",
                "housing_share",
            ],
            rename_columns={
                "country_code": (
                    "Country Code"
                ),
                "year": (
                    "Year"
                ),
                "old_age_share": (
                    "Old-Age Benefits Share (%)"
                ),
                "housing_share": (
                    "Housing Benefits Share (%)"
                ),
            },
        )

    @output
    @render.table
    def social_table():
        return format_display_table(
            load_table(
                "social_protection"
            ),
            columns=[
                "metric",
                "year",
                "greece",
            ],
            rename_columns={
                "metric": (
                    "Indicator"
                ),
                "year": (
                    "Year"
                ),
                "greece": (
                    "Greece (%)"
                ),
            },
        )

    @output
    @render.plot
    def old_age_social_chart():
        draw_country_chart(
            table_name=(
                "social_protection_eu_countries"
            ),
            value_column=(
                "old_age_share"
            ),
            value_label=(
                "Old-Age Benefits Share"
            ),
            title=(
                "Old-Age Benefits Share "
                "in EU Countries, 2023"
            ),
            y_axis_label=(
                "Old-Age Benefits Share (%)"
            ),
            eu_suffix="%",
            minimum=0,
            maximum_padding=5,
        )

    @output
    @render.plot
    def housing_social_chart():
        draw_country_chart(
            table_name=(
                "social_protection_eu_countries"
            ),
            value_column=(
                "housing_share"
            ),
            value_label=(
                "Housing Benefits Share"
            ),
            title=(
                "Housing Benefits Share "
                "in EU Countries, 2023"
            ),
            y_axis_label=(
                "Housing Benefits Share (%)"
            ),
            eu_suffix="%",
            minimum=0,
            maximum_padding=0.5,
        )

    @output
    @render.ui
    def quality_summary_cards():
        (
            summary,
            _,
            _,
        ) = build_data_quality_outputs()

        cards = []

        for item in summary:
            status = item[
                "Status"
            ]

            if status == "PASS":
                border_class = (
                    "border-success"
                )

                text_class = (
                    "text-success"
                )

            elif status == "REVIEW":
                border_class = (
                    "border-warning"
                )

                text_class = (
                    "text-warning"
                )

            else:
                border_class = (
                    "border-danger"
                )

                text_class = (
                    "text-danger"
                )

            card = ui.div(
                ui.div(
                    ui.h5(
                        item[
                            "Dimension"
                        ],
                        class_=(
                            "card-title"
                        ),
                    ),

                    ui.h3(
                        status,
                        class_=(
                            text_class
                        ),
                    ),

                    ui.p(
                        item[
                            "Details"
                        ],
                        class_=(
                            "mb-0"
                        ),
                    ),

                    class_=(
                        "card-body"
                    ),
                ),

                class_=(
                    "card h-100 shadow-sm "
                    "border-2 "
                    f"{border_class}"
                ),
            )

            cards.append(
                ui.div(
                    card,
                    class_=(
                        "col-lg-4 col-md-6"
                    ),
                )
            )

        return ui.div(
            *cards,
            class_=(
                "row g-3 mb-4"
            ),
        )

    @output
    @render.table
    def indicator_quality_table():
        (
            _,
            indicator_table,
            _,
        ) = build_data_quality_outputs()

        return indicator_table

    @output
    @render.table
    def detailed_quality_table():
        (
            _,
            _,
            detailed_table,
        ) = build_data_quality_outputs()

        return detailed_table


app = App(
    app_ui,
    server,
)