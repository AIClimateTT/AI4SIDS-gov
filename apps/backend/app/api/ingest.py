import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.registry import get_module
from app.db import get_session
from app.quality.store import record_event

router = APIRouter()


@router.post("/ingest/{module_name}")
async def ingest(
    module_name: str,
    file: UploadFile,
    session: Session = Depends(get_session),
) -> dict:
    module = get_module(module_name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"unknown module: {module_name}")

    if module_name == "sitreps":
        raise HTTPException(
            status_code=400,
            detail=(
                "sitreps data arrives as a submission; "
                "POST /submissions with a corporation, an as-at time and up to two CSVs"
            ),
        )

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        result = module.ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if module_name == "survey123":
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
