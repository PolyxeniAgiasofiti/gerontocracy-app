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

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_requests (
                    request_id BIGSERIAL PRIMARY KEY,
                    topic_id BIGINT NOT NULL,
                    prompt TEXT NOT NULL,
                    execution_date TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'RUNNING',
                    candidates_found INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    CONSTRAINT fk_discovery_topic
                        FOREIGN KEY (topic_id)
                        REFERENCES observatory_topics(topic_id)
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
        "discovery_requests",
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


def create_discovery_request(topic_id, prompt):
    """
    Save one repository-discovery execution.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO discovery_requests (
                    topic_id,
                    prompt
                )
                VALUES (%s, %s)
                RETURNING *;
                """,
                (topic_id, prompt),
            )
            row = cursor.fetchone()
        conn.commit()

    return dict(row)


def complete_discovery_request(
    request_id,
    candidates_found,
    status="SUCCESS",
    notes=None,
):
    """
    Mark a discovery execution as completed.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE discovery_requests
                SET status = %s,
                    candidates_found = %s,
                    notes = %s
                WHERE request_id = %s
                RETURNING *;
                """,
                (
                    status,
                    candidates_found,
                    notes,
                    request_id,
                ),
            )
            row = cursor.fetchone()
        conn.commit()

    return dict(row) if row else None


def upsert_repository(
    topic_id,
    provider,
    repository_name,
    url,
    description=None,
    dimension=None,
    geography=None,
    data_format=None,
    refresh_frequency=None,
    status="CANDIDATE",
    relevance_score=None,
):
    """
    Insert a new repository or refresh its metadata.

    The original date_added is preserved. Re-discovered
    repositories are not duplicated; last_checked is updated.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO repositories (
                    topic_id,
                    provider,
                    repository_name,
                    url,
                    description,
                    dimension,
                    geography,
                    data_format,
                    refresh_frequency,
                    status,
                    relevance_score,
                    last_checked
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (topic_id, url)
                DO UPDATE SET
                    provider = EXCLUDED.provider,
                    repository_name = EXCLUDED.repository_name,
                    description = EXCLUDED.description,
                    dimension = EXCLUDED.dimension,
                    geography = EXCLUDED.geography,
                    data_format = EXCLUDED.data_format,
                    refresh_frequency = EXCLUDED.refresh_frequency,
                    relevance_score = EXCLUDED.relevance_score,
                    last_checked = CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    topic_id,
                    provider,
                    repository_name,
                    url,
                    description,
                    dimension,
                    geography,
                    data_format,
                    refresh_frequency,
                    status,
                    relevance_score,
                ),
            )
            row = cursor.fetchone()
        conn.commit()

    return dict(row)


def load_repository_registry(topic_id=None):
    """
    Read the repository registry, optionally for one topic.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            if topic_id is None:
                cursor.execute(
                    """
                    SELECT *
                    FROM repositories
                    ORDER BY repository_id;
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM repositories
                    WHERE topic_id = %s
                    ORDER BY repository_id;
                    """,
                    (topic_id,),
                )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]
