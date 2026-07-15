import pytest

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template
from app.core.registry import get_template, list_templates, register_template, reset_template_registry


def make_template(name: str = "test_template") -> Template:
    return Template(
        name=name,
        title="Test",
        description="test",
        params=[],
        data_requirements=[DataRequirement(module="survey123", metric="incident_count")],
        narration=NarrationConfig(system_prompt="p", output_sections=[]),
        render=RenderConfig(),
    )


@pytest.fixture(autouse=True)
def _clean_template_registry():
    reset_template_registry()
    yield
    reset_template_registry()


def test_register_and_get_template():
    template = make_template()

    register_template(template)

    assert get_template("test_template") is template


def test_get_unregistered_template_returns_none():
    assert get_template("does_not_exist") is None


def test_list_templates_reflects_registrations():
    assert list_templates() == []

    register_template(make_template())

    assert [t.name for t in list_templates()] == ["test_template"]


def test_register_duplicate_template_name_raises():
    register_template(make_template())

    with pytest.raises(ValueError, match="test_template"):
        register_template(make_template())
