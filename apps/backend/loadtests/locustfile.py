import json
from datetime import datetime, timezone

from locust import HttpUser, between, tag, task
from locust.exception import StopUser

CORP = "diego_martin_regional_corporati"
SITREP = "5 houses flooded in Petit Valley. 200 sandbags remaining at the depot."


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _open_session(user: HttpUser) -> tuple[int, int]:
    created = user.client.post(
        "/events",
        json={
            "corporation": CORP,
            "title": "Locust soak",
            "hazard_type": "flood",
            "started_at": _now(),
        },
        name="/events",
    )
    if created.status_code != 201:
        raise StopUser()
    event_id = created.json()["id"]
    session = user.client.post(
        "/capture/sessions",
        json={"corporation": CORP, "event_id": event_id},
        name="/capture/sessions",
    )
    if session.status_code != 201:
        raise StopUser()
    return event_id, session.json()["id"]


def _drain_sse(response) -> tuple[bool, bool]:
    saw_content = False
    saw_error = False
    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "TEXT_MESSAGE_CONTENT":
            saw_content = True
        elif event_type == "RUN_ERROR":
            saw_error = True
    return saw_content, saw_error


@tag("api")
class CaptureApiUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        _event_id, self.session_id = _open_session(self)

    @task(3)
    def healthcheck(self) -> None:
        self.client.get("/healthcheck")

    @task(5)
    def turn(self) -> None:
        self.client.post(
            f"/capture/sessions/{self.session_id}/turns",
            json={"message": SITREP},
            name="/capture/sessions/[id]/turns",
        )

    @task(2)
    def stream_turn(self) -> None:
        with self.client.post(
            f"/capture/sessions/{self.session_id}/turns/stream",
            json={"messages": [{"role": "user", "content": SITREP}]},
            name="/capture/sessions/[id]/turns/stream",
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"stream status {response.status_code}")
                return
            saw_content, saw_error = _drain_sse(response)
            if saw_error:
                response.failure("capture stream ended in RUN_ERROR")
            elif not saw_content:
                response.failure("capture stream had no TEXT_MESSAGE_CONTENT")
            else:
                response.success()


@tag("api")
class CaptureFileUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self._open()

    def _open(self) -> None:
        _event_id, self.session_id = _open_session(self)

    @task
    def turn_and_file(self) -> None:
        turn = self.client.post(
            f"/capture/sessions/{self.session_id}/turns",
            json={"message": SITREP},
            name="/capture/sessions/[id]/turns",
        )
        if turn.status_code != 200:
            return
        filed = self.client.post(
            f"/capture/sessions/{self.session_id}/file",
            name="/capture/sessions/[id]/file",
        )
        if filed.status_code == 201:
            self._open()


@tag("chat")
class CaptureChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        _event_id, self.session_id = _open_session(self)

    @task
    def stream_turn(self) -> None:
        with self.client.post(
            f"/capture/sessions/{self.session_id}/turns/stream",
            json={"messages": [{"role": "user", "content": SITREP}]},
            name="/capture/sessions/[id]/turns/stream",
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"stream status {response.status_code}")
                return
            saw_content, saw_error = _drain_sse(response)
            if saw_error:
                response.failure("capture stream ended in RUN_ERROR")
            elif not saw_content:
                response.failure("capture stream had no TEXT_MESSAGE_CONTENT")
            else:
                response.success()
