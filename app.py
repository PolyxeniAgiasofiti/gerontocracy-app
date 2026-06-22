from pathlib import Path
from src.load import create_tables, save_dataframe
from src.extract import get_all_indicators
from src.quality_checks import run_quality_checks



from shiny import App, ui, render
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt

DB_PATH = "database/gerontocracy.db"


def load_indicators():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM indicators", conn)
    conn.close()
    return df


def load_quality():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM quality_results", conn)
    conn.close()
    return df


app_ui = ui.page_fluid(
    ui.h2("Gerontocracy in Greece — Appendix B Data App"),

    ui.navset_tab(
        ui.nav_panel(
            "Overview",
            ui.output_table("indicator_table"),
            ui.output_plot("indicator_chart")
        ),
        ui.nav_panel(
            "Data Quality",
            ui.output_table("quality_table")
        )
    )
)


def server(input, output, session):

    @output
    @render.table
    def indicator_table():
        return load_indicators()

    @output
    @render.plot
    def indicator_chart():
        df = load_indicators()

        pivot = df.pivot_table(
            index="indicator_name",
            columns="country",
            values="value",
            aggfunc="first"
        )

        pivot.plot(kind="bar")
        plt.title("Greece vs EU Gerontocracy Indicators")
        plt.ylabel("Value")
        plt.xlabel("Indicator")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

    @output
    @render.table
    def quality_table():
        return load_quality()


app = App(app_ui, server)