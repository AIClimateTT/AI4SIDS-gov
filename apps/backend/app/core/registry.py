from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec, Template


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


_templates: dict[str, Template] = {}


def register_template(template: Template) -> None:
    if template.name in _templates:
        raise ValueError(f"template already registered: {template.name}")
    _templates[template.name] = template


def get_template(name: str) -> Template | None:
    return _templates.get(name)


def list_templates() -> list[Template]:
    return list(_templates.values())


def reset_template_registry() -> None:
    _templates.clear()
