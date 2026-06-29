from shiny import App, ui, render
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt

from src.load import create_tables, save_dataframe
from src.quality_checks import run_quality_checks
from src.extract import (
    get_all_indicators,
    get_eurostat_demographics_dataset,
    get_housing_market_dataset,
    get_social_protection_dataset,
)

DB_PATH = "database/gerontocracy.db"


def initialize_database_if_needed():
    create_tables()
    save_dataframe(get_all_indicators(), "indicators")
    save_dataframe(get_eurostat_demographics_dataset(), "eurostat_demographics")
    save_dataframe(get_housing_market_dataset(), "housing_market")
    save_dataframe(get_social_protection_dataset(), "social_protection")
    run_quality_checks()


initialize_database_if_needed()


def load_table(table_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df


app_ui = ui.page_fluid(
    ui.h2("Gerontocracy in Greece — Appendix B Data App"),
    ui.navset_tab(
        ui.nav_panel(
            "Overview",
            ui.output_table("indicator_table"),
        ),
        ui.nav_panel(
            "Eurostat Demographics",
            ui.output_table("eurostat_table"),
            ui.output_plot("eurostat_chart"),
        ),
        ui.nav_panel(
            "Housing Market",
            ui.output_table("housing_table"),
            ui.output_plot("housing_chart"),
        ),
        ui.nav_panel(
            "Social Protection",
            ui.output_table("social_table"),
            ui.output_plot("social_chart"),
        ),
        ui.nav_panel(
            "Data Quality",
            ui.output_table("quality_table"),
        ),
    ),
)


def server(input, output, session):

    @output
    @render.table
    def indicator_table():
        return load_table("indicators")

    @output
    @render.table
    def eurostat_table():
        return load_table("eurostat_demographics")

    @output
    @render.plot
    def eurostat_chart():
        df = load_table("eurostat_demographics")
        df.plot(x="metric", y=["greece", "eu"], kind="bar")
        plt.title("Eurostat Demographics — Greece vs EU")
        plt.ylabel("Value")
        plt.xlabel("Metric")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

    @output
    @render.table
    def housing_table():
        return load_table("housing_market")

    @output
    @render.plot
    def housing_chart():
        df = load_table("housing_market")
        df.plot(x="metric", y="greece", kind="bar", legend=False)
        plt.title("Greece Housing Market")
        plt.ylabel("Percentage (%)")
        plt.xlabel("Metric")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()

    @output
    @render.table
    def social_table():
        return load_table("social_protection")

    @output
    @render.plot
    def social_chart():
        df = load_table("social_protection")
        df.plot(x="metric", y="greece", kind="bar", legend=False)
        plt.title("Greece Social Protection Allocation")
        plt.ylabel("Percentage (%)")
        plt.xlabel("Metric")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()

    @output
    @render.table
    def quality_table():
        return load_table("quality_results")


app = App(app_ui, server)