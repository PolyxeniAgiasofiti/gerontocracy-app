import difflib
import hashlib
import json
import os
import urllib.parse

import psycopg2
from psycopg2.extras import Json, RealDictCursor


OBSERVATORY_DATABASE_URL = os.getenv(
    "OBSERVATORY_DATABASE_URL"
)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

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
    Fingerprint repository-level identity metadata only.

    Requirement/factor/geography/format are deliberately excluded because
    one repository can satisfy multiple research requirements.
    """

    stable = {
        "provider": _normalise_text(
            item.get("provider")
        ),
        "repository_name": _normalise_text(
            item.get("repository_name")
        ),
    }

    raw = json.dumps(
        stable,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        raw
    ).hexdigest()


def _source_version_marker(
    availability,
):
    """
    Use server-provided version headers when available.

    Dynamic HTML body hashes are intentionally not used.
    """

    if not availability:
        return None

    etag = availability.get(
        "etag"
    )

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

    return hashlib.sha256(
        raw
    ).hexdigest()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def initialize_observatory_database():
    """
    Create and migrate the Observatory schema without deleting existing data.
    """

    if not OBSERVATORY_DATABASE_URL:
        print(
            "Observatory PostgreSQL database not configured. "
            "Skipping initialization."
        )
        return False

    with get_observatory_connection() as conn:
        with conn.cursor() as cursor:

            # ---------------------------------------------------------------
            # Core topic / repository registry
            # ---------------------------------------------------------------

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
                        ON DELETE CASCADE
                );
                """
            )

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
                    "TEXT NOT NULL DEFAULT 'UNCHANGED'",
                ),
                (
                    "needs_review",
                    "BOOLEAN NOT NULL DEFAULT TRUE",
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

            for (
                column_name,
                column_type,
            ) in repository_columns:
                cursor.execute(
                    f"""
                    ALTER TABLE repositories
                    ADD COLUMN IF NOT EXISTS
                    {column_name} {column_type};
                    """
                )

            cursor.execute(
                """
                UPDATE repositories
                SET canonical_url = COALESCE(
                        canonical_url,
                        url
                    ),
                    first_discovered_at = COALESCE(
                        first_discovered_at,
                        date_added
                    ),
                    last_discovered_at = COALESCE(
                        last_discovered_at,
                        date_added
                    ),
                    needs_review = CASE
                        WHEN status = 'APPROVED'
                            THEN FALSE
                        WHEN needs_review IS NULL
                            THEN TRUE
                        ELSE needs_review
                    END,
                    change_state = COALESCE(
                        change_state,
                        CASE
                            WHEN status = 'APPROVED'
                                THEN 'UNCHANGED'
                            ELSE 'NEW'
                        END
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

            for (
                column_name,
                column_type,
            ) in [
                (
                    "http_status",
                    "INTEGER",
                ),
                (
                    "content_type",
                    "TEXT",
                ),
                (
                    "last_modified",
                    "TEXT",
                ),
                (
                    "etag",
                    "TEXT",
                ),
            ]:
                cursor.execute(
                    f"""
                    ALTER TABLE repository_runs
                    ADD COLUMN IF NOT EXISTS
                    {column_name} {column_type};
                    """
                )

            # ---------------------------------------------------------------
            # Discovery runs
            # ---------------------------------------------------------------

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

            discovery_columns = [
                (
                    "search_context",
                    "TEXT",
                ),
                (
                    "model",
                    "TEXT",
                ),
                (
                    "run_type",
                    "TEXT",
                ),
                (
                    "new_count",
                    "INTEGER NOT NULL DEFAULT 0",
                ),
                (
                    "updated_count",
                    "INTEGER NOT NULL DEFAULT 0",
                ),
                (
                    "unchanged_count",
                    "INTEGER NOT NULL DEFAULT 0",
                ),
                (
                    "research_id",
                    "BIGINT",
                ),
                (
                    "plan_version_id",
                    "BIGINT",
                ),
            ]

            for (
                column_name,
                column_type,
            ) in discovery_columns:
                cursor.execute(
                    f"""
                    ALTER TABLE discovery_requests
                    ADD COLUMN IF NOT EXISTS
                    {column_name} {column_type};
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

            # ---------------------------------------------------------------
            # Previous prototype tables kept for backwards compatibility
            # ---------------------------------------------------------------

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

            # ---------------------------------------------------------------
            # Clarified functional flow:
            # question -> factors -> categories -> requirements
            # ---------------------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_questions (
                    research_id BIGSERIAL PRIMARY KEY,
                    topic_id BIGINT NOT NULL,
                    question_text TEXT NOT NULL,
                    guardrail_status TEXT NOT NULL,
                    guardrail_reason TEXT,
                    guardrail_model TEXT,
                    plain_summary TEXT,
                    geographic_scope TEXT,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_research_topic
                        FOREIGN KEY (topic_id)
                        REFERENCES observatory_topics(topic_id)
                        ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_factors (
                    factor_id BIGSERIAL PRIMARY KEY,
                    research_id BIGINT NOT NULL,
                    factor_name TEXT NOT NULL,
                    simple_explanation TEXT,
                    source_type TEXT NOT NULL DEFAULT 'AI',
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_factor_research
                        FOREIGN KEY (research_id)
                        REFERENCES research_questions(research_id)
                        ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS data_categories (
                    category_id BIGSERIAL PRIMARY KEY,
                    research_id BIGINT NOT NULL,
                    factor_id BIGINT,
                    category_name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'AI',
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_category_research
                        FOREIGN KEY (research_id)
                        REFERENCES research_questions(research_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_category_factor
                        FOREIGN KEY (factor_id)
                        REFERENCES research_factors(factor_id)
                        ON DELETE SET NULL
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS data_requirements (
                    requirement_id BIGSERIAL PRIMARY KEY,
                    research_id BIGINT NOT NULL,
                    factor_id BIGINT,
                    category_id BIGINT,
                    requirement_text TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'AI',
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_requirement_research
                        FOREIGN KEY (research_id)
                        REFERENCES research_questions(research_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_requirement_factor
                        FOREIGN KEY (factor_id)
                        REFERENCES research_factors(factor_id)
                        ON DELETE SET NULL,
                    CONSTRAINT fk_requirement_category
                        FOREIGN KEY (category_id)
                        REFERENCES data_categories(category_id)
                        ON DELETE SET NULL
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_plan_versions (
                    plan_version_id BIGSERIAL PRIMARY KEY,
                    research_id BIGINT NOT NULL,
                    version_number INTEGER NOT NULL,
                    snapshot_json JSONB NOT NULL,
                    confirmed_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_plan_research
                        FOREIGN KEY (research_id)
                        REFERENCES research_questions(research_id)
                        ON DELETE CASCADE,
                    CONSTRAINT uq_research_plan_version
                        UNIQUE (
                            research_id,
                            version_number
                        )
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS repository_research_links (
                    research_id BIGINT NOT NULL,
                    repository_id BIGINT NOT NULL,
                    first_seen_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (
                        research_id,
                        repository_id
                    ),
                    CONSTRAINT fk_link_research
                        FOREIGN KEY (research_id)
                        REFERENCES research_questions(research_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_link_repository
                        FOREIGN KEY (repository_id)
                        REFERENCES repositories(repository_id)
                        ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS requirement_dataset_matches (
                    match_id BIGSERIAL PRIMARY KEY,
                    request_id BIGINT NOT NULL,
                    requirement_id BIGINT NOT NULL,
                    repository_id BIGINT,
                    status TEXT NOT NULL,
                    dataset_name TEXT,
                    dataset_url TEXT,
                    provider TEXT,
                    geography TEXT,
                    data_format TEXT,
                    evidence_reason TEXT,
                    availability_status TEXT,
                    http_status INTEGER,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_requirement_match_request
                        FOREIGN KEY (request_id)
                        REFERENCES discovery_requests(request_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_requirement_match_requirement
                        FOREIGN KEY (requirement_id)
                        REFERENCES data_requirements(requirement_id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_requirement_match_repository
                        FOREIGN KEY (repository_id)
                        REFERENCES repositories(repository_id)
                        ON DELETE SET NULL
                );
                """
            )

        conn.commit()

    print(
        "Data Observatory PostgreSQL tables are ready."
    )

    return True


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

def initialize_default_topic():
    if not OBSERVATORY_DATABASE_URL:
        return None

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM observatory_topics
                WHERE name = %s
                ORDER BY topic_id
                LIMIT 1;
                """,
                (
                    "Gerontocracy in Greece",
                ),
            )

            row = cursor.fetchone()

            if row:
                return dict(row)

            cursor.execute(
                """
                INSERT INTO observatory_topics (
                    name,
                    description,
                    geography,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'ACTIVE'
                )
                RETURNING *;
                """,
                (
                    "Gerontocracy in Greece",
                    (
                        "Research topic for studying gerontocracy "
                        "and intergenerational distributions of power, "
                        "resources and opportunities."
                    ),
                    "Greece + European Union",
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


# ---------------------------------------------------------------------------
# Generic reads
# ---------------------------------------------------------------------------

def load_observatory_table(
    table_name,
):
    allowed = {
        "observatory_topics",
        "repositories",
        "repository_runs",
        "discovery_requests",
        "discovery_results",
        "concept_analyses",
        "expert_suggestions",
        "research_questions",
        "research_factors",
        "data_categories",
        "data_requirements",
        "research_plan_versions",
        "repository_research_links",
        "requirement_dataset_matches",
    }

    if table_name not in allowed:
        raise ValueError(
            "Unsupported Observatory table."
        )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                f"""
                SELECT *
                FROM {table_name};
                """
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def get_repository(
    repository_id,
):
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
                (
                    repository_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row
        else None
    )


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
                        r.provider,
                        r.repository_name
                    FROM repository_runs rr
                    JOIN repositories r
                      ON r.repository_id =
                         rr.repository_id
                    ORDER BY
                        rr.execution_date DESC,
                        rr.run_id DESC
                    LIMIT %s;
                    """,
                    (
                        limit,
                    ),
                )

            else:
                cursor.execute(
                    """
                    SELECT
                        rr.*,
                        r.provider,
                        r.repository_name
                    FROM repository_runs rr
                    JOIN repositories r
                      ON r.repository_id =
                         rr.repository_id
                    WHERE r.topic_id = %s
                    ORDER BY
                        rr.execution_date DESC,
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


# ---------------------------------------------------------------------------
# Research question
# ---------------------------------------------------------------------------

def create_research_question(
    topic_id,
    question_text,
    guardrail_status,
    guardrail_reason=None,
    guardrail_model=None,
):
    status = (
        "DRAFT"
        if guardrail_status
        in (
            "IN_SCOPE",
            "RELATED",
        )
        else "REJECTED"
    )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                INSERT INTO research_questions (
                    topic_id,
                    question_text,
                    guardrail_status,
                    guardrail_reason,
                    guardrail_model,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *;
                """,
                (
                    topic_id,
                    question_text,
                    guardrail_status,
                    guardrail_reason,
                    guardrail_model,
                    status,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def get_research_question(
    research_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM research_questions
                WHERE research_id = %s;
                """,
                (
                    research_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row
        else None
    )


def get_latest_research_question(
    topic_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM research_questions
                WHERE topic_id = %s
                ORDER BY
                    created_at DESC,
                    research_id DESC
                LIMIT 1;
                """,
                (
                    topic_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row
        else None
    )


# ---------------------------------------------------------------------------
# Editable research plan
# ---------------------------------------------------------------------------

def save_generated_research_plan(
    research_id,
    plain_summary,
    geographic_scope,
    factors,
):
    """
    Save the hidden AI analysis as relational editable records.

    Old active items are retained historically but deactivated.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                UPDATE research_questions
                SET plain_summary = %s,
                    geographic_scope = %s,
                    status = 'DRAFT',
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE research_id = %s;
                """,
                (
                    plain_summary,
                    geographic_scope,
                    research_id,
                ),
            )

            cursor.execute(
                """
                UPDATE research_factors
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE research_id = %s
                  AND active = TRUE;
                """,
                (
                    research_id,
                ),
            )

            cursor.execute(
                """
                UPDATE data_categories
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE research_id = %s
                  AND active = TRUE;
                """,
                (
                    research_id,
                ),
            )

            cursor.execute(
                """
                UPDATE data_requirements
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE research_id = %s
                  AND active = TRUE;
                """,
                (
                    research_id,
                ),
            )

            for factor in factors or []:

                factor_name = str(
                    factor.get(
                        "name",
                        "",
                    )
                ).strip()

                if not factor_name:
                    continue

                cursor.execute(
                    """
                    INSERT INTO research_factors (
                        research_id,
                        factor_name,
                        simple_explanation,
                        source_type,
                        active
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        'AI',
                        TRUE
                    )
                    RETURNING factor_id;
                    """,
                    (
                        research_id,
                        factor_name,
                        factor.get(
                            "simple_explanation",
                            "",
                        ),
                    ),
                )

                factor_id = int(
                    cursor.fetchone()[
                        "factor_id"
                    ]
                )

                for category in factor.get(
                    "categories",
                    [],
                ):

                    category_name = str(
                        category.get(
                            "name",
                            "",
                        )
                    ).strip()

                    if not category_name:
                        continue

                    cursor.execute(
                        """
                        INSERT INTO data_categories (
                            research_id,
                            factor_id,
                            category_name,
                            source_type,
                            active
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'AI',
                            TRUE
                        )
                        RETURNING category_id;
                        """,
                        (
                            research_id,
                            factor_id,
                            category_name,
                        ),
                    )

                    category_id = int(
                        cursor.fetchone()[
                            "category_id"
                        ]
                    )

                    for requirement in (
                        category.get(
                            "requirements",
                            [],
                        )
                    ):

                        requirement_text = str(
                            requirement
                        ).strip()

                        if not requirement_text:
                            continue

                        cursor.execute(
                            """
                            INSERT INTO data_requirements (
                                research_id,
                                factor_id,
                                category_id,
                                requirement_text,
                                source_type,
                                active
                            )
                            VALUES (
                                %s,
                                %s,
                                %s,
                                %s,
                                'AI',
                                TRUE
                            );
                            """,
                            (
                                research_id,
                                factor_id,
                                category_id,
                                requirement_text,
                            ),
                        )

        conn.commit()


def load_research_plan(
    research_id,
    active_only=True,
):
    active_clause = (
        " AND active = TRUE"
        if active_only
        else ""
    )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM research_factors
                WHERE research_id = %s
                """
                + active_clause
                + """
                ORDER BY factor_id;
                """,
                (
                    research_id,
                ),
            )

            factors = [
                dict(row)
                for row in cursor.fetchall()
            ]

            category_active_clause = (
                " AND c.active = TRUE"
                if active_only
                else ""
            )

            cursor.execute(
                """
                SELECT
                    c.*,
                    f.factor_name
                FROM data_categories c
                LEFT JOIN research_factors f
                  ON f.factor_id = c.factor_id
                WHERE c.research_id = %s
                """
                + category_active_clause
                + """
                ORDER BY c.category_id;
                """,
                (
                    research_id,
                ),
            )

            categories = [
                dict(row)
                for row in cursor.fetchall()
            ]

            requirement_active_clause = (
                " AND r.active = TRUE"
                if active_only
                else ""
            )

            cursor.execute(
                """
                SELECT
                    r.*,
                    f.factor_name,
                    c.category_name
                FROM data_requirements r
                LEFT JOIN research_factors f
                  ON f.factor_id = r.factor_id
                LEFT JOIN data_categories c
                  ON c.category_id =
                     r.category_id
                WHERE r.research_id = %s
                """
                + requirement_active_clause
                + """
                ORDER BY r.requirement_id;
                """,
                (
                    research_id,
                ),
            )

            requirements = [
                dict(row)
                for row in cursor.fetchall()
            ]

    return {
        "factors": factors,
        "categories": categories,
        "requirements": requirements,
    }


def update_research_plan_items(
    research_id,
    factors,
    categories,
    requirements,
):
    with get_observatory_connection() as conn:
        with conn.cursor() as cursor:

            for item in factors:
                cursor.execute(
                    """
                    UPDATE research_factors
                    SET factor_name = %s,
                        active = %s,
                        updated_at =
                            CURRENT_TIMESTAMP
                    WHERE factor_id = %s
                      AND research_id = %s;
                    """,
                    (
                        item["text"],
                        bool(
                            item["active"]
                        ),
                        item["id"],
                        research_id,
                    ),
                )

            for item in categories:
                cursor.execute(
                    """
                    UPDATE data_categories
                    SET category_name = %s,
                        active = %s,
                        updated_at =
                            CURRENT_TIMESTAMP
                    WHERE category_id = %s
                      AND research_id = %s;
                    """,
                    (
                        item["text"],
                        bool(
                            item["active"]
                        ),
                        item["id"],
                        research_id,
                    ),
                )

            for item in requirements:
                cursor.execute(
                    """
                    UPDATE data_requirements
                    SET requirement_text = %s,
                        active = %s,
                        updated_at =
                            CURRENT_TIMESTAMP
                    WHERE requirement_id = %s
                      AND research_id = %s;
                    """,
                    (
                        item["text"],
                        bool(
                            item["active"]
                        ),
                        item["id"],
                        research_id,
                    ),
                )

            # If a factor is removed, remove its child categories.
            cursor.execute(
                """
                UPDATE data_categories c
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                FROM research_factors f
                WHERE c.factor_id = f.factor_id
                  AND c.research_id = %s
                  AND f.research_id = %s
                  AND f.active = FALSE
                  AND c.active = TRUE;
                """,
                (
                    research_id,
                    research_id,
                ),
            )

            # If a factor is removed, remove its child requirements.
            cursor.execute(
                """
                UPDATE data_requirements r
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                FROM research_factors f
                WHERE r.factor_id = f.factor_id
                  AND r.research_id = %s
                  AND f.research_id = %s
                  AND f.active = FALSE
                  AND r.active = TRUE;
                """,
                (
                    research_id,
                    research_id,
                ),
            )

            # If a category is removed, remove its child requirements.
            cursor.execute(
                """
                UPDATE data_requirements r
                SET active = FALSE,
                    updated_at =
                        CURRENT_TIMESTAMP
                FROM data_categories c
                WHERE r.category_id =
                      c.category_id
                  AND r.research_id = %s
                  AND c.research_id = %s
                  AND c.active = FALSE
                  AND r.active = TRUE;
                """,
                (
                    research_id,
                    research_id,
                ),
            )

            cursor.execute(
                """
                UPDATE research_questions
                SET updated_at =
                    CURRENT_TIMESTAMP
                WHERE research_id = %s;
                """,
                (
                    research_id,
                ),
            )

        conn.commit()


def add_research_factor(
    research_id,
    text,
):
    text = (
        text
        or ""
    ).strip()

    if not text:
        return None

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                INSERT INTO research_factors (
                    research_id,
                    factor_name,
                    simple_explanation,
                    source_type,
                    active
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'HUMAN',
                    TRUE
                )
                RETURNING *;
                """,
                (
                    research_id,
                    text,
                    "Added by the user.",
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def add_data_category(
    research_id,
    text,
):
    text = (
        text
        or ""
    ).strip()

    if not text:
        return None

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                INSERT INTO data_categories (
                    research_id,
                    factor_id,
                    category_name,
                    source_type,
                    active
                )
                VALUES (
                    %s,
                    NULL,
                    %s,
                    'HUMAN',
                    TRUE
                )
                RETURNING *;
                """,
                (
                    research_id,
                    text,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def add_data_requirement(
    research_id,
    text,
):
    text = (
        text
        or ""
    ).strip()

    if not text:
        return None

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                INSERT INTO data_requirements (
                    research_id,
                    factor_id,
                    category_id,
                    requirement_text,
                    source_type,
                    active
                )
                VALUES (
                    %s,
                    NULL,
                    NULL,
                    %s,
                    'HUMAN',
                    TRUE
                )
                RETURNING *;
                """,
                (
                    research_id,
                    text,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


# ---------------------------------------------------------------------------
# Confirmed research-plan versions
# ---------------------------------------------------------------------------

def confirm_research_plan(
    research_id,
):
    research = get_research_question(
        research_id
    )

    if not research:
        raise RuntimeError(
            "Research question not found."
        )

    plan = load_research_plan(
        research_id,
        active_only=True,
    )

    if not plan[
        "requirements"
    ]:
        raise RuntimeError(
            "The research plan must contain at least "
            "one active data requirement."
        )

    snapshot = {
        "research_id": research_id,
        "question_text": (
            research[
                "question_text"
            ]
        ),
        "plain_summary": (
            research.get(
                "plain_summary"
            )
        ),
        "geographic_scope": (
            research.get(
                "geographic_scope"
            )
        ),
        "factors": [
            {
                "factor_id": int(
                    item["factor_id"]
                ),
                "factor_name": (
                    item[
                        "factor_name"
                    ]
                ),
                "simple_explanation": (
                    item.get(
                        "simple_explanation"
                    )
                ),
                "source_type": (
                    item.get(
                        "source_type"
                    )
                ),
            }
            for item in plan[
                "factors"
            ]
        ],
        "categories": [
            {
                "category_id": int(
                    item["category_id"]
                ),
                "factor_id": (
                    int(
                        item[
                            "factor_id"
                        ]
                    )
                    if item.get(
                        "factor_id"
                    ) is not None
                    else None
                ),
                "category_name": (
                    item[
                        "category_name"
                    ]
                ),
                "source_type": (
                    item.get(
                        "source_type"
                    )
                ),
            }
            for item in plan[
                "categories"
            ]
        ],
        "requirements": [
            {
                "requirement_id": int(
                    item[
                        "requirement_id"
                    ]
                ),
                "factor_id": (
                    int(
                        item[
                            "factor_id"
                        ]
                    )
                    if item.get(
                        "factor_id"
                    ) is not None
                    else None
                ),
                "category_id": (
                    int(
                        item[
                            "category_id"
                        ]
                    )
                    if item.get(
                        "category_id"
                    ) is not None
                    else None
                ),
                "requirement_text": (
                    item[
                        "requirement_text"
                    ]
                ),
                "source_type": (
                    item.get(
                        "source_type"
                    )
                ),
            }
            for item in plan[
                "requirements"
            ]
        ],
    }

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        MAX(
                            version_number
                        ),
                        0
                    ) + 1
                    AS next_version
                FROM research_plan_versions
                WHERE research_id = %s;
                """,
                (
                    research_id,
                ),
            )

            version_number = int(
                cursor.fetchone()[
                    "next_version"
                ]
            )

            cursor.execute(
                """
                INSERT INTO research_plan_versions (
                    research_id,
                    version_number,
                    snapshot_json
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                RETURNING *;
                """,
                (
                    research_id,
                    version_number,
                    Json(
                        snapshot
                    ),
                ),
            )

            row = cursor.fetchone()

            cursor.execute(
                """
                UPDATE research_questions
                SET status = 'CONFIRMED',
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE research_id = %s;
                """,
                (
                    research_id,
                ),
            )

        conn.commit()

    return dict(row)


def get_latest_confirmed_plan(
    research_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM research_plan_versions
                WHERE research_id = %s
                ORDER BY
                    version_number DESC,
                    plan_version_id DESC
                LIMIT 1;
                """,
                (
                    research_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row
        else None
    )


# ---------------------------------------------------------------------------
# Discovery-run persistence
# ---------------------------------------------------------------------------

def create_discovery_request(
    topic_id,
    prompt,
    search_context=None,
    model=None,
    run_type="MANUAL",
    research_id=None,
    plan_version_id=None,
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
                    run_type,
                    research_id,
                    plan_version_id
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *;
                """,
                (
                    topic_id,
                    prompt,
                    search_context,
                    model,
                    run_type,
                    research_id,
                    plan_version_id,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def complete_discovery_request(
    request_id,
    candidates_found,
    status,
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
                SET candidates_found = %s,
                    status = %s,
                    notes = %s,
                    new_count = %s,
                    updated_count = %s,
                    unchanged_count = %s,
                    model = COALESCE(
                        %s,
                        model
                    )
                WHERE request_id = %s
                RETURNING *;
                """,
                (
                    candidates_found,
                    status,
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

    return (
        dict(row)
        if row
        else None
    )


def load_discovery_history(
    topic_id,
    limit=25,
    research_id=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            if research_id is None:
                cursor.execute(
                    """
                    SELECT *
                    FROM discovery_requests
                    WHERE topic_id = %s
                    ORDER BY
                        execution_date DESC,
                        request_id DESC
                    LIMIT %s;
                    """,
                    (
                        topic_id,
                        limit,
                    ),
                )

            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM discovery_requests
                    WHERE topic_id = %s
                      AND research_id = %s
                    ORDER BY
                        execution_date DESC,
                        request_id DESC
                    LIMIT %s;
                    """,
                    (
                        topic_id,
                        research_id,
                        limit,
                    ),
                )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


# ---------------------------------------------------------------------------
# Repository identity / NEW UPDATED UNCHANGED
# ---------------------------------------------------------------------------

def _repository_name_tokens(
    name,
    provider=None,
):
    text = _normalise_text(
        name
    )

    provider_tokens = set(
        _normalise_text(
            provider
        ).split()
    )

    stop_words = {
        "data",
        "database",
        "dataset",
        "datasets",
        "statistics",
        "statistical",
        "portal",
        "repository",
        "official",
        "open",
        "the",
        "and",
        "for",
        "of",
        "on",
        "chapter",
    }

    tokens = []

    for raw in text.split():
        token = "".join(
            character
            for character in raw
            if character.isalnum()
        )

        if not token:
            continue

        if (
            token.endswith("s")
            and len(token) > 3
        ):
            token = token[:-1]

        if (
            token in stop_words
            or token in provider_tokens
        ):
            continue

        tokens.append(
            token
        )

    return set(
        tokens
    )


def _repository_similarity(
    candidate,
    existing,
):
    candidate_provider = (
        _normalise_text(
            candidate.get(
                "provider"
            )
        )
    )

    existing_provider = (
        _normalise_text(
            existing.get(
                "provider"
            )
        )
    )

    provider_same = bool(
        candidate_provider
        and candidate_provider
        == existing_provider
    )

    candidate_tokens = (
        _repository_name_tokens(
            candidate.get(
                "repository_name"
            ),
            candidate.get(
                "provider"
            ),
        )
    )

    existing_tokens = (
        _repository_name_tokens(
            existing.get(
                "repository_name"
            ),
            existing.get(
                "provider"
            ),
        )
    )

    union = (
        candidate_tokens
        | existing_tokens
    )

    overlap = (
        len(
            candidate_tokens
            & existing_tokens
        )
        / len(union)
        if union
        else 0.0
    )

    name_ratio = (
        difflib.SequenceMatcher(
            None,
            _normalise_text(
                candidate.get(
                    "repository_name"
                )
            ),
            _normalise_text(
                existing.get(
                    "repository_name"
                )
            ),
        ).ratio()
    )

    candidate_domain = (
        urllib.parse.urlsplit(
            _canonicalize_url(
                candidate.get(
                    "url"
                )
            )
        ).netloc
    )

    existing_domain = (
        urllib.parse.urlsplit(
            _canonicalize_url(
                existing.get(
                    "canonical_url"
                )
                or existing.get(
                    "url"
                )
            )
        ).netloc
    )

    domain_same = bool(
        candidate_domain
        and candidate_domain
        == existing_domain
    )

    if (
        provider_same
        and overlap >= 0.60
    ):
        return max(
            0.85,
            overlap,
        )

    if (
        provider_same
        and name_ratio >= 0.82
    ):
        return name_ratio

    if (
        domain_same
        and overlap >= 0.75
    ):
        return max(
            0.80,
            overlap,
        )

    return 0.0


def _find_existing_repository(
    cursor,
    topic_id,
    canonical_url,
    candidate,
):
    cursor.execute(
        """
        SELECT *
        FROM repositories
        WHERE topic_id = %s
        ORDER BY repository_id;
        """,
        (
            topic_id,
        ),
    )

    rows = [
        dict(row)
        for row in cursor.fetchall()
    ]

    # First try exact canonical URL.
    for row in rows:
        existing_url = (
            row.get(
                "canonical_url"
            )
            or row.get(
                "url"
            )
        )

        if (
            _canonicalize_url(
                existing_url
            )
            == canonical_url
        ):
            return row

    # Otherwise try logical identity.
    best = None
    best_score = 0.0

    for row in rows:
        score = _repository_similarity(
            candidate,
            row,
        )

        if score > best_score:
            best = row
            best_score = score

    if (
        best is not None
        and best_score >= 0.80
    ):
        return best

    return None


def compare_and_store_repository_candidate(
    topic_id,
    request_id,
    candidate,
    availability=None,
):
    canonical_url = _canonicalize_url(
        candidate.get(
            "url"
        )
    )

    if not canonical_url:
        raise ValueError(
            "Repository candidate has no valid URL."
        )

    new_hash = (
        _repository_metadata_hash(
            candidate
        )
    )

    new_version_marker = (
        _source_version_marker(
            availability
        )
    )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            existing = (
                _find_existing_repository(
                    cursor=cursor,
                    topic_id=topic_id,
                    canonical_url=canonical_url,
                    candidate=candidate,
                )
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
                        metadata_hash,
                        source_version_marker,
                        change_state,
                        needs_review,
                        first_discovered_at,
                        last_discovered_at,
                        last_discovery_request_id,
                        availability_status,
                        last_http_status
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'CANDIDATE',
                        %s,
                        %s,
                        %s,
                        'NEW',
                        TRUE,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING *;
                    """,
                    (
                        topic_id,
                        candidate.get(
                            "provider"
                        )
                        or "Unknown",
                        candidate.get(
                            "repository_name"
                        )
                        or "Unnamed repository",
                        candidate.get(
                            "url"
                        ),
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
                        new_hash,
                        new_version_marker,
                        request_id,
                        (
                            availability.get(
                                "status"
                            )
                            if availability
                            else None
                        ),
                        (
                            availability.get(
                                "http_status"
                            )
                            if availability
                            else None
                        ),
                    ),
                )

                repository = dict(
                    cursor.fetchone()
                )

                state = "NEW"

            else:
                repository_id = int(
                    existing[
                        "repository_id"
                    ]
                )

                old_url = _canonicalize_url(
                    existing.get(
                        "canonical_url"
                    )
                    or existing.get(
                        "url"
                    )
                )

                old_hash = (
                    _repository_metadata_hash(
                        existing
                    )
                )

                old_version_marker = (
                    existing.get(
                        "source_version_marker"
                    )
                )

                url_changed = bool(
                    old_url
                    and old_url
                    != canonical_url
                )

                metadata_changed = (
                    old_hash
                    != new_hash
                )

                version_changed = bool(
                    old_version_marker
                    and new_version_marker
                    and old_version_marker
                    != new_version_marker
                )

                updated = (
                    url_changed
                    or metadata_changed
                    or version_changed
                )

                if updated:
                    state = "UPDATED"

                    previous_status = (
                        existing.get(
                            "status"
                        )
                    )

                    status = "CANDIDATE"
                    needs_review = True

                else:
                    state = "UNCHANGED"

                    previous_status = (
                        existing.get(
                            "previous_status"
                        )
                    )

                    status = (
                        existing.get(
                            "status"
                        )
                        or "CANDIDATE"
                    )

                    needs_review = bool(
                        existing.get(
                            "needs_review"
                        )
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
                        status = %s,
                        relevance_score = %s,
                        metadata_hash = %s,
                        source_version_marker =
                            COALESCE(
                                %s,
                                source_version_marker
                            ),
                        change_state = %s,
                        needs_review = %s,
                        previous_status = %s,
                        last_discovered_at =
                            CURRENT_TIMESTAMP,
                        last_discovery_request_id = %s,
                        availability_status = %s,
                        last_http_status = %s
                    WHERE repository_id = %s
                    RETURNING *;
                    """,
                    (
                        candidate.get(
                            "provider"
                        )
                        or existing.get(
                            "provider"
                        ),
                        candidate.get(
                            "repository_name"
                        )
                        or existing.get(
                            "repository_name"
                        ),
                        candidate.get(
                            "url"
                        )
                        or existing.get(
                            "url"
                        ),
                        canonical_url,
                        candidate.get(
                            "description"
                        )
                        or existing.get(
                            "description"
                        ),
                        candidate.get(
                            "dimension"
                        )
                        or existing.get(
                            "dimension"
                        ),
                        candidate.get(
                            "geography"
                        )
                        or existing.get(
                            "geography"
                        ),
                        candidate.get(
                            "data_format"
                        )
                        or existing.get(
                            "data_format"
                        ),
                        candidate.get(
                            "refresh_frequency"
                        )
                        or existing.get(
                            "refresh_frequency"
                        ),
                        status,
                        candidate.get(
                            "relevance_score"
                        ),
                        new_hash,
                        new_version_marker,
                        state,
                        needs_review,
                        previous_status,
                        request_id,
                        (
                            availability.get(
                                "status"
                            )
                            if availability
                            else existing.get(
                                "availability_status"
                            )
                        ),
                        (
                            availability.get(
                                "http_status"
                            )
                            if availability
                            else existing.get(
                                "last_http_status"
                            )
                        ),
                        repository_id,
                    ),
                )

                repository = dict(
                    cursor.fetchone()
                )

            cursor.execute(
                """
                INSERT INTO discovery_results (
                    request_id,
                    repository_id,
                    result_state,
                    previous_status,
                    metadata_hash
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    request_id,
                    repository[
                        "repository_id"
                    ],
                    state,
                    repository.get(
                        "previous_status"
                    ),
                    new_hash,
                ),
            )

        conn.commit()

    return (
        repository,
        state,
    )


def set_repository_status(
    repository_id,
    new_status,
):
    new_status = str(
        new_status
    ).upper()

    if new_status not in {
        "APPROVED",
        "REJECTED",
        "CANDIDATE",
    }:
        raise ValueError(
            "Unsupported repository status."
        )

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT status
                FROM repositories
                WHERE repository_id = %s;
                """,
                (
                    repository_id,
                ),
            )

            current = cursor.fetchone()

            if not current:
                return None

            cursor.execute(
                """
                UPDATE repositories
                SET previous_status = %s,
                    status = %s,
                    needs_review = CASE
                        WHEN %s IN (
                            'APPROVED',
                            'REJECTED'
                        )
                            THEN FALSE
                        ELSE TRUE
                    END,
                    reviewed_at = CASE
                        WHEN %s IN (
                            'APPROVED',
                            'REJECTED'
                        )
                            THEN CURRENT_TIMESTAMP
                        ELSE reviewed_at
                    END
                WHERE repository_id = %s
                RETURNING *;
                """,
                (
                    current[
                        "status"
                    ],
                    new_status,
                    new_status,
                    new_status,
                    repository_id,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return (
        dict(row)
        if row
        else None
    )


# ---------------------------------------------------------------------------
# Repository checks
# ---------------------------------------------------------------------------

def create_repository_run(
    repository_id,
    status,
    changed=None,
    rows_received=None,
    content_hash=None,
    raw_snapshot_location=None,
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
                    rows_received,
                    content_hash,
                    raw_snapshot_location,
                    notes,
                    http_status,
                    content_type,
                    last_modified,
                    etag
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *;
                """,
                (
                    repository_id,
                    status,
                    changed,
                    rows_received,
                    content_hash,
                    raw_snapshot_location,
                    notes,
                    http_status,
                    content_type,
                    last_modified,
                    etag,
                ),
            )

            row = cursor.fetchone()

            cursor.execute(
                """
                UPDATE repositories
                SET last_checked =
                        CURRENT_TIMESTAMP,
                    availability_status = %s,
                    last_http_status = %s
                WHERE repository_id = %s;
                """,
                (
                    status,
                    http_status,
                    repository_id,
                ),
            )

        conn.commit()

    return dict(row)


def update_repository_check_state(
    repository_id,
    availability,
):
    with get_observatory_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE repositories
                SET last_checked =
                        CURRENT_TIMESTAMP,
                    availability_status = %s,
                    last_http_status = %s
                WHERE repository_id = %s;
                """,
                (
                    availability.get(
                        "status"
                    ),
                    availability.get(
                        "http_status"
                    ),
                    repository_id,
                ),
            )

        conn.commit()


# ---------------------------------------------------------------------------
# Research <-> repository links
# ---------------------------------------------------------------------------

def link_repository_to_research(
    research_id,
    repository_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO repository_research_links (
                    research_id,
                    repository_id
                )
                VALUES (
                    %s,
                    %s
                )
                ON CONFLICT (
                    research_id,
                    repository_id
                )
                DO UPDATE
                SET last_seen_at =
                    CURRENT_TIMESTAMP;
                """,
                (
                    research_id,
                    repository_id,
                ),
            )

        conn.commit()


def load_repositories_for_research(
    research_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT r.*
                FROM repositories r
                JOIN repository_research_links l
                  ON l.repository_id =
                     r.repository_id
                WHERE l.research_id = %s
                ORDER BY r.repository_id;
                """,
                (
                    research_id,
                ),
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


# ---------------------------------------------------------------------------
# Requirement coverage
# ---------------------------------------------------------------------------

def save_requirement_dataset_match(
    request_id,
    requirement_id,
    status,
    repository_id=None,
    dataset_name=None,
    dataset_url=None,
    provider=None,
    geography=None,
    data_format=None,
    evidence_reason=None,
    availability_status=None,
    http_status=None,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                INSERT INTO requirement_dataset_matches (
                    request_id,
                    requirement_id,
                    repository_id,
                    status,
                    dataset_name,
                    dataset_url,
                    provider,
                    geography,
                    data_format,
                    evidence_reason,
                    availability_status,
                    http_status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *;
                """,
                (
                    request_id,
                    requirement_id,
                    repository_id,
                    status,
                    dataset_name,
                    dataset_url,
                    provider,
                    geography,
                    data_format,
                    evidence_reason,
                    availability_status,
                    http_status,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return dict(row)


def load_latest_requirement_coverage(
    research_id,
):
    """
    Return coverage for exactly the requirements evaluated by the latest
    successful discovery run.
    """

    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT request_id
                FROM discovery_requests
                WHERE research_id = %s
                  AND status = 'SUCCESS'
                ORDER BY
                    execution_date DESC,
                    request_id DESC
                LIMIT 1;
                """,
                (
                    research_id,
                ),
            )

            request = cursor.fetchone()

            if not request:
                return []

            request_id = int(
                request[
                    "request_id"
                ]
            )

            cursor.execute(
                """
                SELECT
                    r.requirement_id,
                    r.requirement_text,
                    f.factor_name,
                    c.category_name,
                    m.status,
                    m.dataset_name,
                    m.dataset_url,
                    m.provider,
                    m.geography,
                    m.data_format,
                    m.evidence_reason,
                    m.availability_status,
                    m.http_status,
                    m.repository_id,
                    m.request_id
                FROM requirement_dataset_matches m
                JOIN data_requirements r
                  ON r.requirement_id =
                     m.requirement_id
                LEFT JOIN research_factors f
                  ON f.factor_id =
                     r.factor_id
                LEFT JOIN data_categories c
                  ON c.category_id =
                     r.category_id
                WHERE m.request_id = %s
                  AND r.research_id = %s
                ORDER BY
                    r.requirement_id,
                    m.match_id;
                """,
                (
                    request_id,
                    research_id,
                ),
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]


def get_last_discovery_at(
    research_id,
):
    with get_observatory_connection() as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT execution_date
                FROM discovery_requests
                WHERE research_id = %s
                  AND status = 'SUCCESS'
                ORDER BY
                    execution_date DESC,
                    request_id DESC
                LIMIT 1;
                """,
                (
                    research_id,
                ),
            )

            row = cursor.fetchone()

    if not row:
        return None

    return row[
        "execution_date"
    ]