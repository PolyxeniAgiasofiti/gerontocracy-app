"""
Monthly Gerontocracy Data Observatory repository discovery.

Render Cron command:
    python pipelines/monthly_observatory.py
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.observatory_db import (  # noqa: E402
    initialize_default_topic,
    initialize_observatory_database,
)
from src.observatory_workflow import (  # noqa: E402
    run_fresh_repository_discovery,
)


def main():
    initialize_observatory_database()

    topic = initialize_default_topic()

    if topic is None:
        raise RuntimeError(
            "Observatory topic could not be initialized."
        )

    result = run_fresh_repository_discovery(
        topic_id=int(
            topic["topic_id"]
        ),
        run_type="SCHEDULED",
    )

    print(
        "Scheduled Observatory discovery completed: "
        f"{result['candidates_found']} found, "
        f"{result['new_count']} new, "
        f"{result['updated_count']} updated, "
        f"{result['unchanged_count']} unchanged."
    )


if __name__ == "__main__":
    main()
