"""Intelligence Router: Classification, Bulk Classification, Similar Tickets, and Human-in-the-Loop Feedback."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.intelligence import TicketFeedback, TicketPrediction
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.schemas import BulkClassifyRequest, ClassifyRequest
from app.services.analytics_service import (
    compute_classification_and_feedback_analytics,
    compute_customer_experience_and_trends,
)
from app.services.auth_service import get_current_user, require_roles
from app.services.intelligence_service import (
    classify_ticket_text,
    search_similar_tickets_for_user,
)
from app.services.routing_service import get_routing_thresholds

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence"])


@router.post("/classify")
def classify_single(
    payload: ClassifyRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    try:
        return classify_ticket_text(db, payload.subject, payload.description, payload.product_reference)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/bulk-classify")
def classify_bulk(
    payload: BulkClassifyRequest,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    results = []
    for idx, item in enumerate(payload.items):
        try:
            res = classify_ticket_text(db, item.subject, item.description, item.product_reference)
            results.append({"index": idx, "status": "ok", "prediction": res})
        except ValueError as exc:
            results.append({"index": idx, "status": "error", "error": str(exc)})
    return {"count": len(results), "results": results}


@router.get("/predictions/{ticket_id}")
def get_ticket_predictions(
    ticket_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    preds = (
        db.query(TicketPrediction)
        .filter(TicketPrediction.ticket_id == ticket_id)
        .order_by(TicketPrediction.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "ticket_id": p.ticket_id,
            "model_version": p.model_version.version if p.model_version else "rule_based_fallback",
            "predicted_category": p.predicted_category.name if p.predicted_category else None,
            "predicted_subcategory": p.predicted_subcategory.name if p.predicted_subcategory else None,
            "suggested_department": p.suggested_department.name if p.suggested_department else None,
            "final_department": p.final_department.name if p.final_department else None,
            "suggested_priority": p.suggested_priority,
            "confidence": p.confidence,
            "alternative_predictions": p.alternative_predictions or [],
            "explanation": p.explanation,
            "routing_rule_applied": p.routing_rule_applied,
            "routing_decision": p.routing_decision,
            "override_reason": p.override_reason,
            "created_at": p.created_at.isoformat(),
        }
        for p in preds
    ]


@router.get("/similar/{ticket_id}")
def get_similar_tickets(
    ticket_id: int,
    threshold: Optional[float] = Query(None, ge=0.05, le=0.95),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    if current_user.role == "customer":
        if not current_user.customer_profile or ticket.customer_id != current_user.customer_profile.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    similar = search_similar_tickets_for_user(db, ticket, current_user, threshold=threshold, top_k=top_k)
    return {"ticket_id": ticket.id, "ticket_reference": ticket.ticket_reference, "similar_tickets": similar}


@router.get("/feedback")
def get_feedback_analytics(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    stats = compute_classification_and_feedback_analytics(db)
    recent = (
        db.query(TicketFeedback)
        .order_by(TicketFeedback.created_at.desc())
        .limit(30)
        .all()
    )
    _, med_t = get_routing_thresholds(db)
    low_conf = (
        db.query(TicketPrediction)
        .filter(TicketPrediction.confidence < med_t)
        .order_by(TicketPrediction.created_at.desc())
        .limit(20)
        .all()
    )
    cx = compute_customer_experience_and_trends(db)

    return {
        **stats,
        "sentiment_distribution": cx["sentiment_distribution"],
        "demand_alerts": cx["demand_alerts"],
        "recent_corrections": [
            {
                "id": fb.id,
                "ticket_id": fb.ticket_id,
                "ticket_reference": fb.ticket.ticket_reference if fb.ticket else None,
                "ticket_subject": fb.ticket.subject if fb.ticket else None,
                "original_category": (
                    fb.prediction.predicted_category.name
                    if (fb.prediction and fb.prediction.predicted_category)
                    else None
                ),
                "corrected_category": fb.corrected_category.name if fb.corrected_category else None,
                "corrected_priority": fb.corrected_priority,
                "corrected_department": fb.corrected_department.name if fb.corrected_department else None,
                "correction_reason": fb.correction_reason,
                "corrected_by": fb.corrector.name if fb.corrector else None,
                "model_version": fb.model_version.version if fb.model_version else "rule_based_fallback",
                "created_at": fb.created_at.isoformat(),
            }
            for fb in recent
        ],
        "low_confidence_predictions": [
            {
                "ticket_id": p.ticket_id,
                "ticket_reference": p.ticket.ticket_reference if p.ticket else None,
                "subject": p.ticket.subject if p.ticket else None,
                "predicted_category": p.predicted_category.name if p.predicted_category else None,
                "confidence": p.confidence,
                "routing_decision": p.routing_decision,
                "status": p.ticket.status if p.ticket else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in low_conf
            if p.ticket is not None
        ],
    }
