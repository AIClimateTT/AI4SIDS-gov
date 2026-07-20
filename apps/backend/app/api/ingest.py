import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.registry import get_module
from app.db import get_session
from app.modules.sitreps.ingest import ingest_sitrep_csv

router = APIRouter()


@router.post("/ingest/{module_name}")
async def ingest(
    module_name: str,
    file: UploadFile,
    corporation: str | None = Form(None),
    session: Session = Depends(get_session),
) -> dict:
    module = get_module(module_name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"unknown module: {module_name}")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        if module_name == "sitreps":
            if not corporation or not corporation.strip():
                raise HTTPException(
                    status_code=400,
                    detail="corporation is required for sitreps ingest",
                )
            result = ingest_sitrep_csv(tmp_path, corporation.strip(), session)
        else:
            result = module.ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.model_dump()
