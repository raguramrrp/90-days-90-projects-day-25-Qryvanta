"""Operations (SLA Risk & Workload) and Resolution Intelligence Router (Phases 2 & 3)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.incidents import KnowledgeGap, ResolutionFeedback
from app.models.intelligence import KnowledgeArticle
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.schemas import KnowledgeGapDraftRequest, ResolutionFeedbackCreateRequest
from app.services.audit_service import log_audit_event
from app.services.auth_service import get_current_user, require_roles
from app.services.operations_service import compute_risk_and_workload_overview
from app.services.resolution_service import (
    compute_resolution_effectiveness,
    detect_knowledge_gaps,
    find_similar_resolved_tickets,
)

router = APIRouter(tags=["Operations & Resolution Intelligence"])


@router.get("/api/operations/overview")
def operations_risk_and_workload(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_risk_and_workload_overview(db)


@router.get("/api/resolution/similar/{ticket_id}")
def get_similar_resolved_for_ticket(
    ticket_id: int,
    threshold: float = Query(0.15, ge=0.05, le=0.90),
    top_k: int = Query(5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    if current_user.role == "customer":
        if not current_user.customer_profile or ticket.customer_id != current_user.customer_profile.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    items = find_similar_resolved_tickets(db, ticket, current_user, threshold=threshold, top_k=top_k)
    return {"ticket_id": ticket.id, "similar_resolved": items}


@router.post("/api/resolution/feedback", status_code=status.HTTP_201_CREATED)
def submit_resolution_feedback(
    payload: ResolutionFeedbackCreateRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    fb = ResolutionFeedback(
        ticket_id=payload.ticket_id,
        source_ticket_id=payload.source_ticket_id,
        article_id=payload.article_id,
        recommendation_type=payload.recommendation_type,
        rating=payload.rating,
        applied_to_reply=payload.applied_to_reply,
        submitted_by=current_user.id,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {
        "id": fb.id,
        "rating": fb.rating,
        "applied_to_reply": fb.applied_to_reply,
        "created_at": fb.created_at.isoformat(),
    }


@router.get("/api/resolution/overview")
def resolution_intelligence_overview(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    gaps = detect_knowledge_gaps(db)
    effectiveness = compute_resolution_effectiveness(db)

    # Pull recent genuine resolved tickets with clear public resolution replies for quick reference
    resolved_recent = (
        db.query(Ticket)
        .filter(Ticket.status.in_(("resolved", "closed")))
        .order_by(Ticket.resolved_at.desc())
        .limit(30)
        .all()
    )
    verified_resolutions = []
    for t in resolved_recent:
        staff_msgs = [
            m for m in t.messages if m.visibility == "public" and m.sender and m.sender.role in ("agent", "manager", "admin")
        ]
        if not staff_msgs:
            continue
        verified_resolutions.append(
            {
                "ticket_id": t.id,
                "ticket_reference": t.ticket_reference,
                "subject": t.subject,
                "category_name": t.category.name if t.category else "Uncategorized",
                "department_name": t.department.name if t.department else "General",
                "resolution_excerpt": staff_msgs[-1].message.strip(),
                "reopened": (t.reopen_count or 0) > 0,
                "satisfaction_rating": t.satisfaction_rating,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            }
        )
        if len(verified_resolutions) >= 10:
            break

    recent_fb = (
        db.query(ResolutionFeedback)
        .order_by(ResolutionFeedback.created_at.desc())
        .limit(15)
        .all()
    )

    return {
        "effectiveness": effectiveness,
        "knowledge_gaps": gaps,
        "recent_verified_resolutions": verified_resolutions,
        "recent_feedback": [
            {
                "id": f.id,
                "ticket_id": f.ticket_id,
                "ticket_reference": f.ticket.ticket_reference if f.ticket else None,
                "source_ticket_reference": f.source_ticket.ticket_reference if f.source_ticket else None,
                "article_title": f.article.title if f.article else None,
                "recommendation_type": f.recommendation_type,
                "rating": f.rating,
                "applied_to_reply": f.applied_to_reply,
                "submitted_by": f.submitter.name if f.submitter else None,
                "created_at": f.created_at.isoformat(),
            }
            for f in recent_fb
        ],
    }


@router.post("/api/resolution/knowledge-gaps/{gap_id}/draft", status_code=status.HTTP_201_CREATED)
def create_draft_article_from_gap(
    gap_id: int,
    payload: KnowledgeGapDraftRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Create an UNPUBLISHED draft Knowledge Base article from a detected knowledge gap."""
    gap = db.query(KnowledgeGap).filter(KnowledgeGap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=404, detail="Knowledge gap not found.")

    symptoms_str = ", ".join(gap.common_symptoms or [])
    draft_title = payload.title.strip() if payload.title else gap.suggested_title
    draft_content = (
        payload.content.strip()
        if payload.content
        else (
            f"DRAFT — Pending editorial review before publishing.\n\n"
            f"Topic: {gap.topic}\n"
            f"Observed across {gap.related_ticket_count} ticket(s).\n"
            f"Common symptoms / terms: {symptoms_str or 'Review recent tickets for recurring indicators'}.\n\n"
            "Recommended Troubleshooting Steps:\n"
            "1. Verify customer account/order reference and error details.\n"
            "2. Confirm whether an active incident is linked.\n"
            "3. Document verified resolution steps here before publishing."
        )
    )

    # Never auto-publish drafts created from knowledge gaps
    article = KnowledgeArticle(
        title=draft_title,
        content=draft_content,
        category_id=gap.category_id,
        tags=",".join((gap.common_symptoms or [])[:5]) or "draft,knowledge-gap",
        is_published=False,
    )
    db.add(article)
    db.flush()

    gap.status = "draft_created"
    gap.draft_article_id = article.id
    log_audit_event(
        db,
        action="knowledge_gap.create_draft",
        entity_type="knowledge_article",
        entity_id=article.id,
        user_id=current_user.id,
        details={"gap_id": gap.id, "title": article.title, "is_published": False},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(article)
    return {
        "gap_id": gap.id,
        "article_id": article.id,
        "title": article.title,
        "is_published": article.is_published,
        "message": "Unpublished draft Knowledge Base article created for manager review.",
    }


@router.patch("/api/resolution/knowledge-gaps/{gap_id}/dismiss")
def dismiss_knowledge_gap(
    gap_id: int,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    gap = db.query(KnowledgeGap).filter(KnowledgeGap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=404, detail="Knowledge gap not found.")
    gap.status = "dismissed"
    db.commit()
    return {"id": gap.id, "status": "dismissed"}
