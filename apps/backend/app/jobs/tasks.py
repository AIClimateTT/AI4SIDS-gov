from app.jobs.reports import run_generate_report
from app.jobs.whatsapp import run_extract, run_briefing

HANDLERS = {
    "generate_report": run_generate_report,
    "extract_whatsapp": run_extract,
    "generate_briefing": run_briefing,
}


def run(name: str, **kwargs) -> None:
    HANDLERS[name](**kwargs)
