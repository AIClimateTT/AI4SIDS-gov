from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.modules.incident_list import list_incidents

router = APIRouter()


class IncidentListItem(BaseModel):
    id: str
    source: Literal["survey123", "sitreps"]
    corporation: str | None
    community: str | None
    incident_type: str | None
    event_date: datetime | None
    incident_summary: str | None
    injuries_occurred: bool
    injuries_count: int | None
    deaths_occurred: bool
    deaths_count: int | None
    ingested_at: datetime
    validation_status: str | None
    is_duplicate: bool | None


class IncidentListResponse(BaseModel):
    items: list[IncidentListItem]
    total: int


@router.get("/incidents", response_model=IncidentListResponse)
def get_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str | None = None,
    source: str = Query("all"),
    session: Session = Depends(get_session),
) -> IncidentListResponse:
    try:
        items, total = list_incidents(
            session,
            page=page,
            page_size=page_size,
            q=q,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IncidentListResponse(items=[IncidentListItem(**item) for item in items], total=total)
