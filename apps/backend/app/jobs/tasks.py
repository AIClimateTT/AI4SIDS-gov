from app.jobs.reports import run_generate_report

HANDLERS = {
    "generate_report": run_generate_report,
}


def run(name: str, **kwargs) -> None:
    HANDLERS[name](**kwargs)
