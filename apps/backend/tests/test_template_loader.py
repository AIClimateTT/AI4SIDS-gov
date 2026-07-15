from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.templates.loader import load_template, load_templates_from_directory


def test_template_param_defaults_to_not_required():
    param = TemplateParam(name="community")

    assert param.required is False


def test_data_requirement_defaults_to_empty_params():
    req = DataRequirement(module="survey123", metric="incident_count")

    assert req.params == {}


def test_render_config_defaults():
    config = RenderConfig()

    assert config.format == "markdown"
    assert config.include_citation_appendix is True


def make_minimal_template_dict() -> dict:
    return {
        "name": "test_template",
        "title": "Test Template",
        "description": "A template for testing",
        "params": [{"name": "date_from", "required": True}],
        "data_requirements": [
            {"module": "survey123", "metric": "incident_count", "params": {"date_from": "{date_from}"}}
        ],
        "narration": {
            "system_prompt": "You are a test narrator.",
            "output_sections": ["headline"],
        },
        "render": {"format": "markdown", "include_citation_appendix": True},
    }


def test_template_validates_from_dict():
    template = Template.model_validate(make_minimal_template_dict())

    assert template.name == "test_template"
    assert template.params[0].name == "date_from"
    assert template.params[0].required is True
    assert template.data_requirements[0].module == "survey123"
    assert template.narration.output_sections == ["headline"]


def test_template_rejects_missing_required_field():
    raw = make_minimal_template_dict()
    del raw["narration"]

    with pytest.raises(ValidationError):
        Template.model_validate(raw)


def test_load_template_reads_and_validates_yaml_file(tmp_path):
    yaml_path = tmp_path / "test_template.yaml"
    yaml_path.write_text(
        """
name: test_template
title: Test Template
description: A template for testing
params:
  - name: date_from
    required: true
  - name: date_to
    required: true
data_requirements:
  - module: survey123
    metric: incident_count
    params: { date_from: "{date_from}", date_to: "{date_to}" }
narration:
  system_prompt: |
    You are a test narrator.
  output_sections: [headline]
render:
  format: markdown
  include_citation_appendix: true
"""
    )

    template = load_template(yaml_path)

    assert template.name == "test_template"
    assert len(template.params) == 2
    assert template.data_requirements[0].params == {"date_from": "{date_from}", "date_to": "{date_to}"}


def test_load_templates_from_directory_loads_all_yaml_files(tmp_path):
    (tmp_path / "a.yaml").write_text(
        """
name: template_a
title: A
description: d
params: []
data_requirements: []
narration:
  system_prompt: p
  output_sections: []
render: {}
"""
    )
    (tmp_path / "b.yaml").write_text(
        """
name: template_b
title: B
description: d
params: []
data_requirements: []
narration:
  system_prompt: p
  output_sections: []
render: {}
"""
    )

    templates = load_templates_from_directory(tmp_path)

    assert sorted(t.name for t in templates) == ["template_a", "template_b"]


def test_load_templates_from_directory_empty_directory_returns_empty_list(tmp_path):
    assert load_templates_from_directory(tmp_path) == []
