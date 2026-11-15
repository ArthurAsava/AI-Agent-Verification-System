"""Bootstrap an active verification administrator from an existing user UUID.

Run only as a trusted backend maintenance action. The UUID must belong to an
existing SalesMesh agent; this script deliberately does not accept an email or
handle credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal
from app.models.entities import Agent, AuditLog
from app.models.reviewer import Reviewer


def bootstrap_admin(user_id: UUID) -> None:
    with SessionLocal() as db:
        agent = db.execute(
            select(Agent).where(Agent.user_id == user_id)
        ).scalar_one_or_none()
        if agent is None:
            raise ValueError(
                "The supplied user does not have a SalesMesh agent profile."
            )

        reviewer = db.get(Reviewer, user_id)
        if reviewer is None:
            reviewer = Reviewer(
                user_id=user_id,
                is_active=True,
                is_admin=True,
            )
            db.add(reviewer)
        else:
            reviewer.is_active = True
            reviewer.is_admin = True

        db.add(
            AuditLog(
                agent_id=agent.id,
                actor_user_id=user_id,
                action="verification_administrator_bootstrapped",
                details={"user_id": str(user_id)},
            )
        )
        db.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap a SalesMesh verification administrator."
    )
    parser.add_argument(
        "--user-id",
        required=True,
        type=UUID,
        help="Existing Supabase Auth user UUID with an agent profile.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        bootstrap_admin(parse_args().user_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print("Verification administrator access is active.")
