from sqlalchemy.orm import sessionmaker

from app.core.contracts import DataRequirement, NarrationConfig, RenderConfig, Template, TemplateParam
from app.core.template_store import (
    create_template_version,
    get_latest_template_version,
    get_template_version,
    list_latest_templates,
)
from app.db import Base, make_engine


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_template(name="single_region_report", **overrides) -> Template:
    defaults = dict(
        name=name,
        title="Single Region Deep Dive",
        description="test",
        params=[TemplateParam(name="corporation", required=True)],
        data_requirements=[DataRequirement(module="survey123", metric="incident_count")],
        narration=NarrationConfig(system_prompt="p", output_sections=["headline"]),
        render=RenderConfig(),
    )
    defaults.update(overrides)
    return Template(**defaults)


def test_create_template_version_starts_at_one(tmp_path):
    session = make_session(tmp_path)

    stored = create_template_version(make_template(), session)

    assert stored.version == 1


def test_create_template_version_increments_for_same_name(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)

    stored = create_template_version(make_template(title="Updated title"), session)

    assert stored.version == 2
    assert stored.title == "Updated title"


def test_create_template_version_is_independent_per_name(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(name="template_a"), session)

    stored = create_template_version(make_template(name="template_b"), session)

    assert stored.version == 1


def test_get_latest_template_version_returns_highest_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)
    create_template_version(make_template(title="v2 title"), session)

    latest = get_latest_template_version("single_region_report", session)

    assert latest is not None
    assert latest.version == 2
    assert latest.title == "v2 title"


def test_get_latest_template_version_returns_none_for_unknown_name(tmp_path):
    session = make_session(tmp_path)

    assert get_latest_template_version("does_not_exist", session) is None


def test_get_template_version_returns_frozen_historical_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(), session)
    create_template_version(make_template(title="v2 title"), session)

    v1 = get_template_version("single_region_report", 1, session)

    assert v1 is not None
    assert v1.title == "Single Region Deep Dive"


def test_list_latest_templates_returns_one_entry_per_name_at_highest_version(tmp_path):
    session = make_session(tmp_path)
    create_template_version(make_template(name="template_a"), session)
    create_template_version(make_template(name="template_a", title="a v2"), session)
    create_template_version(make_template(name="template_b"), session)

    templates = list_latest_templates(session)

    assert [(t.name, t.version, t.title) for t in templates] == [
        ("template_a", 2, "a v2"),
        ("template_b", 1, "Single Region Deep Dive"),
    ]
