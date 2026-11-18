"""Score a prompt version against a fixed set of officer messages.

Cases live in evals/<prompt_id>/cases.yaml, taken from UAT transcripts. Each
case is one officer message, optionally on top of a working set and chat
history, with checks on what the full capture pipeline (model plus guards
plus questions) produced. Running the same cases against two versions, on
the same model, is how a prompt change is shown to help before officers see
it.

Checks look for properties, not an exact reply, because a model phrases
things differently every run. Run each case a few times (--repeat): a check
that passes 2 of 3 times is a weak rule, not a pass.

Value specs in checks:
  plain string    case-insensitive "contains" ("flooding" matches "flooding_")
  number/bool/null  equality
  {is: v}         exact equality
  {present: true} not null or empty ({present: false}: null or empty)
  {any_of: [...]} any of the specs
  {not: spec}     the spec does not match
  "{today}", "{yesterday}"  the case's today, or the day before"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from app.core.llm import LLMClient, model_label
from app.modules.capture.schemas import CaptureMessage, CaptureWorkingSet
from app.modules.capture.turn import run_turn
from app.prompts.registry import Prompt

EVALS_DIR = Path(__file__).resolve().parent.parent.parent / "evals"


@dataclass
class Case:
    id: str
    message: str
    today: date
    checks: list[dict]
    source: str = ""
    prior: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class RunResult:
    parse_ok: bool
    seconds: float
    assistant_message: str
    questions: list[str]
    interventions: dict[str, int]
    checks: list[CheckResult]
    working: dict
    error: str | None = None


def load_cases(prompt_id: str, path: Path | None = None) -> list[Case]:
    path = path or EVALS_DIR / prompt_id / "cases.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cases_from_items(raw["cases"])


def cases_from_items(items: list[dict]) -> list[Case]:
    """Cases from their YAML/JSON form: the test set file, or inline cases
    sent to the eval runner to try once before they are committed."""
    cases = []
    for item in items:
        missing = [key for key in ("id", "message", "today", "checks") if key not in item]
        if missing:
            raise ValueError(f"case {item.get('id', '?')!r} is missing {missing}")
        today = item["today"]
        cases.append(
            Case(
                id=item["id"],
                message=item["message"],
                today=today if isinstance(today, date) else date.fromisoformat(str(today)),
                checks=item["checks"],
                source=item.get("source", ""),
                prior=item.get("prior") or {},
                history=item.get("history") or [],
            )
        )
    ids = [case.id for case in cases]
    duplicates = {case_id for case_id in ids if ids.count(case_id) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids: {sorted(duplicates)}")
    return cases


# --- matching -----------------------------------------------------------------


def _resolve(spec: object, today: date) -> object:
    if spec == "{today}":
        return today.isoformat()
    if spec == "{yesterday}":
        return (today - timedelta(days=1)).isoformat()
    return spec


def matches(actual: object, spec: object, today: date) -> bool:
    spec = _resolve(spec, today)
    if isinstance(spec, dict):
        if "present" in spec:
            present = actual not in (None, "", [], {})
            return present == bool(spec["present"])
        if "is" in spec:
            return actual == _resolve(spec["is"], today)
        if "any_of" in spec:
            return any(matches(actual, option, today) for option in spec["any_of"])
        if "not" in spec:
            return not matches(actual, spec["not"], today)
        raise ValueError(f"unknown spec {spec!r}")
    if isinstance(spec, str):
        return actual is not None and spec.lower() in str(actual).lower()
    if isinstance(spec, bool) or spec is None:
        return actual is spec
    if isinstance(spec, (int, float)):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == spec
    return actual == spec


def _row_matches(row: dict, where: dict, today: date) -> bool:
    return all(matches(row.get(key), spec, today) for key, spec in where.items())


def _row_failures(row: dict, expect: dict, today: date) -> list[str]:
    return [
        f"{key}={row.get(key)!r}"
        for key, spec in expect.items()
        if not matches(row.get(key), spec, today)
    ]


def _check_name(check: dict) -> str:
    if check.get("name"):
        return check["name"]
    parts = [check["kind"]]
    for key in ("rows", "path", "about"):
        if key in check:
            parts.append(str(check[key]))
    if check.get("where"):
        parts.append(",".join(f"{k}~{v}" for k, v in check["where"].items()))
    if check.get("expect"):
        parts.append("→ " + ",".join(check["expect"]))
    return " ".join(parts)


def evaluate(check: dict, working: dict, questions: list[str], parse_ok: bool, today: date) -> CheckResult:
    kind = check["kind"]
    name = _check_name(check)
    rows = working.get(check.get("rows", "incidents")) or []
    where = check.get("where") or {}
    selected = [row for row in rows if _row_matches(row, where, today)]
    if kind == "parsed":
        return CheckResult(name, parse_ok)
    if kind == "any":
        # Either of two right answers, e.g. "assessments ongoing" as the
        # present activity or as an activity log.
        results = [evaluate(sub, working, questions, parse_ok, today) for sub in check["checks"]]
        ok = any(result.passed for result in results)
        return CheckResult(name, ok, "" if ok else " / ".join(r.detail or r.name for r in results))
    if kind == "field":
        actual = working.get(check["path"])
        ok = matches(actual, check["expect"], today)
        return CheckResult(name, ok, "" if ok else f"{check['path']}={actual!r}")
    if kind == "count":
        ok = len(selected) == check["equals"]
        return CheckResult(name, ok, "" if ok else f"found {len(selected)}")
    if kind == "row":
        if not selected:
            return CheckResult(name, False, "no matching row")
        failures = _row_failures(selected[0], check.get("expect") or {}, today)
        return CheckResult(name, not failures, "; ".join(failures))
    if kind == "every":
        failures = [
            f"row {row.get('row_id')}: {'; '.join(bad)}"
            for row in selected
            if (bad := _row_failures(row, check.get("expect") or {}, today))
        ]
        return CheckResult(name, not failures, " | ".join(failures))
    if kind == "none":
        ok = not selected
        return CheckResult(name, ok, "" if ok else f"{len(selected)} matching rows")
    if kind == "asks":
        ok = any(matches(question, check["about"], today) for question in questions)
        return CheckResult(name, ok, "" if ok else f"asked {questions!r}")
    raise ValueError(f"unknown check kind {kind!r}")


# --- running ------------------------------------------------------------------


def _history(case: Case) -> list[CaptureMessage]:
    stamp = datetime(case.today.year, case.today.month, case.today.day, tzinfo=UTC)
    return [
        CaptureMessage(role=item["role"], content=item["content"], created_at=stamp)
        for item in case.history
    ]


def run_case(case: Case, prompt: Prompt, llm: LLMClient) -> RunResult:
    working = CaptureWorkingSet.model_validate(case.prior)
    started = time.monotonic()
    try:
        done = run_turn(
            working,
            _history(case),
            case.message,
            llm,
            system_prompt=prompt.text,
            today=case.today,
        )
    except Exception as exc:  # noqa: BLE001 - a model or network failure fails the case, not the run
        return RunResult(
            parse_ok=False,
            seconds=round(time.monotonic() - started, 2),
            assistant_message="",
            questions=[],
            interventions={},
            checks=[CheckResult(_check_name(check), False, "run failed") for check in case.checks],
            working={},
            error=f"{type(exc).__name__}: {exc}",
        )
    seconds = round(time.monotonic() - started, 2)
    out = done.working.model_dump(mode="json")
    return RunResult(
        parse_ok=done.parse_ok,
        seconds=seconds,
        assistant_message=done.assistant_message,
        questions=done.questions,
        interventions=done.interventions,
        checks=[evaluate(check, out, done.questions, done.parse_ok, case.today) for check in case.checks],
        working=out,
    )


def run_eval(
    prompt: Prompt,
    llm: LLMClient,
    cases: list[Case],
    repeat: int = 1,
    progress=None,
) -> dict:
    results = []
    for case in cases:
        runs = []
        for attempt in range(repeat):
            run = run_case(case, prompt, llm)
            runs.append(run)
            if progress:
                passed = sum(check.passed for check in run.checks)
                progress(f"{case.id} [{attempt + 1}/{repeat}] {passed}/{len(run.checks)} checks, {run.seconds}s")
        results.append({"id": case.id, "source": case.source, "runs": [asdict(run) for run in runs]})
    return {
        "prompt": prompt.ref,
        "prompt_hash": prompt.hash,
        "model": model_label(llm),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repeat": repeat,
        "cases": results,
        "summary": summarize(results),
    }


def summarize(results: list[dict]) -> dict:
    total = passed = runs = parsed = 0
    by_check: dict[str, list[int]] = {}
    by_case: dict[str, str] = {}
    corrections: dict[str, int] = {}
    seconds: list[float] = []
    for case in results:
        case_total = case_passed = 0
        for run in case["runs"]:
            runs += 1
            parsed += bool(run["parse_ok"])
            seconds.append(run["seconds"])
            for name, count in run["interventions"].items():
                corrections[name] = corrections.get(name, 0) + count
            for check in run["checks"]:
                key = f"{case['id']}: {check['name']}"
                tally = by_check.setdefault(key, [0, 0])
                tally[0] += check["passed"]
                tally[1] += 1
                case_total += 1
                case_passed += check["passed"]
        total += case_total
        passed += case_passed
        by_case[case["id"]] = f"{case_passed}/{case_total}"
    return {
        "checks_passed": passed,
        "checks_total": total,
        "pass_rate": round(passed / total, 3) if total else None,
        "parse_rate": round(parsed / runs, 3) if runs else None,
        "median_seconds": sorted(seconds)[len(seconds) // 2] if seconds else None,
        "guard_corrections": corrections,
        "by_case": by_case,
        "by_check": {key: f"{p}/{n}" for key, (p, n) in by_check.items()},
    }


def result_path(result: dict, out_dir: Path) -> Path:
    model = result["model"].replace("/", "_").replace(":", "_")
    stamp = result["run_at"].replace(":", "").replace("-", "")[:13]
    return out_dir / f"{result['prompt'].replace('@', '@v')}__{model}__{stamp}.json"


def save_result(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = result_path(result, out_dir)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def summary_lines(result: dict) -> list[str]:
    summary = result["summary"]
    lines = [
        f"{result['prompt']} on {result['model']} ×{result['repeat']}",
        (
            f"  checks passed  {summary['checks_passed']}/{summary['checks_total']}"
            f"  ({summary['pass_rate']:.0%})"
        ),
        f"  replies parsed {summary['parse_rate']:.0%}   median {summary['median_seconds']}s per turn",
    ]
    if summary["guard_corrections"]:
        lines.append(
            "  guard corrections: "
            + ", ".join(f"{k} {v}" for k, v in sorted(summary["guard_corrections"].items()))
        )
    failing = [
        f"    {key}  {score}"
        for key, score in summary["by_check"].items()
        if score.split("/")[0] != score.split("/")[1]
    ]
    if failing:
        lines += ["  not always passing:", *failing]
    return lines


def compare_lines(before: dict, after: dict) -> list[str]:
    a, b = before["summary"], after["summary"]
    lines = [
        f"{before['prompt']} ({before['model']})  →  {after['prompt']} ({after['model']})",
    ]
    if before["model"] != after["model"]:
        lines.append("  warning: different models; the difference is not only the prompt")
    lines += [
        f"  pass rate   {a['pass_rate']:.0%} → {b['pass_rate']:.0%}",
        f"  parsed      {a['parse_rate']:.0%} → {b['parse_rate']:.0%}",
        f"  median s    {a['median_seconds']} → {b['median_seconds']}",
    ]
    better, worse = [], []
    for key in sorted(set(a["by_check"]) | set(b["by_check"])):
        old, new = a["by_check"].get(key), b["by_check"].get(key)
        if old is None or new is None:
            continue
        old_rate = int(old.split("/")[0]) / int(old.split("/")[1])
        new_rate = int(new.split("/")[0]) / int(new.split("/")[1])
        if new_rate > old_rate:
            better.append(f"    {key}  {old} → {new}")
        elif new_rate < old_rate:
            worse.append(f"    {key}  {old} → {new}")
    if better:
        lines += ["  improved:", *better]
    if worse:
        lines += ["  got worse:", *worse]
    return lines
