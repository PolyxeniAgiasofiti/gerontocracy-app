import os

import psycopg2
from psycopg2.extras import RealDictCursor


OBSERVATORY_DATABASE_URL = os.getenv(
    "OBSERVATORY_DATABASE_URL"
)


def get_observatory_connection():
    """
    Connect to the persistent PostgreSQL database used
    by the Data Observatory.
    """

    if not OBSERVATORY_DATABASE_URL:
        raise RuntimeError(
            "OBSERVATORY_DATABASE_URL is not configured."
        )

    return psycopg2.connect(
        OBSERVATORY_DATABASE_URL
    )


def initialize_observatory_database():
    """
    Create the core Data Observatory tables.

    Existing tables and records are preserved.
    """

    if not OBSERVATORY_DATABASE_URL:
        print(
            "Observatory PostgreSQL database not configured "
            "in this environment. Skipping initialization."
        )
        return False

    with get_observatory_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS observatory_topics (
                    topic_id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    geography TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    repository_id BIGSERIAL PRIMARY KEY,
                    topic_id BIGINT NOT NULL,
                    provider TEXT NOT NULL,
                    repository_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT,
                    dimension TEXT,
                    geography TEXT,
                    data_format TEXT,
                    refresh_frequency TEXT,
                    status TEXT NOT NULL DEFAULT 'CANDIDATE',
                    relevance_score NUMERIC(5, 2),
                    date_added TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    last_checked TIMESTAMPTZ,
                    CONSTRAINT fk_repository_topic
                        FOREIGN KEY (topic_id)
                        REFERENCES observatory_topics(topic_id)
                        ON DELETE CASCADE,
                    CONSTRAINT uq_topic_repository_url
                        UNIQUE (topic_id, url)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS repository_runs (
                    run_id BIGSERIAL PRIMARY KEY,
                    repository_id BIGINT NOT NULL,
                    execution_date TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    changed BOOLEAN,
                    rows_received BIGINT,
                    content_hash TEXT,
                    raw_snapshot_location TEXT,
                    notes TEXT,
                    CONSTRAINT fk_run_repository
                        FOREIGN KEY (repository_id)
                        REFERENCES repositories(repository_id)
                        ON DELETE CASCADE
                );
                """
            )

        conn.commit()

    print(
        "Data Observatory PostgreSQL tables are ready."
    )

    return True


def load_observatory_table(table_name):
    """
    Read one approved Observatory table into a list
    of dictionaries.
    """

    allowed_tables = {
        "observatory_topics",
        "repositories",
        "repository_runs",
    }

    if table_name not in allowed_tables:
        raise ValueError(
            f"Unsupported Observatory table: {table_name}"
        )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                f"""
                SELECT *
                FROM {table_name}
                ORDER BY 1;
                """
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def get_or_create_topic(
    name,
    description=None,
    geography=None,
):
    """
    Return an existing Observatory topic or create it.

    This avoids creating duplicate topics every time
    the application is restarted.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM observatory_topics
                WHERE LOWER(name) = LOWER(%s)
                ORDER BY topic_id
                LIMIT 1;
                """,
                (name,),
            )

            existing_topic = cursor.fetchone()

            if existing_topic:
                return dict(existing_topic)

            cursor.execute(
                """
                INSERT INTO observatory_topics (
                    name,
                    description,
                    geography
                )
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (
                    name,
                    description,
                    geography,
                ),
            )

            new_topic = cursor.fetchone()

        conn.commit()

    return dict(new_topic)


def initialize_default_topic():
    """
    Create the default Gerontocracy topic when the
    Observatory PostgreSQL database is available.
    """

    if not OBSERVATORY_DATABASE_URL:
        print(
            "Observatory topic initialization skipped: "
            "PostgreSQL is not configured locally."
        )
        return None

    topic = get_or_create_topic(
        name="Gerontocracy in Greece",
        description=(
            "Study of the concentration of demographic, "
            "political, economic and social resources "
            "across generations, with focus on Greece "
            "and comparison with the European Union."
        ),
        geography="Greece + European Union",
    )

    print(
        f"Observatory topic ready: "
        f"{topic['topic_id']} - {topic['name']}"
    )

    return topic
