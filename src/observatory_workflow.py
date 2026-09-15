"""
High-level workflow for the Gerontocracy Data Observatory.
"""

from src.observatory_db import (
    compare_and_store_repository_candidate,
    complete_discovery_request,
    create_discovery_request,
    create_repository_run,
    ensure_human_research_goal,
    get_latest_concept_analysis,
    load_active_research_goals,
    load_expert_suggestions,
    replace_llm_research_goals,
    save_concept_analysis,
    save_expert_suggestion,
    save_goal_dataset_match,
)
from src.observatory_discovery import (
    analyse_gerontocracy_concept,
    build_final_search_context,
    canonicalize_url,
    discover_datasets_for_goals,
    validate_human_knowledge,
)
from src.observatory_refresh import (
    check_repository_source,
)


def analyse_and_store_gerontocracy(
    topic_id,
):
    result = analyse_gerontocracy_concept()

    analysis = save_concept_analysis(
        topic_id=topic_id,
        definition=result["definition"],
        factors=result["factors"],
        data_dimensions=result[
            "data_dimensions"
        ],
        model=result.get("_model"),
    )

    replace_llm_research_goals(
        topic_id=topic_id,
        analysis_id=analysis["analysis_id"],
        factors=result["factors"],
    )

    # Keep already accepted human knowledge active as research goals.
    suggestions = load_expert_suggestions(
        topic_id=topic_id,
        accepted_only=True,
    )

    for suggestion in suggestions:
        ensure_human_research_goal(
            topic_id=topic_id,
            suggestion_id=suggestion[
                "suggestion_id"
            ],
            goal_name=(
                suggestion.get(
                    "normalized_factor"
                )
                or suggestion.get(
                    "suggestion_text"
                )
            ),
            what_data_to_find=(
                suggestion.get(
                    "what_data_to_find"
                )
                or suggestion.get(
                    "normalized_factor"
                )
                or suggestion.get(
                    "suggestion_text"
                )
            ),
        )

    return analysis


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

    # Add an accepted human idea to the persistent research-goal list.
    if status == "ACCEPTED":
        ensure_human_research_goal(
            topic_id=topic_id,
            suggestion_id=saved[
                "suggestion_id"
            ],
            goal_name=(
                result.get(
                    "normalized_factor"
                )
                or suggestion
            ),
            what_data_to_find=(
                result.get(
                    "what_data_to_find"
                )
                or result.get(
                    "normalized_factor"
                )
                or suggestion
            ),
        )

    return saved


def _ensure_goals_exist(
    topic_id,
    analysis,
):
    goals = load_active_research_goals(
        topic_id
    )

    if goals:
        return goals

    replace_llm_research_goals(
        topic_id=topic_id,
        analysis_id=analysis[
            "analysis_id"
        ],
        factors=analysis[
            "factors_json"
        ],
    )

    return load_active_research_goals(
        topic_id
    )


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

    goals = _ensure_goals_exist(
        topic_id,
        analysis,
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

    context = build_final_search_context(
        concept_analysis=concept,
        accepted_suggestions=suggestions,
        research_goals=goals,
    )

    return context, goals


def run_fresh_repository_discovery(
    topic_id,
    run_type="MANUAL",
):
    """
    For every active research goal:
      1. search the live web,
      2. evaluate whether an actual usable dataset was found,
      3. save the goal -> dataset result,
      4. register the source repository,
      5. compare the source with the existing repository registry.
    """

    search_context, goals = (
        get_final_search_context(
            topic_id
        )
    )

    request = create_discovery_request(
        topic_id=topic_id,
        prompt=(
            "Fresh goal-by-goal dataset discovery "
            "from the validated gerontocracy research goals."
        ),
        search_context=search_context,
        model=None,
        run_type=run_type,
    )

    request_id = int(
        request["request_id"]
    )

    try:
        discovery = discover_datasets_for_goals(
            search_context=search_context,
            research_goals=goals,
        )

        counts = {
            "NEW": 0,
            "UPDATED": 0,
            "UNCHANGED": 0,
        }

        counted_repository_ids = set()
        goals_found = 0
        goals_not_found = 0
        goals_unavailable = 0

        for goal_result in discovery[
            "goal_results"
        ]:
            goal_id = int(
                goal_result["goal_id"]
            )

            datasets = goal_result.get(
                "datasets",
                [],
            )

            if not goal_result.get(
                "found"
            ) or not datasets:
                save_goal_dataset_match(
                    request_id=request_id,
                    goal_id=goal_id,
                    status="NOT_FOUND",
                    evidence_reason=(
                        goal_result.get(
                            "explanation"
                        )
                        or (
                            "No available dataset was "
                            "found for this goal."
                        )
                    ),
                )
                goals_not_found += 1
                continue

            goal_has_available_dataset = False
            goal_has_unavailable_candidate = False

            for dataset in datasets:
                availability = (
                    check_repository_source(
                        dataset["url"]
                    )
                )

                candidate = {
                    "provider": dataset.get(
                        "provider"
                    ),
                    "repository_name": (
                        dataset.get(
                            "repository_name"
                        )
                        or dataset.get(
                            "dataset_name"
                        )
                    ),
                    "url": dataset.get("url"),
                    "description": dataset.get(
                        "description"
                    ),
                    "dimension": goal_result.get(
                        "goal_name"
                    ),
                    "geography": dataset.get(
                        "geography"
                    ),
                    "data_format": dataset.get(
                        "data_format"
                    ),
                    "refresh_frequency": (
                        dataset.get(
                            "refresh_frequency"
                        )
                        or "Periodic check"
                    ),
                    "relevance_score": dataset.get(
                        "relevance_score"
                    ),
                }

                repository, state = (
                    compare_and_store_repository_candidate(
                        topic_id=topic_id,
                        request_id=request_id,
                        candidate=candidate,
                        availability=availability,
                    )
                )

                repository_id = int(
                    repository[
                        "repository_id"
                    ]
                )

                if (
                    repository_id
                    not in counted_repository_ids
                ):
                    counts[state] += 1
                    counted_repository_ids.add(
                        repository_id
                    )

                    create_repository_run(
                        repository_id=repository_id,
                        status=availability[
                            "status"
                        ],
                        changed=None,
                        content_hash=availability.get(
                            "content_hash"
                        ),
                        notes=(
                            "Availability check during "
                            "goal-by-goal dataset discovery. "
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
                        etag=availability.get(
                            "etag"
                        ),
                    )

                if availability[
                    "status"
                ] == "SUCCESS":
                    match_status = "FOUND"
                    goal_has_available_dataset = True
                else:
                    match_status = "UNAVAILABLE"
                    goal_has_unavailable_candidate = True

                save_goal_dataset_match(
                    request_id=request_id,
                    goal_id=goal_id,
                    repository_id=repository_id,
                    status=match_status,
                    dataset_name=dataset.get(
                        "dataset_name"
                    ),
                    dataset_url=dataset.get(
                        "url"
                    ),
                    provider=dataset.get(
                        "provider"
                    ),
                    geography=dataset.get(
                        "geography"
                    ),
                    data_format=dataset.get(
                        "data_format"
                    ),
                    evidence_reason=dataset.get(
                        "evidence_reason"
                    ),
                    availability_status=availability.get(
                        "status"
                    ),
                    http_status=availability.get(
                        "http_status"
                    ),
                )

            if goal_has_available_dataset:
                goals_found += 1
            elif goal_has_unavailable_candidate:
                goals_unavailable += 1
            else:
                goals_not_found += 1

        candidates_found = len(
            counted_repository_ids
        )

        complete_discovery_request(
            request_id=request_id,
            candidates_found=candidates_found,
            status="SUCCESS",
            notes=(
                f"Research goals: {len(goals)}. "
                f"Goals with available data: {goals_found}. "
                f"Goals without a dataset: {goals_not_found}. "
                f"Goals with only unreachable candidates: "
                f"{goals_unavailable}."
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
            "candidates_found": candidates_found,
            "new_count": counts["NEW"],
            "updated_count": counts[
                "UPDATED"
            ],
            "unchanged_count": counts[
                "UNCHANGED"
            ],
            "goals_total": len(goals),
            "goals_found": goals_found,
            "goals_not_found": goals_not_found,
            "goals_unavailable": goals_unavailable,
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
