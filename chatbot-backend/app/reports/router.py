"""Downloading a leave or attendance report.

The chat reply offers a report; this is where the file is actually built. It is
a separate request because the browser needs to send the token and receive a
binary body, and because a download should be repeatable without asking the
question again.

The ERP id is re-authorised here rather than trusted from the request: the
offer that produced these parameters came from this service, but the request
carrying them is still just a request.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.identity import Identity, current_identity
from app.chat.schemas import ReportRequest
from app.config.settings import settings
from app.database.db import get_db
from app.hr import queries as hr
from app.reports import builder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

SUBJECTS = ("leave", "attendance", "official_work")
FORMATS = ("excel", "pdf")


@router.post("/generate")
def generate_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    if request.subject not in SUBJECTS:
        raise HTTPException(status_code=400, detail=f"subject must be one of {', '.join(SUBJECTS)}")
    if request.report_format not in FORMATS:
        raise HTTPException(status_code=400, detail="report_format must be excel or pdf")

    start: date = request.start
    end: date = request.end
    if end < start:
        start, end = end, start

    span = (end - start).days + 1
    if span > settings.REPORT_MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"That period covers {span} days; the maximum for one report is "
                f"{settings.REPORT_MAX_RANGE_DAYS}."
            ),
        )

    # Anyone may report on themselves. Only an administrator may name somebody
    # else, and an employee who tries is simply reported on themselves.
    erp_id = identity.erp_id
    if request.erp_id and request.erp_id != identity.erp_id:
        if not identity.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You can only download reports for your own records.",
            )
        erp_id = request.erp_id

    employee = hr.get_employee(db, erp_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"No active employee with ERP ID {erp_id}")

    summary = None
    if request.subject == "attendance":
        ranged = hr.attendance_range(db, erp_id, start, end)
        rows = ranged.get("days", [])
        summary = {key: value for key, value in (ranged.get("summary") or {}).items() if value}
    elif request.subject == "official_work":
        rows = hr.official_work(db, erp_id, start, end, limit=settings.REPORT_MAX_ROWS)
        summary = {"records": len(rows)}
    else:
        rows = hr.leave_history(db, erp_id, start, end, limit=settings.REPORT_MAX_ROWS)
        summary = {
            "records": len(rows),
            "total_days": sum(row.get("days") or 0 for row in rows),
        }

    payload, filename, media_type = builder.build(
        request.report_format, request.subject, employee, (start, end), rows, summary
    )

    logger.info(
        "report: subject=%s format=%s erp=%s (requested by %s) rows=%d bytes=%d",
        request.subject, request.report_format, erp_id, identity.erp_id, len(rows), len(payload),
    )

    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # The widget reads this to name the saved file; without it the
            # browser only sees the header on a same-origin response.
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
