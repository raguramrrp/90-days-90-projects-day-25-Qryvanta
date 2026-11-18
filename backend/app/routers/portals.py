"""Portals & Companies Router: manage target platforms/companies and portal-wise reporting."""

from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.operations import Company
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.schemas import CompanyCreateRequest, CompanyUpdateRequest
from app.services.audit_service import log_audit_event
from app.services.auth_service import get_current_user, require_roles
from app.services.routing_service import OPEN_TICKET_STATUSES
from app.services.sla_service import compute_sla_metrics

router = APIRouter(tags=["Portals & Companies"])

PLATFORM_TYPES = [
    "E-Commerce",
    "SaaS / Software",
    "Fintech / Payments",
    "Logistics / Courier",
    "Hardware & Devices",
]


@router.get("/api/companies")
def list_companies(
    platform_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if platform_type:
        q = q.filter(Company.platform_type == platform_type)
    if active_only:
        q = q.filter(Company.is_active.is_(True))
    companies = q.order_by(Company.platform_type.asc(), Company.name.asc()).all()

    is_staff = current_user.role in ("agent", "manager", "admin")
    rows = []
    for c in companies:
        item = {
            "id": c.id,
            "name": c.name,
            "platform_type": c.platform_type,
            "portal_url": c.portal_url,
            "support_email": c.support_email,
            "description": c.description,
            "is_active": c.is_active,
        }
        if is_staff:
            tkts = c.tickets
            total = len(tkts)
            verified_count = sum(
                1
                for t in tkts
                if t.verification_status in ("verified_ready", "reported_to_company", "company_acknowledged", "company_resolved")
            )
            reported_count = sum(
                1
                for t in tkts
                if t.verification_status in ("reported_to_company", "company_acknowledged", "company_resolved")
            )
            resolved_count = sum(1 for t in tkts if t.status in ("resolved", "closed") or t.verification_status == "company_resolved")
            open_count = sum(1 for t in tkts if t.status in OPEN_TICKET_STATUSES)
            item.update(
                {
                    "total_tickets": total,
                    "open_tickets": open_count,
                    "verified_tickets": verified_count,
                    "reported_tickets": reported_count,
                    "resolved_tickets": resolved_count,
                    "verification_rate": round((verified_count / total) * 100.0, 1) if total else 0.0,
                }
            )
        rows.append(item)

    return {"platform_types": PLATFORM_TYPES, "companies": rows}


@router.post("/api/companies", status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    if db.query(Company).filter(Company.name == payload.name.strip()).first():
        raise HTTPException(status_code=409, detail="A company with this name already exists.")

    comp = Company(
        name=payload.name.strip(),
        platform_type=payload.platform_type.strip(),
        portal_url=payload.portal_url.strip() if payload.portal_url else None,
        support_email=payload.support_email.strip().lower() if payload.support_email else None,
        description=payload.description.strip() if payload.description else None,
        is_active=True,
    )
    db.add(comp)
    db.flush()
    log_audit_event(
        db,
        action="company.create",
        entity_type="company",
        entity_id=comp.id,
        user_id=current_user.id,
        details={"name": comp.name, "platform_type": comp.platform_type},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(comp)
    return {"id": comp.id, "name": comp.name, "platform_type": comp.platform_type}


@router.patch("/api/companies/{company_id}")
def update_company(
    company_id: int,
    payload: CompanyUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    comp = db.query(Company).filter(Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(comp, k, v.strip() if isinstance(v, str) else v)
    log_audit_event(
        db,
        action="company.update",
        entity_type="company",
        entity_id=comp.id,
        user_id=current_user.id,
        details=payload.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"id": comp.id, "status": "updated"}


@router.get("/api/analytics/portals")
def analytics_portals(
    platform_type: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """Portal-wise and company-wise ticket volume, verification pipeline, and handoff status report."""
    q = db.query(Ticket)
    if platform_type:
        q = q.filter(Ticket.platform_type == platform_type)
    tickets = q.all()

    portal_agg = defaultdict(
        lambda: {
            "platform_type": "",
            "total": 0,
            "open": 0,
            "resolved": 0,
            "unverified": 0,
            "under_verification": 0,
            "verified_ready": 0,
            "reported_to_company": 0,
            "company_acknowledged": 0,
            "company_resolved": 0,
            "insufficient_proof": 0,
        }
    )

    company_agg = defaultdict(
        lambda: {
            "company_id": None,
            "company_name": "Unspecified Company",
            "platform_type": "Unspecified",
            "support_email": None,
            "total": 0,
            "open": 0,
            "unverified": 0,
            "verified_ready": 0,
            "reported_to_company": 0,
            "company_acknowledged": 0,
            "company_resolved": 0,
            "sla_completed": 0,
            "sla_met": 0,
        }
    )

    verification_summary = defaultdict(int)

    for t in tickets:
        p_key = t.platform_type or (t.company.platform_type if t.company else "General / Unspecified")
        v_st = t.verification_status or "unverified"
        verification_summary[v_st] += 1

        p_row = portal_agg[p_key]
        p_row["platform_type"] = p_key
        p_row["total"] += 1
        if t.status in OPEN_TICKET_STATUSES:
            p_row["open"] += 1
        if t.status in ("resolved", "closed"):
            p_row["resolved"] += 1
        if v_st in p_row:
            p_row[v_st] += 1

        c_key = t.company_id or 0
        c_row = company_agg[c_key]
        c_row["company_id"] = t.company_id
        c_row["company_name"] = t.company.name if t.company else "Direct / Unspecified"
        c_row["platform_type"] = p_key
        c_row["support_email"] = t.company.support_email if t.company else None
        c_row["total"] += 1
        if t.status in OPEN_TICKET_STATUSES:
            c_row["open"] += 1
        if v_st in c_row:
            c_row[v_st] += 1

        if t.sla_tracking:
            m = compute_sla_metrics(t.sla_tracking, t.created_at, t.status)
            if m["current_state"] == "completed":
                c_row["sla_completed"] += 1
                if not m["sla_breached"]:
                    c_row["sla_met"] += 1

    company_rows = []
    for row in company_agg.values():
        total = row["total"]
        verified_total = (
            row["verified_ready"]
            + row["reported_to_company"]
            + row["company_acknowledged"]
            + row["company_resolved"]
        )
        company_rows.append(
            {
                **row,
                "verification_rate": round((verified_total / total) * 100.0, 1) if total else 0.0,
                "sla_compliance_rate": (
                    round((row["sla_met"] / row["sla_completed"]) * 100.0, 1)
                    if row["sla_completed"] > 0
                    else None
                ),
            }
        )
    company_rows.sort(key=lambda r: r["total"], reverse=True)

    portal_rows = sorted(portal_agg.values(), key=lambda r: r["total"], reverse=True)

    return {
        "platform_types": PLATFORM_TYPES,
        "total_tickets": len(tickets),
        "verification_pipeline": [
            {"status": k, "count": verification_summary.get(k, 0)}
            for k in (
                "unverified",
                "under_verification",
                "verified_ready",
                "reported_to_company",
                "company_acknowledged",
                "company_resolved",
                "insufficient_proof",
            )
        ],
        "by_portal": portal_rows,
        "by_company": company_rows,
    }
