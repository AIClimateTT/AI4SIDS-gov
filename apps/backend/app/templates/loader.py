from pathlib import Path

import yaml

from app.core.contracts import Template


def load_template(path: Path) -> Template:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Template.model_validate(raw)


def load_templates_from_directory(directory: Path) -> list[Template]:
    return [load_template(p) for p in sorted(directory.glob("*.yaml"))]
