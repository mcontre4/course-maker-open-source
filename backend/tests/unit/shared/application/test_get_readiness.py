import pytest
from fakes.shared.domain.readiness import FixedReadinessProbe

from app.shared.application.get_readiness import GetReadiness, ReadinessRequest
from app.shared.domain.readiness import Readiness


@pytest.mark.parametrize(
    "database,cache,storage", [(True, True, True), (False, True, False), (True, False, False)]
)
def test_readiness_reports_each_injected_boundary(database, cache, storage):
    probe = FixedReadinessProbe(Readiness(database, cache, storage))
    result = GetReadiness(probe).execute(ReadinessRequest())
    assert (result.database, result.cache, result.storage_configured) == (database, cache, storage)
