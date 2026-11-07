"""Grant credits to a snapshot of existing users, with an auditable, retry-safe batch ID."""

import argparse
import json

from app.credits.composition import grant_existing_user_credits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grant-id", required=True)
    parser.add_argument("--credits", type=int, default=1_000_000)
    parser.add_argument("--apply", action="store_true", help="Apply; otherwise preview only")
    args = parser.parse_args()
    print(json.dumps(grant_existing_user_credits(args.grant_id, args.credits, apply=args.apply)))


if __name__ == "__main__":
    main()
