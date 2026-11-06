import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.modules.survey123.ingest import IngestFormatError, ingest_survey123_export
from app.quality.store import record_event

router = APIRouter()


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
