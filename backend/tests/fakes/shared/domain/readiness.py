from app.shared.domain.readiness import Readiness


class FixedReadinessProbe:
    def __init__(self, status: Readiness) -> None:
        self.result = status

    def status(self) -> Readiness:
        return self.result
