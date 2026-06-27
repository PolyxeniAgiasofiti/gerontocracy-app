from pathlib import Path

from shiny import App, ui, render
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from shiny.express import output

from src.load import create_tables, save_dataframe
from src.extract import get_all_indicators
from src.quality_checks import run_quality_checks
from src.extract import (
    get_all_indicators,
    get_eurostat_demographics_dataset,
    get_housing_market_dataset,
    get_social_protection_dataset
)

DB_PATH = "database/gerontocracy.db"


def initialize_database_if_needed():
    create_tables()

    df = get_all_indicators()
    save_dataframe(df, "indicators")

    eurostat_df = get_eurostat_demographics_dataset()
    save_dataframe(eurostat_df, "eurostat_demographics")

    housing_df = get_housing_market_dataset()
    save_dataframe(housing_df, "housing_market")

    social_df = get_social_protection_dataset()
    save_dataframe(social_df, "social_protection")

    run_quality_checks()


initialize_database_if_needed()


def load_indicators():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM indicators", conn)
    conn.close()
    return df


def load_housing_market():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM housing_market", conn)
    conn.close()
    return df
def load_social_protection():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM social_protection", conn)
    conn.close()
    return df

def load_quality():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM quality_results", conn)
    conn.close()
    return df


def load_eurostat_demographics():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM eurostat_demographics", conn)
    conn.close()
    return df


app_ui = ui.page_fluid(
    ui.h2("Gerontocracy in Greece — Appendix B Data App"),

    ui.navset_tab(
        ui.nav_panel(
    "Overview",
    ui.output_table("indicator_table")
),
        ui.nav_panel(
            "Eurostat Demographics",
            ui.output_table("eurostat_table"),
            ui.output_plot("eurostat_chart")
        ),
        ui.nav_panel(
            "Housing Market",
            ui.output_table("housing_table")
        ),
        ui.nav_panel(
            "Data Quality",
            ui.output_table("quality_table")
        ),
        ui.nav_panel(
    "Social Protection",
    ui.output_table("social_table"),
    ui.output_plot("social_chart")
),
    )
)


def server(input, output, session):

    @output
    @render.table
    def indicator_table():
        return load_indicators()


    @output
    @render.table
    def eurostat_table():
        return load_eurostat_demographics()

    @output
    @render.plot
    def eurostat_chart():
        df = load_eurostat_demographics()

        df.plot(
            x="metric",
            y=["greece", "eu"],
            kind="bar"
        )

        plt.title("Eurostat Demographics — Greece vs EU")
        plt.ylabel("Value")
        plt.xlabel("Metric")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

@output
@render.table
def housing_table():
    return load_housing_market()

@output
@render.table
def social_table():
    return load_social_protection()

@output
@render.plot
def social_chart():
    df = load_social_protection()

    df.plot(
        x="metric",
        y="greece",
        kind="bar",
        legend=False
    )

    plt.title("Greece Social Protection Allocation")
    plt.ylabel("Percentage (%)")
    plt.xlabel("Metric")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

@output
@render.table
def quality_table():
    return load_quality()


app = App(app_ui, server)