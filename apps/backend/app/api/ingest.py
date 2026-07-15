import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.registry import get_module

router = APIRouter()


@router.post("/ingest/{module_name}")
async def ingest(module_name: str, file: UploadFile) -> dict:
    module = get_module(module_name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"unknown module: {module_name}")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        result = module.ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.model_dump()
