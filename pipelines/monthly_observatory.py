"""
Optional scheduled entry point for the Gerontocracy Data Observatory.

For the MVP, the Shiny UI already supports:
- a monthly reminder,
- a manual "Search Again" button.

This script is kept so automatic scheduling can be enabled later
without changing the underlying discovery workflow.
"""

from src.observatory_db import (
    get_latest_research_question,
    initialize_default_topic,
    initialize_observatory_database,
)
from src.observatory_workflow import (
    run_confirmed_research_search,
)


def main():
    """
    Run the latest confirmed gerontocracy research automatically.

    Flow:
    1. initialise PostgreSQL schema,
    2. load the Observatory topic,
    3. load the latest research question,
    4. re-check existing repositories,
    5. perform a fresh web search from scratch,
    6. compare results with PostgreSQL,
    7. save NEW / UPDATED / UNCHANGED results.
    """

    initialize_observatory_database()

    topic = initialize_default_topic()

    if topic is None:
        raise RuntimeError(
            "Could not initialise the Observatory topic."
        )

    research = get_latest_research_question(
        int(
            topic["topic_id"]
        )
    )

    if research is None:
        raise RuntimeError(
            "No research question exists yet."
        )

    if research.get(
        "guardrail_status"
    ) not in (
        "IN_SCOPE",
        "RELATED",
    ):
        raise RuntimeError(
            "The latest research question is not within "
            "the Gerontocracy Observatory scope."
        )

    result = run_confirmed_research_search(
        topic_id=int(
            topic["topic_id"]
        ),
        research_id=int(
            research["research_id"]
        ),
        run_type="SCHEDULED",
    )

    print(
        "Scheduled Observatory search completed."
    )

    print(
        f"Research ID: "
        f"{research['research_id']}"
    )

    print(
        f"Existing repositories checked: "
        f"{result['existing_checked']}"
    )

    print(
        f"Requirements total: "
        f"{result['requirements_total']}"
    )

    print(
        f"Requirements with available data: "
        f"{result['requirements_found']}"
    )

    print(
        f"Requirements with no dataset found: "
        f"{result['requirements_not_found']}"
    )

    print(
        f"Requirements with only unavailable candidates: "
        f"{result['requirements_unavailable']}"
    )

    print(
        f"Repositories NEW: "
        f"{result['new_count']}"
    )

    print(
        f"Repositories UPDATED: "
        f"{result['updated_count']}"
    )

    print(
        f"Repositories UNCHANGED: "
        f"{result['unchanged_count']}"
    )


if __name__ == "__main__":
    main()