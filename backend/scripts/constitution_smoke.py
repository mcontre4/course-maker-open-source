"""Seed the reusable one-minute Constitution brief, without syllabus generation.

Run from backend: poetry run python scripts/constitution_smoke.py --env-file /path/to/.env
Then use the documented authenticated generation endpoints or the UI.
"""

import argparse
from pathlib import Path

from app.courses.composition import seed_constitution_smoke

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--database-url")
    parser.add_argument(
        "--reset-storyboard",
        action="store_true",
        help="Clear script/audio/animation for another paid smoke run; preserve plan and spend",
    )
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/constitution.json"))
    args = parser.parse_args()
    print(
        seed_constitution_smoke(
            args.env_file, args.fixture, args.database_url, args.reset_storyboard
        )
    )
