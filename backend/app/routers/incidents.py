"""Incident Centre Router: detection, grouping, investigation, confirmation/dismissal, and ticket linking."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.incidents import Incident, IncidentTicket
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.schemas import (
    IncidentCreateRequest,
    IncidentDetectRequest,
    IncidentLinkTicketRequest,
    IncidentUpdateRequest,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import require_roles
from app.services.incident_service import (
    ACTIVE_INCIDENT_STATUSES,
    detect_candidate_incidents,
    generate_incident_reference,
    recompute_incident_timestamps,
    record_incident_event,
    serialize_incident_detail,
    serialize_incident_summary,
)

router = APIRouter(prefix="/api/incidents", tags=["Incident Centre"])


@router.get("")
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    include_dismissed: bool = Query(False),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    q = db.query(Incident)
    if status_filter:
        q = q.filter(Incident.status == status_filter)
    elif not include_dismissed:
        q = q.filter(Incident.status != "dismissed")
    if severity:
        q = q.filter(Incident.severity == severity)
    if department_id is not None:
        q = q.filter(Incident.department_id == department_id)

    incidents = q.order_by(Incident.created_at.desc()).all()
    summaries = [serialize_incident_summary(i) for i in incidents]

    active_all = db.query(Incident).filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES)).all()
    unique_affected_across_active = set()
    for inc in active_all:
        for lnk in inc.ticket_links:
            if lnk.ticket:
                unique_affected_across_active.add(lnk.ticket.customer_id)

    return {
        "items": summaries,
        "summary": {
            "active_incidents": len(active_all),
            "newly_detected": sum(1 for i in active_all if i.status == "detected"),
            "confirmed_or_investigating": sum(1 for i in active_all if i.status in ("confirmed", "investigating")),
            "unique_affected_customers_active": len(unique_affected_across_active),
        },
    }


@router.post("/detect")
def run_incident_detection(
    payload: IncidentDetectRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    result = detect_candidate_incidents(
        db=db,
        window_days=payload.window_days,
        similarity_threshold=payload.similarity_threshold,
        min_cluster_size=payload.min_cluster_size,
        actor=current_user,
    )
    log_audit_event(
        db,
        action="incident.detect",
        entity_type="incident",
        user_id=current_user.id,
        details={"detected_count": result["detected_count"], "scanned_tickets": result["scanned_tickets"]},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    inc = Incident(
        incident_reference=generate_incident_reference(db),
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        severity=payload.severity,
        status="investigating",
        department_id=payload.department_id,
        owner_id=payload.owner_id or current_user.id,
        common_symptoms=payload.common_symptoms,
        is_auto_detected=False,
        first_reported_at=now,
        last_reported_at=now,
    )
    db.add(inc)
    db.flush()

    for tid in set(payload.ticket_ids):
        t = db.query(Ticket).filter(Ticket.id == tid).first()
        if t:
            db.add(IncidentTicket(incident_id=inc.id, ticket_id=t.id, linked_by=current_user.id))

    db.flush()
    recompute_incident_timestamps(inc)
    record_incident_event(
        db, inc.id, "incident_created", f"{current_user.name} created incident '{inc.title}'.", current_user.id, new_value=inc.status
    )
    log_audit_event(
        db, "incident.create", "incident", inc.id, current_user.id, {"title": inc.title},
        request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(inc)
    return serialize_incident_detail(inc)


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return serialize_incident_detail(inc)


@router.patch("/{incident_id}")
def update_incident(
    incident_id: int,
    payload: IncidentUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")

    now = datetime.now(timezone.utc)
    if payload.status and payload.status != inc.status:
        old = inc.status
        inc.status = payload.status
        if payload.status == "resolved":
            inc.resolved_at = now
        elif old == "resolved":
            inc.resolved_at = None
        record_incident_event(
            db, inc.id, "status_changed",
            f"{current_user.name} changed incident status from '{old}' to '{payload.status}'.",
            current_user.id, old, payload.status,
        )

    if payload.severity and payload.severity != inc.severity:
        old_s = inc.severity
        inc.severity = payload.severity
        record_incident_event(
            db, inc.id, "severity_changed",
            f"{current_user.name} changed severity from '{old_s}' to '{payload.severity}'.",
            current_user.id, old_s, payload.severity,
        )

    if payload.title is not None:
        inc.title = payload.title.strip()
    if payload.description is not None:
        inc.description = payload.description.strip()
    if payload.department_id is not None:
        inc.department_id = payload.department_id
    if payload.owner_id is not None:
        inc.owner_id = payload.owner_id
    if payload.investigation_notes is not None:
        inc.investigation_notes = payload.investigation_notes.strip()
        record_incident_event(db, inc.id, "notes_updated", f"{current_user.name} updated investigation notes.", current_user.id)
    if payload.resolution_summary is not None:
        inc.resolution_summary = payload.resolution_summary.strip()

    log_audit_event(
        db, "incident.update", "incident", inc.id, current_user.id,
        payload.model_dump(exclude_none=True),
        request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(inc)
    return serialize_incident_detail(inc)


@router.post("/{incident_id}/tickets", status_code=status.HTTP_201_CREATED)
def link_ticket(
    incident_id: int,
    payload: IncidentLinkTicketRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    existing = (
        db.query(IncidentTicket)
        .filter(IncidentTicket.incident_id == incident_id, IncidentTicket.ticket_id == payload.ticket_id)
        .first()
    )
    if existing:
        return serialize_incident_detail(inc)

    db.add(
        IncidentTicket(
            incident_id=incident_id,
            ticket_id=ticket.id,
            similarity_score=payload.similarity_score,
            linked_by=current_user.id,
        )
    )
    db.flush()
    recompute_incident_timestamps(inc)
    record_incident_event(
        db, inc.id, "ticket_linked",
        f"{current_user.name} linked ticket {ticket.ticket_reference} to this incident.",
        current_user.id, new_value=ticket.ticket_reference,
    )
    db.commit()
    db.refresh(inc)
    return serialize_incident_detail(inc)


@router.delete("/{incident_id}/tickets/{ticket_id}")
def unlink_ticket(
    incident_id: int,
    ticket_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    lnk = (
        db.query(IncidentTicket)
        .filter(IncidentTicket.incident_id == incident_id, IncidentTicket.ticket_id == ticket_id)
        .first()
    )
    if not lnk:
        raise HTTPException(status_code=404, detail="Ticket is not linked to this incident.")

    ref = lnk.ticket.ticket_reference if lnk.ticket else str(ticket_id)
    db.delete(lnk)
    db.flush()
    recompute_incident_timestamps(inc)
    record_incident_event(
        db, inc.id, "ticket_unlinked",
        f"{current_user.name} unlinked ticket {ref} from this incident.",
        current_user.id, old_value=ref,
    )
    db.commit()
    db.refresh(inc)
    return serialize_incident_detail(inc)
