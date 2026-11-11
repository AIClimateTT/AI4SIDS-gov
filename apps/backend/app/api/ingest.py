import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.modules.survey123.client import (
    Survey123NotConfigured,
    Survey123Unavailable,
    query_responses,
)
from app.modules.survey123.ingest import IngestFormatError, ingest_survey123_export
from app.modules.survey123.pull import pull_survey123
from app.quality.store import record_event

router = APIRouter()


@router.get("/field-data/survey123/query")
def query_survey123(
    where: str = "1=1",
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    layer: int = Query(default=0, ge=0),
) -> dict:
    try:
        return query_responses(where=where, limit=limit, offset=offset, layer=layer)
    except Survey123NotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Survey123Unavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/field-data/survey123/pull")
def pull_survey123_responses(
    layer: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    record_event(session, workflow="survey123_ingest", step="api_pull", outcome="started")
    try:
        result = pull_survey123(session, settings.dedup_salt, layer=layer)
    except Survey123NotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Survey123Unavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except IngestFormatError as exc:
        raise HTTPException(status_code=502, detail=exc.detail) from exc
    record_event(session, workflow="survey123_ingest", step="api_pull", outcome="succeeded")
    return result.model_dump()


@router.post("/field-data/upload")
async def upload_field_data(
    file: UploadFile,
    session: Session = Depends(get_session),
) -> dict:
    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        try:
            result = ingest_survey123_export(tmp_path, session, settings.dedup_salt)
        except IngestFormatError as exc:
            raise HTTPException(status_code=400, detail=exc.detail) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    record_event(
        session,
        workflow="survey123_ingest",
        step="ingest",
        outcome="started",
        subject_id=file.filename,
    )
    record_event(
        session,
        workflow="survey123_ingest",
        step="ingest",
        outcome="succeeded",
        subject_id=file.filename,
    )

    return result.model_dump()
