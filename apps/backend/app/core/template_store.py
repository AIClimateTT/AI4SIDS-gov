from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.contracts import Template
from app.core.template_models import TemplateRecord
from app.templates.loader import load_templates_from_directory


def _to_template(record: TemplateRecord) -> Template:
    return Template.model_validate(
        {
            "name": record.name,
            "version": record.version,
            "title": record.title,
            "description": record.description,
            "params": record.params,
            "data_requirements": record.data_requirements,
            "narration": record.narration,
            "render": record.render,
        }
    )


def create_template_version(template: Template, session: Session) -> Template:
    latest_version = session.execute(
        select(func.max(TemplateRecord.version)).where(TemplateRecord.name == template.name)
    ).scalar()
    next_version = (latest_version or 0) + 1

    record = TemplateRecord(
        name=template.name,
        version=next_version,
        title=template.title,
        description=template.description,
        params=[p.model_dump() for p in template.params],
        data_requirements=[d.model_dump() for d in template.data_requirements],
        narration=template.narration.model_dump(),
        render=template.render.model_dump(),
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.commit()
    return _to_template(record)


def get_latest_template_version(name: str, session: Session) -> Template | None:
    record = (
        session.execute(
            select(TemplateRecord).where(TemplateRecord.name == name).order_by(TemplateRecord.version.desc())
        )
        .scalars()
        .first()
    )
    return _to_template(record) if record else None


def get_template_version(name: str, version: int, session: Session) -> Template | None:
    record = (
        session.execute(
            select(TemplateRecord).where(TemplateRecord.name == name, TemplateRecord.version == version)
        )
        .scalars()
        .first()
    )
    return _to_template(record) if record else None


def list_latest_templates(session: Session) -> list[Template]:
    subquery = (
        select(TemplateRecord.name, func.max(TemplateRecord.version).label("max_version"))
        .group_by(TemplateRecord.name)
        .subquery()
    )
    records = (
        session.execute(
            select(TemplateRecord).join(
                subquery,
                (TemplateRecord.name == subquery.c.name) & (TemplateRecord.version == subquery.c.max_version),
            )
        )
        .scalars()
        .all()
    )
    return [_to_template(r) for r in sorted(records, key=lambda r: r.name)]


def import_template_directory(directory: Path, session: Session) -> list[Template]:
    return [create_template_version(template, session) for template in load_templates_from_directory(directory)]
