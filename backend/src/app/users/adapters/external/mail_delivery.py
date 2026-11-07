"""An expiring transactional outbox; SMTP runs after the claim transaction closes."""

import logging
from collections.abc import Callable
from threading import Event

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.shared.domain.clock import Clock
from app.users.adapters.persistence.authentication import (
    AccountActionRecord,
    AccountMailRecord,
    LoginSessionRecord,
)
from app.users.domain.authentication import AccountMail

logger = logging.getLogger(__name__)


class DeliverAccountMail:
    def __init__(
        self, sessions: sessionmaker[Session], clock: Clock, send: Callable[[AccountMail], None]
    ) -> None:
        self._sessions, self._clock, self._send = sessions, clock, send

    def deliver_one(self) -> bool:
        now = self._clock.now().timestamp()
        with self._sessions.begin() as session:
            for record in (AccountMailRecord, AccountActionRecord, LoginSessionRecord):
                session.execute(delete(record).where(record.expires_at <= now))
            row = session.scalar(
                select(AccountMailRecord)
                .where(
                    AccountMailRecord.available_at <= now,
                )
                .order_by(AccountMailRecord.available_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return False
            mail = AccountMail(row.id, row.recipient, row.subject, row.body, row.expires_at)
            row.attempts += 1
            # Lease survives crashes; failed delivery retries with bounded backoff.
            row.available_at = now + min(3600, 30 * 2 ** min(row.attempts, 7))
        try:
            self._send(mail)
        except Exception:
            # Do not log recipients, message bodies, tokens or SMTP credentials.
            logger.warning("Account email delivery failed; retry scheduled")
            return False
        with self._sessions.begin() as session:
            session.execute(delete(AccountMailRecord).where(AccountMailRecord.id == mail.id))
        return True

    def run(self, stop: Event) -> None:
        while not stop.is_set():
            try:
                if self.deliver_one():
                    continue
            except Exception:
                logger.warning("Account outbox unavailable; retry scheduled")
            stop.wait(2)
