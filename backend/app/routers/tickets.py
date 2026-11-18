"""Ticket Operations & Lifecycle Router with strict RBAC and customer data isolation."""

import csv
from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import asc, case, desc, or_
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.models.incidents import Incident, IncidentTicket
from app.models.intelligence import TicketFeedback, TicketPrediction
from app.models.operations import SLATracking
from app.models.ticket import (
    Category,
    Ticket,
    TicketAssignment,
    TicketAttachment,
    TicketMessage,
    TicketRelation,
)
from app.models.user import Agent, Customer, Department, User
from app.schemas.schemas import (
    BulkImportExecuteRequest,
    BulkTicketActionRequest,
    TicketAssignRequest,
    TicketCloseRequest,
    TicketCreateRequest,
    TicketRatingRequest,
    TicketReclassifyRequest,
    TicketRelationCreateRequest,
    TicketReopenRequest,
    TicketReplyRequest,
    TicketUpdateRequest,
    TicketVerifyRequest,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import (
    get_agent_authorized_department_ids,
    get_current_user,
    require_roles,
)
from app.services.bulk_import_service import execute_csv_import, preview_csv_content
from app.services.routing_service import OPEN_TICKET_STATUSES, get_routing_thresholds
from app.services.sla_risk_service import build_risk_caches, compute_ticket_sla_risk
from app.services.sla_service import (
    compute_sla_state,
    create_or_update_sla_tracking,
    handle_sla_pause_resume,
)
from app.services.ticket_service import (
    build_company_handoff_report,
    create_ticket_full,
    record_ticket_event,
    serialize_ticket_detail,
    serialize_ticket_summary,
)
from app.utils.security import sanitize_filename

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


def _ensure_ticket_access(ticket: Ticket, user: User) -> None:
    """Enforce strict customer isolation and department-level access for agents."""
    if user.role in ("admin", "manager"):
        return
    if user.role == "customer":
        if not user.customer_profile or ticket.customer_id != user.customer_profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this ticket.")
        return
    if user.role == "agent":
        dept_ids = set(get_agent_authorized_department_ids(user))
        assigned_to_me = user.agent_profile and ticket.assigned_agent_id == user.agent_profile.id
        in_dept = ticket.department_id in dept_ids or ticket.department_id is None
        if not (assigned_to_me or in_dept):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ticket belongs to an unauthorized department.")


def _get_or_create_customer_profile(db: Session, user: User) -> Customer:
    if user.customer_profile:
        return user.customer_profile
    cust = Customer(
        user_id=user.id,
        customer_reference=f"CUST-USR-{user.id:05d}",
        contact_information=user.email,
    )
    db.add(cust)
    db.flush()
    return cust


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = _get_or_create_customer_profile(db, current_user)
    if payload.contact_information:
        customer.contact_information = payload.contact_information.strip()

    ticket = create_ticket_full(
        db=db,
        customer=customer,
        actor=current_user,
        subject=payload.subject,
        description=payload.description,
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        product_reference=payload.product_reference,
        company_id=payload.company_id,
        platform_type=payload.platform_type,
        external_reference=payload.external_reference,
        source="web_portal",
        is_demo_data=False,
        ip_address=request.client.host if request.client else None,
    )
    return serialize_ticket_detail(db, ticket, current_user)


@router.get("")
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    preset: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    department_id: Optional[int] = None,
    category_id: Optional[int] = None,
    assigned_agent_id: Optional[int] = None,
    platform_type: Optional[str] = None,
    company_id: Optional[int] = None,
    verification_status: Optional[str] = None,
    sla_state: Optional[str] = None,
    risk_level: Optional[str] = None,
    incident_linked: Optional[bool] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|priority|sla|status|updated_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Ticket).outerjoin(SLATracking, Ticket.id == SLATracking.ticket_id)

    # Role-based scoping
    if current_user.role == "customer":
        if not current_user.customer_profile:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        q = q.filter(Ticket.customer_id == current_user.customer_profile.id)
    elif current_user.role == "agent":
        dept_ids = list(get_agent_authorized_department_ids(current_user))
        my_agent_id = current_user.agent_profile.id if current_user.agent_profile else -1
        q = q.filter(
            or_(
                Ticket.assigned_agent_id == my_agent_id,
                Ticket.department_id.in_(dept_ids) if dept_ids else False,
                Ticket.department_id.is_(None),
            )
        )

    # Search
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.outerjoin(Customer, Ticket.customer_id == Customer.id).outerjoin(User, Customer.user_id == User.id)
        q = q.filter(
            or_(
                Ticket.ticket_reference.ilike(term),
                Ticket.subject.ilike(term),
                Ticket.description.ilike(term),
                User.name.ilike(term),
                User.email.ilike(term),
            )
        )

    # Presets
    _, med_threshold = get_routing_thresholds(db)
    if preset == "my_tickets" and current_user.agent_profile:
        q = q.filter(Ticket.assigned_agent_id == current_user.agent_profile.id)
    elif preset == "unassigned":
        q = q.filter(Ticket.assigned_agent_id.is_(None), Ticket.status.in_(OPEN_TICKET_STATUSES))
    elif preset == "critical_high":
        q = q.filter(Ticket.priority.in_(("critical", "high")), Ticket.status.in_(OPEN_TICKET_STATUSES))
    elif preset == "awaiting_response":
        q = q.filter(Ticket.status.in_(("new", "open", "awaiting_customer")))
    elif preset == "reopened":
        q = q.filter(Ticket.reopen_count > 0)
    elif preset == "active":
        q = q.filter(Ticket.status.in_(OPEN_TICKET_STATUSES))
    elif preset == "resolved":
        q = q.filter(Ticket.status.in_(("resolved", "closed")))
    elif preset == "low_confidence":
        q = q.join(TicketPrediction, Ticket.id == TicketPrediction.ticket_id).filter(
            TicketPrediction.confidence < med_threshold
        )

    # Explicit filters
    if status_filter:
        q = q.filter(Ticket.status == status_filter)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if department_id is not None:
        q = q.filter(Ticket.department_id == department_id)
    if category_id is not None:
        q = q.filter(Ticket.category_id == category_id)
    if assigned_agent_id is not None:
        q = q.filter(Ticket.assigned_agent_id == assigned_agent_id)
    if platform_type:
        q = q.filter(Ticket.platform_type == platform_type)
    if company_id is not None:
        q = q.filter(Ticket.company_id == company_id)
    if verification_status:
        q = q.filter(Ticket.verification_status == verification_status)

    # Sorting
    priority_rank = case(
        (Ticket.priority == "critical", 4),
        (Ticket.priority == "high", 3),
        (Ticket.priority == "medium", 2),
        else_=1,
    )
    sort_col = {
        "created_at": Ticket.created_at,
        "updated_at": Ticket.updated_at,
        "priority": priority_rank,
        "sla": SLATracking.resolution_deadline,
        "status": Ticket.status,
    }.get(sort_by, Ticket.created_at)

    q = q.order_by(desc(sort_col) if sort_order == "desc" else asc(sort_col), desc(Ticket.id))

    all_rows = q.distinct().all()

    # Dynamic SLA state, SLA risk, and incident-linked filtering
    if preset == "overdue" or sla_state:
        target_state = "overdue" if preset == "overdue" else sla_state
        all_rows = [
            t for t in all_rows
            if (compute_sla_state(t.sla_tracking, t.status) if t.sla_tracking else "unknown") == target_state
        ]

    is_staff = current_user.role in ("agent", "manager", "admin")
    incident_ticket_map: dict[int, list[dict]] = {}
    if is_staff:
        links = (
            db.query(IncidentTicket)
            .join(Incident, IncidentTicket.incident_id == Incident.id)
            .filter(Incident.status != "dismissed")
            .all()
        )
        for lnk in links:
            if lnk.incident:
                incident_ticket_map.setdefault(lnk.ticket_id, []).append(
                    {
                        "id": lnk.incident.id,
                        "incident_reference": lnk.incident.incident_reference,
                        "status": lnk.incident.status,
                    }
                )
        if incident_linked is True:
            all_rows = [t for t in all_rows if t.id in incident_ticket_map]
        elif incident_linked is False:
            all_rows = [t for t in all_rows if t.id not in incident_ticket_map]

    dept_c, agent_c, cat_avgs = build_risk_caches(db) if is_staff else ({}, {}, {})
    risk_by_tid: dict[int, dict] = {}
    if is_staff and (risk_level or preset == "high_risk"):
        target_levels = {"critical", "high"} if preset == "high_risk" else {risk_level}
        filtered_r = []
        for t in all_rows:
            r = compute_ticket_sla_risk(db, t, dept_c, agent_c, cat_avgs)
            risk_by_tid[t.id] = r
            if r["risk_level"] in target_levels:
                filtered_r.append(t)
        all_rows = filtered_r

    total = len(all_rows)
    start = (page - 1) * page_size
    page_items = all_rows[start : start + page_size]

    serialized_items = []
    for t in page_items:
        item = serialize_ticket_summary(t, include_internal_fields=is_staff)
        if is_staff:
            r = risk_by_tid.get(t.id) or compute_ticket_sla_risk(db, t, dept_c, agent_c, cat_avgs)
            item["sla_risk_level"] = r["risk_level"]
            item["sla_risk_score"] = r["risk_score"]
            item["linked_incidents"] = incident_ticket_map.get(t.id, [])
        serialized_items.append(item)

    return {
        "items": serialized_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.get("/export/csv")
def export_tickets_csv(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    department_id: Optional[int] = None,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    q = db.query(Ticket)
    if status_filter:
        q = q.filter(Ticket.status == status_filter)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if department_id is not None:
        q = q.filter(Ticket.department_id == department_id)
    if current_user.role == "agent":
        dept_ids = list(get_agent_authorized_department_ids(current_user))
        q = q.filter(or_(Ticket.department_id.in_(dept_ids), Ticket.department_id.is_(None)))

    tickets = q.order_by(Ticket.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Ticket Reference",
            "Subject",
            "Customer",
            "Category",
            "Subcategory",
            "Priority",
            "Department",
            "Assigned Agent",
            "Status",
            "SLA State",
            "Created At",
            "Demo Data",
        ]
    )
    for t in tickets:
        sla_st = compute_sla_state(t.sla_tracking, t.status) if t.sla_tracking else "unknown"
        writer.writerow(
            [
                t.ticket_reference,
                t.subject,
                t.customer.user.name if (t.customer and t.customer.user) else "",
                t.category.name if t.category else "",
                t.subcategory.name if t.subcategory else "",
                t.priority,
                t.department.name if t.department else "",
                t.assigned_agent.user.name if (t.assigned_agent and t.assigned_agent.user) else "",
                t.status,
                sla_st,
                t.created_at.isoformat() if t.created_at else "",
                "Yes" if t.is_demo_data else "No",
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=qryvanta_tickets_export.csv"},
    )


@router.post("/bulk-action")
def bulk_ticket_action(
    payload: BulkTicketActionRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    tickets = db.query(Ticket).filter(Ticket.id.in_(payload.ticket_ids)).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No matching tickets found.")

    updated = 0
    now = datetime.now(timezone.utc)
    for ticket in tickets:
        if payload.action == "assign" and payload.agent_id is not None:
            agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
            if not agent:
                raise HTTPException(status_code=404, detail="Target agent not found.")
            ticket.assigned_agent_id = agent.id
            if ticket.status == "new":
                ticket.status = "open"
            db.add(
                TicketAssignment(
                    ticket_id=ticket.id,
                    agent_id=agent.id,
                    department_id=ticket.department_id or agent.department_id,
                    assigned_by=current_user.id,
                    assignment_reason=payload.reason or "Bulk assignment by manager.",
                    assigned_at=now,
                )
            )
            record_ticket_event(
                db, ticket.id, "ticket_assigned", f"Bulk assigned to {agent.user.name}.", current_user.id
            )
            updated += 1
        elif payload.action == "department" and payload.department_id is not None:
            dept = db.query(Department).filter(Department.id == payload.department_id).first()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found.")
            ticket.department_id = dept.id
            record_ticket_event(
                db, ticket.id, "department_changed", f"Bulk moved to department {dept.name}.", current_user.id
            )
            updated += 1
        elif payload.action == "status" and payload.status is not None:
            old_status = ticket.status
            ticket.status = payload.status
            if ticket.sla_tracking:
                handle_sla_pause_resume(ticket.sla_tracking, old_status, payload.status, now)
                if payload.status in ("resolved", "closed"):
                    ticket.resolved_at = now
                    ticket.sla_tracking.resolved_at = now
                    ticket.sla_tracking.current_state = "completed"
            record_ticket_event(
                db, ticket.id, "status_changed", f"Bulk status changed from {old_status} to {payload.status}.", current_user.id, old_status, payload.status
            )
            updated += 1

    log_audit_event(
        db,
        action=f"ticket.bulk_{payload.action}",
        entity_type="ticket",
        user_id=current_user.id,
        details={"ticket_ids": payload.ticket_ids, "updated": updated},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"updated_count": updated}


@router.post("/import/preview")
async def import_tickets_preview(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("manager", "admin")),
):
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV file exceeds 5 MB limit.")
    try:
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = raw.decode("latin-1")
    preview = preview_csv_content(csv_text)
    return {**preview, "csv_text": csv_text}


@router.post("/import/execute")
def import_tickets_execute(
    payload: BulkImportExecuteRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    customer = _get_or_create_customer_profile(db, current_user)
    result = execute_csv_import(
        db=db,
        csv_text=payload.csv_text,
        column_mapping=payload.column_mapping,
        default_customer=customer,
        actor=current_user,
        is_demo_data=payload.is_demo_data,
    )
    log_audit_event(
        db,
        action="ticket.bulk_import",
        entity_type="ticket",
        user_id=current_user.id,
        details={
            "imported": result["imported_count"],
            "skipped": result["skipped_duplicates"],
            "failed": result["failed_count"],
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return result


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    detail = serialize_ticket_detail(db, ticket, current_user)
    if current_user.role in ("agent", "manager", "admin"):
        relations = (
            db.query(TicketRelation)
            .filter(
                or_(
                    TicketRelation.source_ticket_id == ticket.id,
                    TicketRelation.related_ticket_id == ticket.id,
                )
            )
            .all()
        )
        detail["confirmed_relations"] = [
            {
                "id": rel.id,
                "relation_type": rel.relation_type,
                "similarity_score": rel.similarity_score,
                "other_ticket_id": rel.related_ticket_id if rel.source_ticket_id == ticket.id else rel.source_ticket_id,
                "other_ticket_reference": (
                    rel.related_ticket.ticket_reference
                    if rel.source_ticket_id == ticket.id
                    else rel.source_ticket.ticket_reference
                ),
                "other_ticket_subject": (
                    rel.related_ticket.subject
                    if rel.source_ticket_id == ticket.id
                    else rel.source_ticket.subject
                ),
                "other_ticket_status": (
                    rel.related_ticket.status
                    if rel.source_ticket_id == ticket.id
                    else rel.source_ticket.status
                ),
                "confirmed_by": rel.confirmer.name if rel.confirmer else None,
                "created_at": rel.created_at.isoformat(),
            }
            for rel in relations
        ]
    return detail


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    now = datetime.now(timezone.utc)
    recalc_sla = False

    if payload.status and payload.status != ticket.status:
        old_status = ticket.status
        ticket.status = payload.status
        if ticket.sla_tracking:
            handle_sla_pause_resume(ticket.sla_tracking, old_status, payload.status, now)
            if payload.status in ("resolved", "closed"):
                ticket.resolved_at = now
                ticket.sla_tracking.resolved_at = now
                ticket.sla_tracking.current_state = "completed"
        record_ticket_event(
            db, ticket.id, "status_changed", f"Status changed from {old_status} to {payload.status}.", current_user.id, old_status, payload.status
        )

    if payload.priority and payload.priority != ticket.priority:
        old_prio = ticket.priority
        ticket.priority = payload.priority
        reason = payload.priority_override_reason or "Priority adjusted by support staff."
        ticket.priority_reason = f"Manual override by {current_user.name}: {reason}"
        recalc_sla = True
        record_ticket_event(
            db, ticket.id, "priority_changed", f"Priority changed from {old_prio} to {payload.priority}. Reason: {reason}", current_user.id, old_prio, payload.priority
        )

    if payload.department_id is not None and payload.department_id != ticket.department_id:
        if current_user.role not in ("manager", "admin", "agent"):
            raise HTTPException(status_code=403, detail="Not permitted to change department.")
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Target department not found.")
        old_dept = ticket.department.name if ticket.department else "Unassigned"
        ticket.department_id = dept.id
        recalc_sla = True
        latest_pred = ticket.predictions[0] if ticket.predictions else None
        if latest_pred:
            latest_pred.final_department_id = dept.id
            latest_pred.routing_decision = "overridden"
            latest_pred.override_reason = payload.override_reason or f"Moved to {dept.name} by {current_user.name}."
        record_ticket_event(
            db, ticket.id, "department_changed", f"Department changed from {old_dept} to {dept.name}.", current_user.id, old_dept, dept.name
        )

    if payload.category_id is not None:
        ticket.category_id = payload.category_id
    if payload.subcategory_id is not None:
        ticket.subcategory_id = payload.subcategory_id

    if recalc_sla:
        create_or_update_sla_tracking(db, ticket, reference_time=ticket.created_at)

    log_audit_event(
        db,
        action="ticket.update",
        entity_type="ticket",
        entity_id=ticket.id,
        user_id=current_user.id,
        details=payload.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/reply", status_code=status.HTTP_201_CREATED)
def reply_to_ticket(
    ticket_id: int,
    payload: TicketReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    if current_user.role == "customer":
        if ticket.status in ("closed",):
            raise HTTPException(status_code=400, detail="Closed tickets cannot receive replies; please reopen first.")
        visibility = "public"
    else:
        visibility = payload.visibility

    now = datetime.now(timezone.utc)
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=payload.message.strip(),
        visibility=visibility,
        created_at=now,
    )
    db.add(msg)

    # Track first public staff response for SLA compliance
    if current_user.role in ("agent", "manager", "admin") and visibility == "public":
        if ticket.sla_tracking and ticket.sla_tracking.first_responded_at is None:
            ticket.sla_tracking.first_responded_at = now
        if payload.new_status:
            old_status = ticket.status
            ticket.status = payload.new_status
            if ticket.sla_tracking:
                handle_sla_pause_resume(ticket.sla_tracking, old_status, payload.new_status, now)
        elif ticket.status == "new":
            ticket.status = "in_progress"
        record_ticket_event(db, ticket.id, "agent_reply", f"{current_user.name} posted a public reply.", current_user.id)
    elif visibility == "internal":
        record_ticket_event(db, ticket.id, "internal_note", f"{current_user.name} added an internal note.", current_user.id)
    else:
        # Customer reply resumes SLA if paused awaiting customer
        if ticket.status == "awaiting_customer":
            old_status = ticket.status
            ticket.status = "open"
            if ticket.sla_tracking:
                handle_sla_pause_resume(ticket.sla_tracking, old_status, "open", now)
        record_ticket_event(db, ticket.id, "customer_reply", f"{current_user.name} replied to the ticket.", current_user.id)

    ticket.updated_at = now
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    settings = get_settings()
    safe_display, stored_name = sanitize_filename(file.filename or "upload.txt")
    ext = Path(safe_display).suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / stored_name
    dest_path.write_bytes(content)

    att = TicketAttachment(
        ticket_id=ticket.id,
        original_filename=safe_display,
        stored_filename=stored_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        storage_path=str(dest_path),
        uploaded_by=current_user.id,
    )
    db.add(att)
    record_ticket_event(db, ticket.id, "attachment_added", f"{current_user.name} uploaded {safe_display}.", current_user.id)
    db.commit()
    db.refresh(att)
    return {
        "id": att.id,
        "original_filename": att.original_filename,
        "mime_type": att.mime_type,
        "file_size": att.file_size,
        "created_at": att.created_at.isoformat(),
    }


@router.get("/{ticket_id}/attachments/{attachment_id}")
def download_attachment(
    ticket_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    att = (
        db.query(TicketAttachment)
        .filter(TicketAttachment.id == attachment_id, TicketAttachment.ticket_id == ticket.id)
        .first()
    )
    if not att or not Path(att.storage_path).exists():
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return FileResponse(att.storage_path, filename=att.original_filename, media_type=att.mime_type)


@router.post("/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    payload: TicketAssignRequest,
    request: Request,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    now = datetime.now(timezone.utc)
    if payload.department_id is not None:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found.")
        ticket.department_id = dept.id

    agent = None
    if payload.agent_id is not None:
        agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found.")
        # Close active assignment record
        for prev in ticket.assignments:
            if prev.ended_at is None:
                prev.ended_at = now
        ticket.assigned_agent_id = agent.id
        if ticket.department_id is None and agent.department_id is not None:
            ticket.department_id = agent.department_id
        if ticket.status == "new":
            ticket.status = "open"

    db.add(
        TicketAssignment(
            ticket_id=ticket.id,
            agent_id=agent.id if agent else None,
            department_id=ticket.department_id,
            assigned_by=current_user.id,
            assignment_reason=payload.reason or f"Assigned by {current_user.name}.",
            assigned_at=now,
        )
    )
    target_label = agent.user.name if (agent and agent.user) else "Unassigned"
    record_ticket_event(
        db,
        ticket.id,
        "ticket_assigned",
        f"Ticket assigned to {target_label}. Reason: {payload.reason or 'Standard assignment'}",
        current_user.id,
        new_value=target_label,
    )
    log_audit_event(
        db,
        action="ticket.assign",
        entity_type="ticket",
        entity_id=ticket.id,
        user_id=current_user.id,
        details={"agent_id": payload.agent_id, "department_id": ticket.department_id, "reason": payload.reason},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/reclassify")
def reclassify_ticket(
    ticket_id: int,
    payload: TicketReclassifyRequest,
    request: Request,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """Human-in-the-loop correction workflow: stores feedback for future model evaluation & retraining."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    cat = db.query(Category).filter(Category.id == payload.corrected_category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Corrected category not found.")

    latest_pred = ticket.predictions[0] if ticket.predictions else None
    old_cat_name = ticket.category.name if ticket.category else "Uncategorized"

    ticket.category_id = payload.corrected_category_id
    ticket.subcategory_id = payload.corrected_subcategory_id
    if payload.corrected_priority:
        ticket.priority = payload.corrected_priority
        ticket.priority_reason = f"Corrected by {current_user.name}: {payload.correction_reason}"
    if payload.corrected_department_id:
        ticket.department_id = payload.corrected_department_id
        if latest_pred:
            latest_pred.final_department_id = payload.corrected_department_id
            latest_pred.routing_decision = "overridden"
            latest_pred.override_reason = payload.correction_reason

    fb = TicketFeedback(
        ticket_id=ticket.id,
        prediction_id=latest_pred.id if latest_pred else None,
        corrected_category_id=payload.corrected_category_id,
        corrected_subcategory_id=payload.corrected_subcategory_id,
        corrected_priority=payload.corrected_priority,
        corrected_department_id=payload.corrected_department_id,
        correction_reason=payload.correction_reason.strip(),
        corrected_by=current_user.id,
        model_version_id=latest_pred.model_version_id if latest_pred else None,
    )
    db.add(fb)

    create_or_update_sla_tracking(db, ticket, reference_time=ticket.created_at)
    record_ticket_event(
        db,
        ticket.id,
        "prediction_corrected",
        f"{current_user.name} reclassified ticket from {old_cat_name} to {cat.name}. Reason: {payload.correction_reason}",
        current_user.id,
        old_value=old_cat_name,
        new_value=cat.name,
    )
    log_audit_event(
        db,
        action="ticket.reclassify",
        entity_type="ticket",
        entity_id=ticket.id,
        user_id=current_user.id,
        details={"corrected_category": cat.name, "reason": payload.correction_reason},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/close")
def close_ticket(
    ticket_id: int,
    payload: TicketCloseRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    now = datetime.now(timezone.utc)
    old_status = ticket.status
    ticket.status = payload.status
    ticket.resolved_at = now
    if ticket.sla_tracking:
        handle_sla_pause_resume(ticket.sla_tracking, old_status, payload.status, now)
        ticket.sla_tracking.resolved_at = now
        if ticket.sla_tracking.first_responded_at is None:
            ticket.sla_tracking.first_responded_at = now
        ticket.sla_tracking.current_state = "completed"

    if payload.resolution_note and payload.resolution_note.strip():
        db.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_id=current_user.id,
                message=payload.resolution_note.strip(),
                visibility="public",
                created_at=now,
            )
        )

    record_ticket_event(
        db,
        ticket.id,
        "ticket_resolved" if payload.status == "resolved" else "ticket_closed",
        f"{current_user.name} marked ticket as {payload.status}.",
        current_user.id,
        old_status,
        payload.status,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/reopen")
def reopen_ticket(
    ticket_id: int,
    payload: TicketReopenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    if ticket.status not in ("resolved", "closed"):
        raise HTTPException(status_code=400, detail="Only resolved or closed tickets can be reopened.")

    now = datetime.now(timezone.utc)
    old_status = ticket.status
    ticket.status = "reopened"
    ticket.reopened_at = now
    ticket.reopen_count = (ticket.reopen_count or 0) + 1
    ticket.reopen_reason = payload.reason.strip()
    ticket.resolved_at = None

    if ticket.sla_tracking:
        ticket.sla_tracking.resolved_at = None
        ticket.sla_tracking.current_state = compute_sla_state(ticket.sla_tracking, "reopened", now)

    db.add(
        TicketMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            message=f"Ticket reopened: {payload.reason.strip()}",
            visibility="public",
            created_at=now,
        )
    )
    record_ticket_event(
        db,
        ticket.id,
        "ticket_reopened",
        f"{current_user.name} reopened ticket. Reason: {payload.reason.strip()}",
        current_user.id,
        old_status,
        "reopened",
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/rate")
def rate_ticket(
    ticket_id: int,
    payload: TicketRatingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    ticket.satisfaction_rating = payload.rating
    ticket.satisfaction_comment = payload.comment.strip() if payload.comment else None
    record_ticket_event(
        db,
        ticket.id,
        "feedback_rated",
        f"Customer submitted satisfaction rating: {payload.rating}/5.",
        current_user.id,
        new_value=str(payload.rating),
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/relations", status_code=status.HTTP_201_CREATED)
def confirm_ticket_relation(
    ticket_id: int,
    payload: TicketRelationCreateRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    if ticket_id == payload.related_ticket_id:
        raise HTTPException(status_code=400, detail="A ticket cannot be related to itself.")

    src = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    rel_target = db.query(Ticket).filter(Ticket.id == payload.related_ticket_id).first()
    if not src or not rel_target:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    existing = (
        db.query(TicketRelation)
        .filter(
            TicketRelation.source_ticket_id == ticket_id,
            TicketRelation.related_ticket_id == payload.related_ticket_id,
            TicketRelation.relation_type == payload.relation_type,
        )
        .first()
    )
    if existing:
        return {"id": existing.id, "message": "Relation already recorded."}

    rel = TicketRelation(
        source_ticket_id=ticket_id,
        related_ticket_id=payload.related_ticket_id,
        relation_type=payload.relation_type,
        similarity_score=payload.similarity_score,
        confirmed_by=current_user.id,
    )
    db.add(rel)
    record_ticket_event(
        db,
        ticket_id,
        "relation_linked",
        f"{current_user.name} marked {rel_target.ticket_reference} as {payload.relation_type}.",
        current_user.id,
    )
    db.commit()
    db.refresh(rel)
    return {"id": rel.id, "relation_type": rel.relation_type, "related_ticket_id": rel.related_ticket_id}


@router.post("/{ticket_id}/escalate")
def escalate_ticket_sla(
    ticket_id: int,
    reason: str = Query("Manual SLA escalation triggered by staff."),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket or not ticket.sla_tracking:
        raise HTTPException(status_code=404, detail="Ticket SLA tracking record not found.")
    _ensure_ticket_access(ticket, current_user)

    now = datetime.now(timezone.utc)
    ticket.sla_tracking.escalated = True
    ticket.sla_tracking.escalated_at = now
    ticket.sla_tracking.escalation_notes = reason
    record_ticket_event(
        db,
        ticket.id,
        "sla_escalated",
        f"SLA escalated by {current_user.name}: {reason}",
        current_user.id,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.post("/{ticket_id}/verify")
def verify_and_report_ticket(
    ticket_id: int,
    payload: TicketVerifyRequest,
    request: Request,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    QRYVANTA Pre-Verification & Company Handoff workflow:
    Staff verifies customer evidence (order/return/charge proof), records findings and a
    direct recommended action, and updates company reporting status so the target company
    can act without redundant investigation.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    now = datetime.now(timezone.utc)
    old_status = ticket.verification_status or "unverified"
    ticket.verification_status = payload.verification_status
    ticket.verification_notes = payload.verification_notes.strip()
    if payload.recommended_company_action is not None:
        ticket.recommended_company_action = payload.recommended_company_action.strip() or None
    if payload.company_case_reference is not None:
        ticket.company_case_reference = payload.company_case_reference.strip() or None

    if payload.verification_status in ("verified_ready", "reported_to_company", "company_acknowledged", "company_resolved"):
        if ticket.verified_at is None:
            ticket.verified_at = now
        ticket.verified_by = current_user.id

    if payload.verification_status in ("reported_to_company", "company_acknowledged", "company_resolved"):
        if ticket.reported_to_company_at is None:
            ticket.reported_to_company_at = now

    label_readable = payload.verification_status.replace("_", " ")
    company_label = ticket.company.name if ticket.company else "target company"
    record_ticket_event(
        db,
        ticket.id,
        "verification_updated",
        f"{current_user.name} updated verification status to '{label_readable}' for {company_label}.",
        current_user.id,
        old_value=old_status,
        new_value=payload.verification_status,
    )
    log_audit_event(
        db,
        action="ticket.verify",
        entity_type="ticket",
        entity_id=ticket.id,
        user_id=current_user.id,
        details={
            "verification_status": payload.verification_status,
            "company_id": ticket.company_id,
            "company_case_reference": ticket.company_case_reference,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(ticket)
    return serialize_ticket_detail(db, ticket, current_user)


@router.get("/{ticket_id}/company-report")
def get_company_handoff_report(
    ticket_id: int,
    download: bool = Query(False),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """Return a structured company-ready verification & resolution handoff brief."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    _ensure_ticket_access(ticket, current_user)

    report = build_company_handoff_report(ticket)
    if download:
        return StreamingResponse(
            iter([report["report_markdown"]]),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={ticket.ticket_reference}_company_handoff_brief.md"
            },
        )
    return report
