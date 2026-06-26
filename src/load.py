import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("database/gerontocracy.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS eurostat_demographics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT,
        year TEXT,
        greece REAL,
        eu REAL,
        unit TEXT,
        source_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS housing_market (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT,
        year TEXT,
        greece REAL,
        eu REAL,
        unit TEXT,
        source_name TEXT,
        notes TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS social_protection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT,
        year TEXT,
        greece REAL,
        eu REAL,
        unit TEXT,
        source_name TEXT,
        notes TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_name TEXT,
        country TEXT,
        comparator TEXT,
        year TEXT,
        value REAL,
        unit TEXT,
        source_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quality_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT,
        check_name TEXT,
        status TEXT,
        details TEXT
    )
    """)

    conn.commit()
    conn.close()

def save_dataframe(df, table_name):
    conn = get_connection()
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()