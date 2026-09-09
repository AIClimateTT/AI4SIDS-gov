import re
from pathlib import Path

from app.quality.denominators import NAMED_WORKFLOWS

_WORKFLOW_MARK = re.compile(r'pytest\.mark\.workflow\(\s*["\']([^"\']+)["\']')


def test_every_named_workflow_has_at_least_one_test(request):
    seen: set[str] = set()
    for item in request.session.items:
        marker = item.get_closest_marker("workflow")
        if marker and marker.args:
            seen.add(marker.args[0])
    if set(NAMED_WORKFLOWS) - seen:
        tests_dir = Path(__file__).resolve().parent
        for path in tests_dir.rglob("test_*.py"):
            seen.update(_WORKFLOW_MARK.findall(path.read_text()))
    missing = set(NAMED_WORKFLOWS) - seen
    assert missing == set(), f"no pytest.mark.workflow tests for {sorted(missing)}"
