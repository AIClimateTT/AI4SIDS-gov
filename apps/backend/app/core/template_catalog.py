"""Report templates are YAML files in app/templates/definitions.

The developer changes them in code and bumps `version:`; git is the history.
Each report records the template name and version that created it.
"""

import re
from functools import lru_cache
from pathlib import Path

from app.core.contracts import Template
from app.core.registry import ensure_default_modules_registered, get_module
from app.templates.loader import load_template

DEFINITIONS_DIR = Path(__file__).parent.parent / "templates" / "definitions"
PLACEHOLDER_RE = re.compile(r"^\{(\w+)\}$")


def validate_template(template: Template) -> None:
    ensure_default_modules_registered()
    param_names = {p.name for p in template.params}

    for requirement in template.data_requirements:
        module = get_module(requirement.module)
        if module is None:
            raise ValueError(f"unknown data module: {requirement.module}")
        metric_names = {spec.name for spec in module.list_metrics()}
        if requirement.metric not in metric_names:
            raise ValueError(
                f"unknown metric {requirement.metric!r} for module {requirement.module!r}"
            )
        for value in requirement.params.values():
            if isinstance(value, str):
                match = PLACEHOLDER_RE.match(value)
                if match and match.group(1) not in param_names:
                    raise ValueError(
                        f"data requirement param placeholder {{{match.group(1)}}} "
                        f"is not declared in template params"
                    )


def load_catalog(directory: Path) -> dict[str, Template]:
    catalog: dict[str, Template] = {}
    for path in sorted(directory.glob("*.yaml")):
        template = load_template(path)
        try:
            validate_template(template)
        except ValueError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        catalog[template.name] = template
    return catalog


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Template]:
    return load_catalog(DEFINITIONS_DIR)


def get_template(name: str) -> Template | None:
    return _catalog().get(name)


def list_templates() -> list[Template]:
    return sorted(_catalog().values(), key=lambda template: template.name)
