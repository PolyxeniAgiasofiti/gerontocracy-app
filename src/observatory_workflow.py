"""
High-level workflow for concept analysis, human validation and fresh discovery.
"""

from src.observatory_db import (
    compare_and_store_repository_candidate,
    complete_discovery_request,
    create_discovery_request,
    create_repository_run,
    get_latest_concept_analysis,
    load_expert_suggestions,
    save_concept_analysis,
    save_expert_suggestion,
)
from src.observatory_discovery import (
    analyse_gerontocracy_concept,
    build_final_search_context,
    discover_gerontocracy_repositories,
    validate_human_knowledge,
)
from src.observatory_refresh import (
    check_repository_source,
)


def analyse_and_store_gerontocracy(
    topic_id,
):
    result = analyse_gerontocracy_concept()

    return save_concept_analysis(
        topic_id=topic_id,
        definition=result["definition"],
        factors=result["factors"],
        data_dimensions=result[
            "data_dimensions"
        ],
        model=result.get("_model"),
    )


def validate_and_store_expert_knowledge(
    topic_id,
    suggestion,
):
    analysis = get_latest_concept_analysis(
        topic_id
    )

    if analysis is None:
        analysis = analyse_and_store_gerontocracy(
            topic_id
        )

    result = validate_human_knowledge(
        suggestion=suggestion,
        concept_definition=analysis[
            "definition"
        ],
        concept_factors=analysis[
            "factors_json"
        ],
    )

    status = (
        "ACCEPTED"
        if result["accepted"]
        else "REJECTED"
    )

    saved = save_expert_suggestion(
        topic_id=topic_id,
        suggestion_text=suggestion,
        normalized_factor=result.get(
            "normalized_factor"
        ),
        status=status,
        reason=result.get("reason"),
        model=result.get("_model"),
    )

    return saved


def get_final_search_context(
    topic_id,
):
    analysis = get_latest_concept_analysis(
        topic_id
    )

    if analysis is None:
        analysis = analyse_and_store_gerontocracy(
            topic_id
        )

    suggestions = load_expert_suggestions(
        topic_id=topic_id,
        accepted_only=True,
    )

    concept = {
        "definition": analysis[
            "definition"
        ],
        "factors": analysis[
            "factors_json"
        ],
        "data_dimensions": analysis[
            "data_dimensions_json"
        ],
    }

    return build_final_search_context(
        concept_analysis=concept,
        accepted_suggestions=suggestions,
    )


def run_fresh_repository_discovery(
    topic_id,
    run_type="MANUAL",
):
    """
    Fresh search -> compare with DB -> update existing -> add new.

    The current registry is intentionally not passed to the LLM. Only after
    the live search has completed do we compare the returned URLs/metadata
    with PostgreSQL.
    """

    search_context = get_final_search_context(
        topic_id
    )

    request = create_discovery_request(
        topic_id=topic_id,
        prompt=(
            "Fresh semantic repository discovery "
            "from validated gerontocracy context."
        ),
        search_context=search_context,
        model=None,
        run_type=run_type,
    )

    request_id = int(
        request["request_id"]
    )

    try:
        discovery = (
            discover_gerontocracy_repositories(
                search_context
            )
        )

        candidates = discovery[
            "repositories"
        ]

        counts = {
            "NEW": 0,
            "UPDATED": 0,
            "UNCHANGED": 0,
        }

        saved_ids = []

        for candidate in candidates:
            availability = (
                check_repository_source(
                    candidate["url"]
                )
            )

            repository, state = (
                compare_and_store_repository_candidate(
                    topic_id=topic_id,
                    request_id=request_id,
                    candidate=candidate,
                    availability=availability,
                )
            )

            saved_ids.append(
                repository["repository_id"]
            )

            counts[state] += 1

            create_repository_run(
                repository_id=repository[
                    "repository_id"
                ],
                status=availability[
                    "status"
                ],
                changed=None,
                content_hash=availability.get(
                    "content_hash"
                ),
                notes=(
                    "Automatic availability check "
                    "during fresh repository discovery. "
                    + str(
                        availability.get(
                            "notes",
                            "",
                        )
                    )
                ),
                http_status=availability.get(
                    "http_status"
                ),
                content_type=availability.get(
                    "content_type"
                ),
                last_modified=availability.get(
                    "last_modified"
                ),
                etag=availability.get("etag"),
            )

        complete_discovery_request(
            request_id=request_id,
            candidates_found=len(
                candidates
            ),
            status="SUCCESS",
            notes=(
                "Repository IDs: "
                + ", ".join(
                    str(value)
                    for value in saved_ids
                )
            ),
            new_count=counts["NEW"],
            updated_count=counts[
                "UPDATED"
            ],
            unchanged_count=counts[
                "UNCHANGED"
            ],
            model=discovery.get("model"),
        )

        return {
            "request_id": request_id,
            "candidates_found": len(
                candidates
            ),
            "new_count": counts["NEW"],
            "updated_count": counts[
                "UPDATED"
            ],
            "unchanged_count": counts[
                "UNCHANGED"
            ],
            "model": discovery.get(
                "model"
            ),
        }

    except Exception as exc:
        complete_discovery_request(
            request_id=request_id,
            candidates_found=0,
            status="FAILED",
            notes=str(exc),
            new_count=0,
            updated_count=0,
            unchanged_count=0,
        )
        raise
