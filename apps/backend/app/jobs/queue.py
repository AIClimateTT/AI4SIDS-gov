from procrastinate import App, PsycopgConnector

from app.config import settings
from app.jobs.reports import run_generate_report
from app.jobs.whatsapp import run_briefing, run_extract


def postgres_dsn() -> str:
    url = settings.database_url
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    return url


app = App(connector=PsycopgConnector(conninfo=postgres_dsn()))


@app.task(name="generate_report")
def generate_report_task(report_id: str) -> None:
    run_generate_report(report_id)


@app.task(name="extract_whatsapp")
def extract_whatsapp_task(draft_id: int) -> None:
    run_extract(draft_id)


@app.task(name="generate_briefing")
def generate_briefing_task(draft_id: int, report_id: str) -> None:
    run_briefing(draft_id, report_id)


def defer_job(name: str, **kwargs) -> None:
    with app.open():
        app.configure_task(name=name).defer(**kwargs)


def _schema_applied() -> bool:
    row = app.connector.get_sync_connector().execute_query_one(
        query="SELECT to_regclass('public.procrastinate_jobs') AS name"
    )
    return bool(row.get("name"))


def apply_schema() -> None:
    if settings.database_url.startswith("sqlite"):
        return
    with app.open():
        if _schema_applied():
            return
        app.schema_manager.apply_schema()
