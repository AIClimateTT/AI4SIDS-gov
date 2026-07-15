from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec
from app.core.registry import get_module, list_modules, register_module, reset_registry


class FakeModule:
    name = "fake_module"

    def ingest(self, file_path: Path) -> IngestResult:
        return IngestResult(
            rows_read=0,
            rows_inserted=0,
            rows_updated=0,
            duplicates_flagged=0,
            unmapped_values={},
            pii_columns_dropped=[],
        )

    def list_metrics(self) -> list[MetricSpec]:
        return []

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        return []


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


def test_register_and_get_module():
    module = FakeModule()

    register_module(module)

    assert get_module("fake_module") is module


def test_get_unregistered_module_returns_none():
    assert get_module("does_not_exist") is None


def test_list_modules_reflects_registrations():
    assert list_modules() == []

    register_module(FakeModule())

    assert [m.name for m in list_modules()] == ["fake_module"]


def test_register_duplicate_name_raises():
    register_module(FakeModule())

    with pytest.raises(ValueError, match="fake_module"):
        register_module(FakeModule())
