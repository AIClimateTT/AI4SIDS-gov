import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import create_app
from app.db import Base, SessionLocal
from app.db import engine as db_engine
from app.prompts import registry
from app.prompts.models import PromptVersion
from app.prompts.stats import prompt_stats
from tests.test_api_capture import (
    EXTRACT_JSON,
    _SitrepAwareLLM,
    create_capture,
    create_event,
)

DEV_DB_PATH = Path(__file__).parent.parent / "dev.db"
MESSAGE = "5 houses flooded in Petit Valley. 200 sandbags remaining."


# --- the lock: a version names exactly one text ------------------------------


def test_prompts_in_this_checkout_match_the_lock():
    """If this fails you changed a prompt (or a list it pulls in from code).
    Bump its version, add a changelog entry, run `python -m app.cli prompts lock`."""
    assert registry.lock_problems() == []


@pytest.fixture
def prompt_copy(tmp_path, monkeypatch):
    """The real prompts, copied somewhere a test may edit them."""
    folder = tmp_path / "prompts"
    shutil.copytree(registry.PROMPTS_DIR / "corp_capture", folder / "corp_capture")
    lock = tmp_path / "prompts.lock.json"
    shutil.copy(registry.LOCK_PATH, lock)
    monkeypatch.setattr(registry, "PROMPTS_DIR", folder)
    return folder / "corp_capture", lock


def _bump(spec_path: Path, changelog: bool = True) -> int:
    """Raise the copy's version by one; returns the new version."""
    current = registry.load_spec("corp_capture").version
    version = current + 1
    text = spec_path.read_text().replace(f"version: {current}\n", f"version: {version}\n", 1)
    text = text.replace("changelog:\n", "changelog:\n" + (
        f"  - version: {version}\n    date: 2026-11-19\n    why: test\n" if changelog else ""
    ), 1)
    spec_path.write_text(text)
    return version


def test_editing_a_prompt_without_a_version_bump_is_caught(prompt_copy):
    folder, lock = prompt_copy
    rules = folder / "rules.txt"
    rules.write_text(rules.read_text() + "\n- A new rule.")

    problems = registry.lock_problems(lock)

    assert any("text changed but its version did not" in p for p in problems)
    with pytest.raises(ValueError, match="bump its version"):
        registry.write_lock(lock)


def test_a_bumped_version_with_a_changelog_entry_locks_cleanly(prompt_copy):
    folder, lock = prompt_copy
    (folder / "rules.txt").write_text((folder / "rules.txt").read_text() + "\n- A new rule.")
    version = _bump(folder / "prompt.yaml")

    assert registry.write_lock(lock) == [f"corp_capture@{version}"]
    assert registry.lock_problems(lock) == []
    locked = json.loads(lock.read_text())["corp_capture"]
    assert locked[str(version)] != locked[str(version - 1)]
    # The new version is frozen, so it can be re-run once the files move on.
    frozen = folder / "history" / f"v{version}.txt"
    assert registry.prompt_hash(frozen.read_text()) == locked[str(version)]


def test_a_new_version_needs_a_changelog_entry(prompt_copy):
    folder, lock = prompt_copy
    (folder / "rules.txt").write_text((folder / "rules.txt").read_text() + "\n- A new rule.")
    version = _bump(folder / "prompt.yaml", changelog=False)
    registry.write_lock(lock)

    assert any(f"changelog entry for version {version}" in p for p in registry.lock_problems(lock))


def test_a_frozen_version_may_not_be_edited(prompt_copy):
    folder, lock = prompt_copy
    frozen = folder / "history" / "v1.txt"
    frozen.write_text(frozen.read_text() + " edited")

    assert any("v1.txt was edited" in p for p in registry.lock_problems(lock))


def test_an_earlier_version_loads_from_its_frozen_text():
    v1 = registry.load_version("corp_capture", 1)

    assert v1.hash == registry.read_lock()["corp_capture"]["1"]
    assert v1.text != registry.current("corp_capture").text


def test_unknown_placeholder_is_an_error(prompt_copy):
    folder, _lock = prompt_copy
    (folder / "rules.txt").write_text("Types: {{no_such_list}}")

    with pytest.raises(ValueError, match="no_such_list"):
        registry.assemble("corp_capture")


def test_code_owned_lists_are_part_of_the_prompt():
    text = registry.assemble("corp_capture").text

    assert "{{" not in text
    assert "blown_off_roof" in text and "relief_distributed" in text


# --- what each turn records ---------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_db():
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()
    yield
    db_engine.dispose()
    if DEV_DB_PATH.exists():
        DEV_DB_PATH.unlink()


class _RecordingLLM(_SitrepAwareLLM):
    model_label = "test:recording"

    def __init__(self, responses):
        super().__init__(responses=responses)
        self.system_prompts: list[str] = []

    def generate(self, system_prompt, user_content):
        self.system_prompts.append(system_prompt)
        return super().generate(system_prompt, user_content)


def _client(monkeypatch, responses=None) -> tuple[TestClient, _RecordingLLM]:
    import app.modules.capture.models
    import app.modules.sitreps.models  # noqa: F401

    llm = _RecordingLLM(responses or [EXTRACT_JSON])
    monkeypatch.setattr("app.api.capture.get_llm_client", lambda purpose="batch": llm)
    Base.metadata.create_all(db_engine)
    return TestClient(create_app()), llm


def _session(client: TestClient) -> int:
    return create_capture(client, create_event(client))["id"]


def _turns(session_id: int):
    from app.modules.capture.models import CaptureTurn

    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(CaptureTurn)
                .where(CaptureTurn.session_id == session_id, CaptureTurn.kind == "turn")
                .order_by(CaptureTurn.seq)
            )
        )
    finally:
        db.close()


def test_each_turn_records_prompt_version_hash_and_model(monkeypatch):
    client, llm = _client(monkeypatch)
    session_id = _session(client)

    assert client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE}).status_code == 200

    current = registry.current("corp_capture")
    turn = _turns(session_id)[0]
    assert (turn.prompt_id, turn.prompt_version, turn.prompt_hash) == (
        "corp_capture",
        current.version,
        current.hash,
    )
    assert turn.model == "test:recording"
    assert llm.system_prompts[0] == current.text
    db = SessionLocal()
    try:
        stored = db.get(PromptVersion, current.hash)
        assert stored is not None and stored.text == current.text
    finally:
        db.close()


def test_a_session_keeps_its_prompt_across_a_deploy(monkeypatch):
    client, llm = _client(monkeypatch)
    session_id = _session(client)
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE})
    first = registry.current("corp_capture")

    newer = registry.Prompt("corp_capture", first.version + 1, "NEW RULES", registry.prompt_hash("NEW RULES"))
    monkeypatch.setattr(registry, "current", lambda prompt_id: newer)
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": "Also 3 trees down."})
    fresh = _session(client)
    client.post(f"/capture/sessions/{fresh}/turns", json={"message": MESSAGE})

    assert [t.prompt_version for t in _turns(session_id)] == [first.version, first.version]
    assert llm.system_prompts[1] == first.text
    assert _turns(fresh)[0].prompt_version == newer.version
    assert llm.system_prompts[-1] == "NEW RULES"


def test_override_runs_an_earlier_version_for_new_sessions(monkeypatch):
    client, llm = _client(monkeypatch)
    db = SessionLocal()
    old_text = "OLD RULES"
    db.add(
        PromptVersion(
            hash=registry.prompt_hash(old_text),
            prompt_id="corp_capture",
            version=0,
            text=old_text,
            created_at=registry.datetime(2026, 11, 1),
        )
    )
    db.commit()
    db.close()
    monkeypatch.setattr(registry.settings, "prompt_overrides", "corp_capture@0")

    session_id = _session(client)
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE})

    assert _turns(session_id)[0].prompt_version == 0
    assert llm.system_prompts[0] == old_text


def test_override_to_a_frozen_version_needs_no_database_history(monkeypatch):
    client, llm = _client(monkeypatch)
    monkeypatch.setattr(registry.settings, "prompt_overrides", "corp_capture@1")

    session_id = _session(client)
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE})

    assert _turns(session_id)[0].prompt_version == 1
    assert llm.system_prompts[0] == registry.load_version("corp_capture", 1).text


def test_guard_corrections_are_counted_per_turn(monkeypatch):
    invented = json.loads(EXTRACT_JSON)
    invented["capture"]["incidents"][0]["injuries_count"] = 7
    client, _llm = _client(monkeypatch, [json.dumps(invented)])
    session_id = _session(client)

    client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE})

    assert _turns(session_id)[0].interventions.get("invented_numbers") == 1


def test_stats_group_turns_by_prompt_version(monkeypatch):
    client, _llm = _client(monkeypatch, ["not json at all"])
    session_id = _session(client)
    client.post(f"/capture/sessions/{session_id}/turns", json={"message": MESSAGE})

    db = SessionLocal()
    try:
        stats = prompt_stats(db, "corp_capture")
    finally:
        db.close()

    assert len(stats) == 1
    row = stats[0]
    assert row.prompt_ref == f"corp_capture@{registry.current('corp_capture').version}"
    assert row.model == "test:recording"
    assert (row.turns, row.unreadable, row.retried) == (1, 1, 1)
