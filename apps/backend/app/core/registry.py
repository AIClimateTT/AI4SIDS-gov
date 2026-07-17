from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec


class DataModule(Protocol):
    name: str

    def ingest(self, file_path: Path) -> IngestResult: ...

    def list_metrics(self) -> list[MetricSpec]: ...

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]: ...


_modules: dict[str, DataModule] = {}


def register_module(module: DataModule) -> None:
    if module.name in _modules:
        raise ValueError(f"data module already registered: {module.name}")
    _modules[module.name] = module


def get_module(name: str) -> DataModule | None:
    return _modules.get(name)


def list_modules() -> list[DataModule]:
    return list(_modules.values())


def reset_registry() -> None:
    _modules.clear()
