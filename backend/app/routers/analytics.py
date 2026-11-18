"""Analytics & Reporting Router with date filtering and CSV export."""

import csv
from datetime import datetime
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.services.analytics_service import (
    compute_agent_analytics,
    compute_classification_and_feedback_analytics,
    compute_customer_experience_and_trends,
    compute_department_analytics,
    compute_overview_analytics,
)
from app.services.auth_service import require_roles
from app.services.resolution_service import compute_resolution_effectiveness

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/overview")
def analytics_overview(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_overview_analytics(
        db,
        start_date=_parse_dt(start_date),
        end_date=_parse_dt(end_date),
        department_id=department_id,
        priority=priority,
    )


@router.get("/tickets")
def analytics_tickets(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    overview = compute_overview_analytics(
        db, _parse_dt(start_date), _parse_dt(end_date), department_id, priority
    )
    cx = compute_customer_experience_and_trends(db, _parse_dt(start_date), _parse_dt(end_date))
    return {
        "metrics": overview["metrics"],
        "volume_over_time": overview["volume_over_time"],
        "by_category": overview["by_category"],
        "by_priority": overview["by_priority"],
        "customer_experience": cx,
    }


@router.get("/departments")
def analytics_departments(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return {"departments": compute_department_analytics(db, _parse_dt(start_date), _parse_dt(end_date))}


@router.get("/agents")
def analytics_agents(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return {"agents": compute_agent_analytics(db, _parse_dt(start_date), _parse_dt(end_date))}


@router.get("/sla")
def analytics_sla(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    overview = compute_overview_analytics(db, _parse_dt(start_date), _parse_dt(end_date))
    depts = compute_department_analytics(db, _parse_dt(start_date), _parse_dt(end_date))
    return {
        "overall_sla_compliance_rate": overview["metrics"]["sla_compliance_rate"],
        "completed_eligible": overview["metrics"]["sla_completed_eligible"],
        "completed_within_target": overview["metrics"]["sla_completed_within_target"],
        "overdue_open_count": overview["metrics"]["overdue_tickets"],
        "avg_first_response_minutes": overview["metrics"]["avg_first_response_minutes"],
        "avg_resolution_minutes": overview["metrics"]["avg_resolution_minutes"],
        "by_department": [
            {
                "department": d["name"],
                "sla_compliance_rate": d["sla_compliance_rate"],
                "avg_resolution_minutes": d["avg_resolution_minutes"],
                "escalation_rate": d["escalation_rate"],
            }
            for d in depts
        ],
        "upcoming_deadlines": overview["upcoming_sla_deadlines"],
    }


@router.get("/classification")
def analytics_classification(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_classification_and_feedback_analytics(db, _parse_dt(start_date), _parse_dt(end_date))


@router.get("/customer-experience")
def analytics_cx(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_customer_experience_and_trends(db, _parse_dt(start_date), _parse_dt(end_date))


@router.get("/effectiveness")
def analytics_resolution_effectiveness(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_resolution_effectiveness(db)


@router.get("/export/csv")
def export_analytics_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    depts = compute_department_analytics(db, _parse_dt(start_date), _parse_dt(end_date))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Department",
            "Agents",
            "Total Tickets",
            "Open Tickets",
            "Unassigned Tickets",
            "Avg Resolution (min)",
            "SLA Compliance (%)",
            "Escalation Rate (%)",
            "Reassignment Rate (%)",
            "Reopen Rate (%)",
        ]
    )
    for d in depts:
        writer.writerow(
            [
                d["name"],
                d["agent_count"],
                d["total_tickets"],
                d["open_tickets"],
                d["unassigned_tickets"],
                d["avg_resolution_minutes"] if d["avg_resolution_minutes"] is not None else "N/A",
                d["sla_compliance_rate"] if d["sla_compliance_rate"] is not None else "N/A",
                d["escalation_rate"],
                d["reassignment_rate"],
                d["reopen_rate"],
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=qryvanta_department_analytics.csv"},
    )
