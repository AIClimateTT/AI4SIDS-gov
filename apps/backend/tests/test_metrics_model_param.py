import inspect

from app.modules.survey123.metrics import (
    METRIC_FUNCTIONS,
    base_query,
    column_exists,
    record_ref_of,
)
from app.modules.survey123.models import FieldObservation
from app.modules.sitreps.models import SitrepIncident


def test_every_metric_accepts_a_model_parameter():
    for name, fn in METRIC_FUNCTIONS.items():
        params = list(inspect.signature(fn).parameters)
        assert params[:3] == ["params", "session", "model"], (
            f"{name} does not take (params, session, model)"
        )


def test_model_defaults_to_field_observation_so_existing_callers_are_unaffected():
    for name, fn in METRIC_FUNCTIONS.items():
        default = inspect.signature(fn).parameters["model"].default
        assert default is FieldObservation, f"{name} has the wrong default model"


def test_column_exists_reports_real_columns_only():
    assert column_exists(FieldObservation, "validation_status") is True
    assert column_exists(FieldObservation, "is_duplicate") is True
    assert column_exists(FieldObservation, "not_a_column") is False


def test_column_exists_rejects_a_property_that_hasattr_would_wrongly_accept():
    # SitrepIncident.record_ref is a Python @property, not a mapped column.
    # hasattr() would say True and then the value would blow up in SQL. This
    # pins column_exists to the __table__.columns check, not hasattr().
    assert hasattr(SitrepIncident, "record_ref") is True
    assert column_exists(SitrepIncident, "record_ref") is False


def test_base_query_selects_from_the_given_model():
    stmt = base_query({}, FieldObservation)

    assert "field_observations" in str(stmt)


def test_record_ref_of_falls_back_to_empty_string_for_blank_global_id():
    # A blank GlobalID cell in a Survey123 export must degrade to an empty
    # citation reference, not crash report generation (FieldObservation has no
    # record_ref attribute at all).
    row = FieldObservation(global_id="")

    assert record_ref_of(row) == ""


def test_record_ref_of_uses_record_ref_for_models_without_global_id():
    row = SitrepIncident(corporation="TTEC", event_id=None, row_id="7")

    assert record_ref_of(row) == "TTEC:-:7"
