import hashlib
import json
import os
import urllib.parse

import psycopg2
from psycopg2.extras import Json, RealDictCursor


OBSERVATORY_DATABASE_URL = os.getenv(
    "OBSERVATORY_DATABASE_URL"
)


def get_observatory_connection():
    if not OBSERVATORY_DATABASE_URL:
        raise RuntimeError(
            "OBSERVATORY_DATABASE_URL is not configured."
        )

    return psycopg2.connect(
        OBSERVATORY_DATABASE_URL
    )


def _canonicalize_url(url):
    url = (url or "").strip()

    if not url:
        return ""

    parsed = urllib.parse.urlsplit(url)

    query_pairs = urllib.parse.parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )

    filtered_query = [
        (key, value)
        for key, value in query_pairs
        if not key.lower().startswith(
            ("utm_", "fbclid", "gclid")
        )
    ]

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urllib.parse.urlencode(
                filtered_query
            ),
            "",
        )
    )


def _normalise_text(value):
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .split()
    )


def _repository_metadata_hash(item):
    """
    Fingerprint stable repository metadata.

    Description and relevance score are deliberately excluded because an LLM
    can paraphrase them between runs without the repository actually changing.
    """

    stable = {
        "provider": _normalise_text(
            item.get("provider")
        ),
        "repository_name": _normalise_text(
            item.get("repository_name")
        ),
        "url": _canonicalize_url(
            item.get("url")
        ),
        "dimension": _normalise_text(
            item.get("dimension")
        ),
        "geography": _normalise_text(
            item.get("geography")
        ),
        "data_format": _normalise_text(
            item.get("data_format")
        ),
        "refresh_frequency": _normalise_text(
            item.get("refresh_frequency")
        ),
    }

    raw = json.dumps(
        stable,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def _source_version_marker(availability):
    """
    Use server-provided version headers when available.

    We do not hash dynamic HTML bodies.
    """

    if not availability:
        return None

    etag = availability.get("etag")
    last_modified = availability.get(
        "last_modified"
    )

    if not etag and not last_modified:
        return None

    raw = (
        str(etag or "")
        + "|"
        + str(last_modified or "")
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def initialize_observatory_database():
    """
    Create/migrate all Data Observatory tables without deleting existing data.
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

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS concept_analyses (
                    analysis_id BIGSERIAL PRIMARY KEY,
                    topic_id BIGINT NOT NULL,
                    definition TEXT NOT NULL,
                    factors_json JSONB NOT NULL,
                    data_dimensions_json JSONB NOT NULL,
                    model TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_analysis_topic
                        FOREIGN KEY (topic_id)
                        REFERENCES observatory_topics(topic_id)
                        ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS expert_suggestions (
                    suggestion_id BIGSERIAL PRIMARY KEY,
                    topic_id BIGINT NOT NULL,
                    suggestion_text TEXT NOT NULL,
                    normalized_factor TEXT,
                    status TEXT NOT NULL,
                    reason TEXT,
                    model TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_suggestion_topic
                        FOREIGN KEY (topic_id)
                        REFERENCES observatory_topics(topic_id)
                        ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_results (
                    result_id BIGSERIAL PRIMARY KEY,
                    request_id BIGINT NOT NULL,
                    repository_id BIGINT NOT NULL,
                    result_state TEXT NOT NULL,
                    previous_status TEXT,
                    metadata_hash TEXT,
                    discovered_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_result_request
                        FOREIGN KEY (request_id)
                        REFERENCES discovery_requests(request_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_result_repository
                        FOREIGN KEY (repository_id)
                        REFERENCES repositories(repository_id)
                        ON DELETE CASCADE
                );
                """
            )

            # Existing-table migrations.
            repository_columns = [
                (
                    "reviewed_at",
                    "TIMESTAMPTZ",
                ),
                (
                    "canonical_url",
                    "TEXT",
                ),
                (
                    "metadata_hash",
                    "TEXT",
                ),
                (
                    "source_version_marker",
                    "TEXT",
                ),
                (
                    "change_state",
                    "TEXT",
                ),
                (
                    "needs_review",
                    "BOOLEAN",
                ),
                (
                    "previous_status",
                    "TEXT",
                ),
                (
                    "first_discovered_at",
                    "TIMESTAMPTZ",
                ),
                (
                    "last_discovered_at",
                    "TIMESTAMPTZ",
                ),
                (
                    "last_discovery_request_id",
                    "BIGINT",
                ),
                (
                    "availability_status",
                    "TEXT",
                ),
                (
                    "last_http_status",
                    "INTEGER",
                ),
            ]

            for column_name, sql_type in repository_columns:
                cursor.execute(
                    "ALTER TABLE repositories "
                    "ADD COLUMN IF NOT EXISTS "
                    + column_name
                    + " "
                    + sql_type
                    + ";"
                )

            run_columns = [
                ("http_status", "INTEGER"),
                ("content_type", "TEXT"),
                ("last_modified", "TEXT"),
                ("etag", "TEXT"),
            ]

            for column_name, sql_type in run_columns:
                cursor.execute(
                    "ALTER TABLE repository_runs "
                    "ADD COLUMN IF NOT EXISTS "
                    + column_name
                    + " "
                    + sql_type
                    + ";"
                )

            discovery_columns = [
                ("search_context", "TEXT"),
                ("model", "TEXT"),
                (
                    "run_type",
                    "TEXT DEFAULT 'MANUAL'",
                ),
                (
                    "new_count",
                    "INTEGER DEFAULT 0",
                ),
                (
                    "updated_count",
                    "INTEGER DEFAULT 0",
                ),
                (
                    "unchanged_count",
                    "INTEGER DEFAULT 0",
                ),
            ]

            for column_name, sql_type in discovery_columns:
                cursor.execute(
                    "ALTER TABLE discovery_requests "
                    "ADD COLUMN IF NOT EXISTS "
                    + column_name
                    + " "
                    + sql_type
                    + ";"
                )

            # Safely initialise newly added columns for the old 8 repositories.
            cursor.execute(
                """
                UPDATE repositories
                SET canonical_url = url
                WHERE canonical_url IS NULL;
                """
            )

            cursor.execute(
                """
                UPDATE repositories
                SET first_discovered_at = date_added
                WHERE first_discovered_at IS NULL;
                """
            )

            cursor.execute(
                """
                UPDATE repositories
                SET last_discovered_at = COALESCE(
                    last_checked,
                    date_added
                )
                WHERE last_discovered_at IS NULL;
                """
            )

            cursor.execute(
                """
                UPDATE repositories
                SET needs_review =
                    CASE
                        WHEN status = 'CANDIDATE'
                            THEN TRUE
                        ELSE FALSE
                    END
                WHERE needs_review IS NULL;
                """
            )

            cursor.execute(
                """
                UPDATE repositories
                SET change_state =
                    CASE
                        WHEN status = 'CANDIDATE'
                            THEN 'NEW'
                        ELSE 'UNCHANGED'
                    END
                WHERE change_state IS NULL;
                """
            )

        conn.commit()

    print(
        "Data Observatory PostgreSQL tables are ready."
    )

    return True


def load_observatory_table(table_name):
    allowed_tables = {
        "observatory_topics",
        "repositories",
        "repository_runs",
        "discovery_requests",
        "concept_analyses",
        "expert_suggestions",
        "discovery_results",
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
            existing = cursor.fetchone()

            if existing:
                return dict(existing)

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
            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def initialize_default_topic():
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


def save_concept_analysis(
    topic_id,
    definition,
    factors,
    data_dimensions,
    model=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO concept_analyses (
                    topic_id,
                    definition,
                    factors_json,
                    data_dimensions_json,
                    model
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    topic_id,
                    definition,
                    Json(factors),
                    Json(data_dimensions),
                    model,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def get_latest_concept_analysis(topic_id):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM concept_analyses
                WHERE topic_id = %s
                ORDER BY created_at DESC, analysis_id DESC
                LIMIT 1;
                """,
                (topic_id,),
            )
            row = cursor.fetchone()

    return dict(row) if row else None


def save_expert_suggestion(
    topic_id,
    suggestion_text,
    normalized_factor,
    status,
    reason,
    model=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO expert_suggestions (
                    topic_id,
                    suggestion_text,
                    normalized_factor,
                    status,
                    reason,
                    model
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    topic_id,
                    suggestion_text,
                    normalized_factor,
                    status,
                    reason,
                    model,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def load_expert_suggestions(
    topic_id,
    accepted_only=False,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            if accepted_only:
                cursor.execute(
                    """
                    SELECT *
                    FROM expert_suggestions
                    WHERE topic_id = %s
                      AND status = 'ACCEPTED'
                    ORDER BY suggestion_id;
                    """,
                    (topic_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM expert_suggestions
                    WHERE topic_id = %s
                    ORDER BY suggestion_id;
                    """,
                    (topic_id,),
                )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def create_discovery_request(
    topic_id,
    prompt,
    search_context=None,
    model=None,
    run_type="MANUAL",
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO discovery_requests (
                    topic_id,
                    prompt,
                    search_context,
                    model,
                    run_type
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    topic_id,
                    prompt,
                    search_context,
                    model,
                    run_type,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def complete_discovery_request(
    request_id,
    candidates_found,
    status="SUCCESS",
    notes=None,
    new_count=0,
    updated_count=0,
    unchanged_count=0,
    model=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE discovery_requests
                SET status = %s,
                    candidates_found = %s,
                    notes = %s,
                    new_count = %s,
                    updated_count = %s,
                    unchanged_count = %s,
                    model = COALESCE(%s, model)
                WHERE request_id = %s
                RETURNING *;
                """,
                (
                    status,
                    candidates_found,
                    notes,
                    new_count,
                    updated_count,
                    unchanged_count,
                    model,
                    request_id,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row) if row else None


def load_discovery_history(
    topic_id,
    limit=25,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM discovery_requests
                WHERE topic_id = %s
                ORDER BY execution_date DESC, request_id DESC
                LIMIT %s;
                """,
                (
                    topic_id,
                    limit,
                ),
            )
            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def load_repository_registry(topic_id=None):
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


def get_repository(repository_id):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM repositories
                WHERE repository_id = %s;
                """,
                (repository_id,),
            )
            row = cursor.fetchone()

    return dict(row) if row else None


def _find_existing_repository(
    cursor,
    topic_id,
    canonical_url,
):
    cursor.execute(
        """
        SELECT *
        FROM repositories
        WHERE topic_id = %s
        ORDER BY repository_id;
        """,
        (topic_id,),
    )

    for row in cursor.fetchall():
        row_dict = dict(row)
        stored = (
            row_dict.get("canonical_url")
            or row_dict.get("url")
        )

        if (
            _canonicalize_url(stored)
            == canonical_url
        ):
            return row_dict

    return None


def compare_and_store_repository_candidate(
    topic_id,
    request_id,
    candidate,
    availability=None,
):
    """
    Compare one freshly discovered repository with the persistent registry.

    Returns (repository, result_state), where state is NEW, UPDATED or
    UNCHANGED.
    """

    canonical_url = _canonicalize_url(
        candidate.get("url")
    )

    if not canonical_url:
        raise ValueError(
            "Repository candidate has no valid HTTP(S) URL."
        )

    candidate = dict(candidate)
    candidate["url"] = canonical_url

    candidate_hash = _repository_metadata_hash(
        candidate
    )

    new_version_marker = _source_version_marker(
        availability
    )

    availability_status = None
    last_http_status = None

    if availability:
        availability_status = availability.get(
            "status"
        )
        last_http_status = availability.get(
            "http_status"
        )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            existing = _find_existing_repository(
                cursor,
                topic_id,
                canonical_url,
            )

            if existing is None:
                cursor.execute(
                    """
                    INSERT INTO repositories (
                        topic_id,
                        provider,
                        repository_name,
                        url,
                        canonical_url,
                        description,
                        dimension,
                        geography,
                        data_format,
                        refresh_frequency,
                        status,
                        relevance_score,
                        last_checked,
                        reviewed_at,
                        metadata_hash,
                        source_version_marker,
                        change_state,
                        needs_review,
                        previous_status,
                        first_discovered_at,
                        last_discovered_at,
                        last_discovery_request_id,
                        availability_status,
                        last_http_status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        'CANDIDATE', %s,
                        CURRENT_TIMESTAMP,
                        NULL,
                        %s, %s,
                        'NEW', TRUE, NULL,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP,
                        %s, %s, %s
                    )
                    RETURNING *;
                    """,
                    (
                        topic_id,
                        candidate.get("provider"),
                        candidate.get(
                            "repository_name"
                        ),
                        canonical_url,
                        canonical_url,
                        candidate.get(
                            "description"
                        ),
                        candidate.get(
                            "dimension"
                        ),
                        candidate.get(
                            "geography"
                        ),
                        candidate.get(
                            "data_format"
                        ),
                        candidate.get(
                            "refresh_frequency"
                        ),
                        candidate.get(
                            "relevance_score"
                        ),
                        candidate_hash,
                        new_version_marker,
                        request_id,
                        availability_status,
                        last_http_status,
                    ),
                )
                row = cursor.fetchone()
                result_state = "NEW"
                previous_status = None

            else:
                old_hash = (
                    existing.get("metadata_hash")
                    or _repository_metadata_hash(
                        existing
                    )
                )

                old_version_marker = (
                    existing.get(
                        "source_version_marker"
                    )
                )

                metadata_changed = (
                    old_hash != candidate_hash
                )

                version_changed = (
                    old_version_marker is not None
                    and new_version_marker is not None
                    and old_version_marker
                    != new_version_marker
                )

                meaningful_change = (
                    metadata_changed
                    or version_changed
                )

                if meaningful_change:
                    previous_status = existing.get(
                        "status"
                    )

                    cursor.execute(
                        """
                        UPDATE repositories
                        SET provider = %s,
                            repository_name = %s,
                            url = %s,
                            canonical_url = %s,
                            description = %s,
                            dimension = %s,
                            geography = %s,
                            data_format = %s,
                            refresh_frequency = %s,
                            relevance_score = %s,
                            status = 'CANDIDATE',
                            previous_status = %s,
                            needs_review = TRUE,
                            change_state = 'UPDATED',
                            metadata_hash = %s,
                            source_version_marker = COALESCE(
                                %s,
                                source_version_marker
                            ),
                            last_discovered_at = CURRENT_TIMESTAMP,
                            last_discovery_request_id = %s,
                            last_checked = CURRENT_TIMESTAMP,
                            availability_status = %s,
                            last_http_status = %s
                        WHERE repository_id = %s
                        RETURNING *;
                        """,
                        (
                            candidate.get(
                                "provider"
                            ),
                            candidate.get(
                                "repository_name"
                            ),
                            canonical_url,
                            canonical_url,
                            candidate.get(
                                "description"
                            ),
                            candidate.get(
                                "dimension"
                            ),
                            candidate.get(
                                "geography"
                            ),
                            candidate.get(
                                "data_format"
                            ),
                            candidate.get(
                                "refresh_frequency"
                            ),
                            candidate.get(
                                "relevance_score"
                            ),
                            previous_status,
                            candidate_hash,
                            new_version_marker,
                            request_id,
                            availability_status,
                            last_http_status,
                            existing[
                                "repository_id"
                            ],
                        ),
                    )
                    row = cursor.fetchone()
                    result_state = "UPDATED"

                else:
                    previous_status = existing.get(
                        "status"
                    )

                    if existing.get(
                        "needs_review"
                    ):
                        retained_change_state = (
                            existing.get(
                                "change_state"
                            )
                            or "NEW"
                        )
                    else:
                        retained_change_state = (
                            "UNCHANGED"
                        )

                    cursor.execute(
                        """
                        UPDATE repositories
                        SET description = %s,
                            relevance_score = %s,
                            canonical_url = %s,
                            metadata_hash = %s,
                            source_version_marker = COALESCE(
                                source_version_marker,
                                %s
                            ),
                            change_state = %s,
                            last_discovered_at = CURRENT_TIMESTAMP,
                            last_discovery_request_id = %s,
                            last_checked = CURRENT_TIMESTAMP,
                            availability_status = %s,
                            last_http_status = %s
                        WHERE repository_id = %s
                        RETURNING *;
                        """,
                        (
                            candidate.get(
                                "description"
                            ),
                            candidate.get(
                                "relevance_score"
                            ),
                            canonical_url,
                            candidate_hash,
                            new_version_marker,
                            retained_change_state,
                            request_id,
                            availability_status,
                            last_http_status,
                            existing[
                                "repository_id"
                            ],
                        ),
                    )
                    row = cursor.fetchone()
                    result_state = "UNCHANGED"

            repository = dict(row)

            cursor.execute(
                """
                INSERT INTO discovery_results (
                    request_id,
                    repository_id,
                    result_state,
                    previous_status,
                    metadata_hash
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    request_id,
                    repository[
                        "repository_id"
                    ],
                    result_state,
                    previous_status,
                    candidate_hash,
                ),
            )

        conn.commit()

    return repository, result_state


def load_repositories_requiring_attention(
    topic_id,
    change_state=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            if change_state:
                cursor.execute(
                    """
                    SELECT *
                    FROM repositories
                    WHERE topic_id = %s
                      AND needs_review = TRUE
                      AND change_state = %s
                    ORDER BY relevance_score DESC NULLS LAST,
                             repository_id;
                    """,
                    (
                        topic_id,
                        change_state,
                    ),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM repositories
                    WHERE topic_id = %s
                      AND needs_review = TRUE
                    ORDER BY
                        CASE change_state
                            WHEN 'UPDATED' THEN 1
                            WHEN 'NEW' THEN 2
                            ELSE 3
                        END,
                        relevance_score DESC NULLS LAST,
                        repository_id;
                    """,
                    (topic_id,),
                )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def set_repository_status(
    repository_id,
    status,
):
    allowed_statuses = {
        "CANDIDATE",
        "APPROVED",
        "REJECTED",
        "DISABLED",
    }

    if status not in allowed_statuses:
        raise ValueError(
            f"Unsupported repository status: {status}"
        )

    needs_review = (
        status == "CANDIDATE"
    )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE repositories
                SET status = %s,
                    needs_review = %s,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE repository_id = %s
                RETURNING *;
                """,
                (
                    status,
                    needs_review,
                    repository_id,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row) if row else None


def create_repository_run(
    repository_id,
    status,
    changed=None,
    content_hash=None,
    notes=None,
    http_status=None,
    content_type=None,
    last_modified=None,
    etag=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO repository_runs (
                    repository_id,
                    status,
                    changed,
                    content_hash,
                    notes,
                    http_status,
                    content_type,
                    last_modified,
                    etag
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING *;
                """,
                (
                    repository_id,
                    status,
                    changed,
                    content_hash,
                    notes,
                    http_status,
                    content_type,
                    last_modified,
                    etag,
                ),
            )
            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def load_repository_runs(
    topic_id=None,
    limit=50,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            if topic_id is None:
                cursor.execute(
                    """
                    SELECT
                        rr.*,
                        r.repository_name,
                        r.provider
                    FROM repository_runs rr
                    JOIN repositories r
                      ON r.repository_id = rr.repository_id
                    ORDER BY rr.execution_date DESC,
                             rr.run_id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        rr.*,
                        r.repository_name,
                        r.provider
                    FROM repository_runs rr
                    JOIN repositories r
                      ON r.repository_id = rr.repository_id
                    WHERE r.topic_id = %s
                    ORDER BY rr.execution_date DESC,
                             rr.run_id DESC
                    LIMIT %s;
                    """,
                    (
                        topic_id,
                        limit,
                    ),
                )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]
