"""
High-level workflow orchestration for the clarified Gerontocracy research flow.
"""

import json

from src.observatory_db import (
    compare_and_store_repository_candidate,
    complete_discovery_request,
    create_discovery_request,
    create_repository_run,
    create_research_question,
    get_latest_confirmed_plan,
    get_research_question,
    link_repository_to_research,
    load_repositories_for_research,
    save_generated_research_plan,
    save_requirement_dataset_match,
    update_repository_check_state,
)
from src.observatory_discovery import (
    analyse_research_question,
    discover_datasets_for_requirements,
    validate_research_question,
)
from src.observatory_refresh import (
    check_repository_source,
)


def start_research_question(
    topic_id,
    question_text,
):
    """
    Validate the user's research question.

    If accepted:
    - run the hidden AI analysis,
    - create the editable research plan,
    - persist the plan in PostgreSQL.
    """

    guardrail = validate_research_question(
        question_text
    )

    research = create_research_question(
        topic_id=topic_id,
        question_text=question_text.strip(),
        guardrail_status=guardrail["scope"],
        guardrail_reason=guardrail["reason"],
        guardrail_model=guardrail.get(
            "_model"
        ),
    )

    if not guardrail["accepted"]:
        return {
            "accepted": False,
            "research": research,
            "guardrail": guardrail,
            "analysis": None,
        }

    analysis = analyse_research_question(
        question_text
    )

    save_generated_research_plan(
        research_id=research[
            "research_id"
        ],
        plain_summary=analysis[
            "plain_summary"
        ],
        geographic_scope=analysis[
            "geographic_scope"
        ],
        factors=analysis[
            "factors"
        ],
    )

    research = get_research_question(
        research[
            "research_id"
        ]
    )

    return {
        "accepted": True,
        "research": research,
        "guardrail": guardrail,
        "analysis": analysis,
    }


def _check_existing_repositories(
    research_id,
):
    """
    Check repositories already associated with this research.

    This checks accessibility and HTTP metadata.

    It does not yet determine whether the statistical values inside a dataset
    changed. That belongs to the later ingestion/snapshot phase.
    """

    checked = 0
    unavailable = 0

    repositories = (
        load_repositories_for_research(
            research_id
        )
    )

    for repository in repositories:

        availability = (
            check_repository_source(
                repository["url"]
            )
        )

        update_repository_check_state(
            repository_id=repository[
                "repository_id"
            ],
            availability=availability,
        )

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
                "Existing-source re-check before fresh web discovery. "
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

        checked += 1

        if (
            availability[
                "status"
            ]
            != "SUCCESS"
        ):
            unavailable += 1

    return {
        "checked": checked,
        "unavailable": unavailable,
    }


def run_confirmed_research_search(
    topic_id,
    research_id,
    run_type="MANUAL",
):
    """
    Run the confirmed research plan.

    The recurring workflow has two separate branches:

    1. Re-check repositories already associated with the research.
    2. Perform a new web search from scratch for every confirmed data
       requirement.

    The existing repository registry is not supplied to Gemini or Tavily as
    the universe of possible sources.
    """

    research = get_research_question(
        research_id
    )

    if not research:
        raise RuntimeError(
            "Research question not found."
        )

    plan_version = (
        get_latest_confirmed_plan(
            research_id
        )
    )

    if not plan_version:
        raise RuntimeError(
            "Confirm the research plan before searching for data."
        )

    snapshot = plan_version[
        "snapshot_json"
    ]

    if isinstance(
        snapshot,
        str,
    ):
        snapshot = json.loads(
            snapshot
        )

    requirements = snapshot.get(
        "requirements",
        [],
    )

    if not requirements:
        raise RuntimeError(
            "The confirmed research plan contains no data requirements."
        )

    search_context = json.dumps(
        {
            "question": research[
                "question_text"
            ],
            "plan_version": plan_version[
                "version_number"
            ],
            "factors": snapshot.get(
                "factors",
                [],
            ),
            "categories": snapshot.get(
                "categories",
                [],
            ),
            "requirements": requirements,
        },
        ensure_ascii=False,
    )

    request = create_discovery_request(
        topic_id=topic_id,
        prompt=(
            "Fresh web discovery for the confirmed "
            "gerontocracy research plan."
        ),
        search_context=search_context,
        model=None,
        run_type=run_type,
        research_id=research_id,
        plan_version_id=plan_version[
            "plan_version_id"
        ],
    )

    request_id = int(
        request[
            "request_id"
        ]
    )

    try:
        # ---------------------------------------------------------------
        # A. Check repositories that are already linked to this research.
        # ---------------------------------------------------------------

        existing_check = (
            _check_existing_repositories(
                research_id
            )
        )

        # ---------------------------------------------------------------
        # B. Fresh web discovery from scratch.
        # ---------------------------------------------------------------

        discovery = (
            discover_datasets_for_requirements(
                research_question=research[
                    "question_text"
                ],
                plan_snapshot=snapshot,
                requirements=requirements,
            )
        )

        counts = {
            "NEW": 0,
            "UPDATED": 0,
            "UNCHANGED": 0,
        }

        counted_repository_ids = set()

        requirements_found = 0
        requirements_not_found = 0
        requirements_unavailable = 0

        for requirement_result in discovery[
            "requirement_results"
        ]:

            requirement_id = int(
                requirement_result[
                    "requirement_id"
                ]
            )

            datasets = (
                requirement_result.get(
                    "datasets",
                    [],
                )
            )

            # -----------------------------------------------------------
            # Nothing usable was found for this specific requirement.
            # -----------------------------------------------------------

            if (
                not requirement_result.get(
                    "found"
                )
                or not datasets
            ):
                save_requirement_dataset_match(
                    request_id=request_id,
                    requirement_id=requirement_id,
                    status="NOT_FOUND",
                    evidence_reason=(
                        requirement_result.get(
                            "explanation"
                        )
                        or (
                            "No available dataset was "
                            "found for this requirement."
                        )
                    ),
                )

                requirements_not_found += 1
                continue

            has_available = False
            has_unavailable = False

            # -----------------------------------------------------------
            # One requirement can have more than one useful dataset.
            # -----------------------------------------------------------

            for dataset in datasets:

                availability = (
                    check_repository_source(
                        dataset[
                            "url"
                        ]
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
                    "url": dataset.get(
                        "url"
                    ),
                    "description": dataset.get(
                        "description"
                    ),
                    "dimension": (
                        requirement_result.get(
                            "requirement_text"
                        )
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

                # -------------------------------------------------------
                # Compare the source with the PostgreSQL repository
                # registry and classify it as NEW / UPDATED / UNCHANGED.
                # -------------------------------------------------------

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

                # Associate this repository with the research question.
                link_repository_to_research(
                    research_id=research_id,
                    repository_id=repository_id,
                )

                # Count each repository only once per discovery execution,
                # even if it satisfies several data requirements.
                if (
                    repository_id
                    not in counted_repository_ids
                ):
                    counts[
                        state
                    ] += 1

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
                            "fresh requirement search. "
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

                if (
                    availability[
                        "status"
                    ]
                    == "SUCCESS"
                ):
                    match_status = (
                        "FOUND"
                    )

                    has_available = True

                else:
                    match_status = (
                        "UNAVAILABLE"
                    )

                    has_unavailable = True

                # -------------------------------------------------------
                # Persist:
                # requirement -> dataset -> repository relationship.
                # -------------------------------------------------------

                save_requirement_dataset_match(
                    request_id=request_id,
                    requirement_id=requirement_id,
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

            # -----------------------------------------------------------
            # Requirement-level coverage classification.
            # -----------------------------------------------------------

            if has_available:
                requirements_found += 1

            elif has_unavailable:
                requirements_unavailable += 1

            else:
                requirements_not_found += 1

        # ---------------------------------------------------------------
        # Mark discovery execution as successful.
        # ---------------------------------------------------------------

        complete_discovery_request(
            request_id=request_id,
            candidates_found=len(
                counted_repository_ids
            ),
            status="SUCCESS",
            notes=(
                f"Existing repositories checked: "
                f"{existing_check['checked']}; "
                f"existing unavailable: "
                f"{existing_check['unavailable']}; "
                f"requirements total: "
                f"{len(requirements)}; "
                f"with available data: "
                f"{requirements_found}; "
                f"not found: "
                f"{requirements_not_found}; "
                f"only unavailable candidates: "
                f"{requirements_unavailable}."
            ),
            new_count=counts[
                "NEW"
            ],
            updated_count=counts[
                "UPDATED"
            ],
            unchanged_count=counts[
                "UNCHANGED"
            ],
            model=discovery.get(
                "model"
            ),
        )

        return {
            "request_id": request_id,

            "existing_checked": (
                existing_check[
                    "checked"
                ]
            ),

            "existing_unavailable": (
                existing_check[
                    "unavailable"
                ]
            ),

            "requirements_total": len(
                requirements
            ),

            "requirements_found": (
                requirements_found
            ),

            "requirements_not_found": (
                requirements_not_found
            ),

            "requirements_unavailable": (
                requirements_unavailable
            ),

            "new_count": counts[
                "NEW"
            ],

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
            notes=str(
                exc
            ),
            new_count=0,
            updated_count=0,
            unchanged_count=0,
        )

        raise