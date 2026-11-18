"""Versioned prompts: what the model is told, kept apart from report layout.

Each prompt is a folder in app/prompts holding prompt.yaml (id, version,
changelog, parts) and plain-text part files. Lists that live in code (incident
types, log categories) are pulled in through {{placeholders}}, so they count
as part of the prompt too.

A version is pinned to the SHA-256 of its assembled text in prompts.lock.json.
tests/test_prompt_registry.py fails when the text changes without a version
bump, so a version number always names exactly one text. Every turn records
the prompt id, version and hash; prompt_versions keeps the text itself."""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.prompts.models import PromptVersion

PROMPTS_DIR = Path(__file__).parent
LOCK_PATH = PROMPTS_DIR / "prompts.lock.json"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
logger = logging.getLogger(__name__)


def _capture_variables() -> dict[str, str]:
    from app.modules.capture.prompt import prompt_variables

    return prompt_variables()


# Code-owned lists a prompt pulls in. Imported lazily: the modules that own
# them import this registry.
_VARIABLES: dict[str, Callable[[], dict[str, str]]] = {
    "corp_capture": _capture_variables,
}


@dataclass(frozen=True)
class ChangelogEntry:
    version: int
    date: str
    why: str
    evidence: str = ""


@dataclass(frozen=True)
class PromptSpec:
    id: str
    version: int
    description: str
    model_hint: str
    parts: tuple[str, ...]
    changelog: tuple[ChangelogEntry, ...]


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    text: str
    hash: str

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class DraftPrompt(Prompt):
    """Prompt text that is not a locked version: the working copy of the part
    files, sent to the eval runner to try before it is committed. Never
    recorded on a turn."""

    @property
    def ref(self) -> str:
        return f"{self.id}@draft-{self.hash[:8]}"


def draft_prompt(prompt_id: str, text: str) -> DraftPrompt:
    return DraftPrompt(id=prompt_id, version=0, text=text, hash=prompt_hash(text))


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_ids() -> list[str]:
    return sorted(path.parent.name for path in PROMPTS_DIR.glob("*/prompt.yaml"))


def load_spec(prompt_id: str) -> PromptSpec:
    folder = PROMPTS_DIR / prompt_id
    raw = yaml.safe_load((folder / "prompt.yaml").read_text(encoding="utf-8"))
    if raw.get("id") != prompt_id:
        raise ValueError(f"{folder}/prompt.yaml: id {raw.get('id')!r} != folder {prompt_id!r}")
    return PromptSpec(
        id=raw["id"],
        version=int(raw["version"]),
        description=raw.get("description", ""),
        model_hint=raw.get("model_hint", ""),
        parts=tuple(raw["parts"]),
        changelog=tuple(
            ChangelogEntry(
                version=int(entry["version"]),
                date=str(entry.get("date", "")),
                why=entry.get("why", ""),
                evidence=entry.get("evidence", ""),
            )
            for entry in raw.get("changelog") or []
        ),
    )


def _fill(text: str, variables: dict[str, str], source: str) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise ValueError(f"{source}: unknown placeholder {{{{{name}}}}}")
        return variables[name]

    return _PLACEHOLDER.sub(replace, text)


def assemble(prompt_id: str) -> Prompt:
    """The prompt as the files in this checkout define it."""
    spec = load_spec(prompt_id)
    provider = _VARIABLES.get(prompt_id)
    variables = provider() if provider else {}
    folder = PROMPTS_DIR / prompt_id
    parts = [
        _fill((folder / name).read_text(encoding="utf-8"), variables, f"{prompt_id}/{name}").strip()
        for name in spec.parts
    ]
    text = "\n\n".join(part for part in parts if part)
    return Prompt(id=spec.id, version=spec.version, text=text, hash=prompt_hash(text))


@cache
def current(prompt_id: str) -> Prompt:
    return assemble(prompt_id)


def history_path(prompt_id: str, version: int) -> Path:
    """A locked version's assembled text, frozen so it can be re-run (eval,
    rollback) after the part files have moved on."""
    return PROMPTS_DIR / prompt_id / "history" / f"v{version}.txt"


def load_version(prompt_id: str, version: int | None = None) -> Prompt:
    """A prompt by version: the current files, or a frozen earlier version."""
    latest = assemble(prompt_id)
    if version is None or version == latest.version:
        return latest
    path = history_path(prompt_id, version)
    if not path.exists():
        raise ValueError(f"{prompt_id}@{version} has no frozen text at {path}")
    text = path.read_text(encoding="utf-8")
    return Prompt(id=prompt_id, version=version, text=text, hash=prompt_hash(text))


# --- lock file -------------------------------------------------------------


def read_lock(path: Path = LOCK_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lock_problems(path: Path = LOCK_PATH) -> list[str]:
    """Why the prompts in this checkout do not match the lock, if they don't."""
    lock = read_lock(path)
    problems: list[str] = []
    for prompt_id in prompt_ids():
        spec = load_spec(prompt_id)
        prompt = assemble(prompt_id)
        if not any(entry.version == spec.version for entry in spec.changelog):
            problems.append(
                f"{prompt.ref}: add a changelog entry for version {spec.version} "
                "in prompt.yaml saying what changed and why"
            )
        locked = lock.get(prompt_id, {}).get(str(spec.version))
        if locked is None:
            problems.append(
                f"{prompt.ref} is not in prompts.lock.json; run `python -m app.cli prompts lock`"
            )
        elif locked != prompt.hash:
            problems.append(
                f"{prompt.ref} text changed but its version did not. Bump `version` in "
                f"app/prompts/{prompt_id}/prompt.yaml, add a changelog entry, then run "
                "`python -m app.cli prompts lock`"
            )
        for version, locked_hash in lock.get(prompt_id, {}).items():
            frozen = history_path(prompt_id, int(version))
            if not frozen.exists():
                problems.append(
                    f"{prompt_id}@{version}: frozen text missing at {frozen.relative_to(PROMPTS_DIR)};"
                    " run `python -m app.cli prompts lock`"
                )
            elif prompt_hash(frozen.read_text(encoding="utf-8")) != locked_hash:
                problems.append(
                    f"{prompt_id}@{version}: {frozen.name} was edited; a locked version never changes"
                )
        newer = [int(v) for v in lock.get(prompt_id, {}) if int(v) > spec.version]
        if newer:
            problems.append(
                f"{prompt_id}: version went backwards ({spec.version} < locked {max(newer)})"
            )
    return problems


def write_lock(path: Path = LOCK_PATH) -> list[str]:
    """Add every current version to the lock. A version already locked to a
    different text is refused: that edit needs a new version number."""
    lock = read_lock(path)
    added: list[str] = []
    for prompt_id in prompt_ids():
        prompt = assemble(prompt_id)
        versions = lock.setdefault(prompt_id, {})
        locked = versions.get(str(prompt.version))
        if locked is not None and locked != prompt.hash:
            raise ValueError(
                f"{prompt.ref} is already locked to a different text; bump its version"
            )
        frozen = history_path(prompt_id, prompt.version)
        if not frozen.exists():
            frozen.parent.mkdir(exist_ok=True)
            frozen.write_text(prompt.text, encoding="utf-8")
        if locked is None:
            versions[str(prompt.version)] = prompt.hash
            added.append(prompt.ref)
    ordered = {
        pid: dict(sorted(versions.items(), key=lambda item: int(item[0])))
        for pid, versions in sorted(lock.items())
    }
    path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    return added


# --- what a call actually uses ----------------------------------------------


def _overrides() -> dict[str, int]:
    """PROMPT_OVERRIDES=corp_capture@1,other@3 runs an earlier version, e.g. to
    roll back or to compare on staging. Applies to new sessions only."""
    out: dict[str, int] = {}
    for item in (settings.prompt_overrides or "").split(","):
        item = item.strip()
        if not item:
            continue
        prompt_id, _, version = item.partition("@")
        if version.isdigit():
            out[prompt_id.strip()] = int(version)
    return out


def _from_row(row: PromptVersion) -> Prompt:
    return Prompt(id=row.prompt_id, version=row.version, text=row.text, hash=row.hash)


def record(db: Session, prompt: Prompt) -> None:
    """Keep the text of a prompt that is about to be sent. Flushed, not
    committed: it lands with the turn that used it."""
    if db.get(PromptVersion, prompt.hash) is None:
        db.add(
            PromptVersion(
                hash=prompt.hash,
                prompt_id=prompt.id,
                version=prompt.version,
                text=prompt.text,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.flush()


def resolve(db: Session, prompt_id: str, pinned_hash: str | None = None) -> Prompt:
    """The prompt a call should use.

    A session pinned to a hash keeps that text, so a deploy mid-conversation
    does not mix two rule sets in one transcript. Otherwise an override from
    PROMPT_OVERRIDES, else the current files. Whatever is chosen is recorded."""
    if pinned_hash:
        row = db.get(PromptVersion, pinned_hash)
        if row is not None:
            return _from_row(row)
    wanted = _overrides().get(prompt_id)
    latest = current(prompt_id)
    if wanted is not None and wanted != latest.version:
        if history_path(prompt_id, wanted).exists():
            chosen = load_version(prompt_id, wanted)
            record(db, chosen)
            return chosen
        row = db.scalars(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id, PromptVersion.version == wanted)
            .order_by(PromptVersion.created_at.desc())
        ).first()
        if row is not None:
            return _from_row(row)
        logger.warning(
            "PROMPT_OVERRIDES asks for %s@%s, which is neither frozen nor recorded; using %s",
            prompt_id,
            wanted,
            latest.ref,
        )
    record(db, latest)
    return latest
