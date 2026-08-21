from app.config import settings


def resolve_job_backend() -> str:
    if settings.job_backend is not None:
        return settings.job_backend
    if settings.database_url.startswith("sqlite"):
        return "eager"
    return "procrastinate"


def enqueue(name: str, **kwargs) -> None:
    if resolve_job_backend() == "eager":
        from app.jobs.tasks import run

        run(name, **kwargs)
        return
    from app.jobs.queue import defer_job

    defer_job(name, **kwargs)
