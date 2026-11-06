from app.core.template_catalog import get_template


def test_template_reads_only_survey123():
    template = get_template("survey123_summary")

    assert template is not None
    assert {r.module for r in template.data_requirements} == {"survey123"}


def test_only_the_dates_are_required():
    template = get_template("survey123_summary")

    assert {p.name for p in template.params if p.required} == {"date_from", "date_to"}
    assert "corporation" in {p.name for p in template.params}


def test_narration_is_kept():
    assert get_template("survey123_summary").narration.output_sections
