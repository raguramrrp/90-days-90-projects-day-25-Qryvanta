"""Core ticket lifecycle service: creation, replies, internal notes, assignment, reclassification, close/reopen."""

from datetime import datetime, timezone
import random
import string
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.incidents import Incident, IncidentTicket
from app.models.intelligence import TicketFeedback, TicketPrediction
from app.models.operations import Company
from app.models.ticket import (
    Category,
    Ticket,
    TicketAssignment,
    TicketEvent,
    TicketMessage,
)
from app.models.user import Agent, Customer, Department, User
from app.services.audit_service import log_audit_event
from app.services.customer_impact_service import compute_ticket_customer_impact
from app.services.intelligence_service import classify_ticket_text, recommend_knowledge_articles
from app.services.routing_service import recommend_agents
from app.services.sla_risk_service import compute_ticket_sla_risk
from app.services.sla_service import (
    compute_sla_metrics,
    compute_sla_state,
    create_or_update_sla_tracking,
    handle_sla_pause_resume,
)
from ml.sentiment.analyzer import analyze_conversation_trend


def generate_ticket_reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    for _ in range(20):
        suffix = "".join(random.choices(string.digits, k=5))
        ref = f"QRY-{year}-{suffix}"
        if not db.query(Ticket.id).filter(Ticket.ticket_reference == ref).first():
            return ref
    return f"QRY-{year}-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}"


def record_ticket_event(
    db: Session,
    ticket_id: int,
    event_type: str,
    description: str,
    actor_id: Optional[int] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> TicketEvent:
    ev = TicketEvent(
        ticket_id=ticket_id,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        event_description=description,
    )
    db.add(ev)
    return ev


def create_ticket_full(
    db: Session,
    customer: Customer,
    actor: User,
    subject: str,
    description: str,
    category_id: Optional[int] = None,
    subcategory_id: Optional[int] = None,
    product_reference: Optional[str] = None,
    company_id: Optional[int] = None,
    platform_type: Optional[str] = None,
    external_reference: Optional[str] = None,
    source: str = "web_portal",
    is_demo_data: bool = False,
    created_at_override: Optional[datetime] = None,
    ip_address: Optional[str] = None,
) -> Ticket:
    """
    Execute the complete 12-step ticket submission pipeline:
    validate -> generate reference -> classify -> priority -> department route ->
    SLA deadlines -> persist prediction -> recommend KB -> optional auto-assign -> return ticket.
    """
    intel = classify_ticket_text(db, subject, description, product_reference)

    chosen_cat_id = category_id if category_id is not None else intel["predicted_category_id"]
    chosen_sub_id = subcategory_id if subcategory_id is not None else intel["predicted_subcategory_id"]
    final_dept_id = intel["final_department_id"]
    assigned_agent_id = None

    resolved_platform_type = platform_type.strip() if platform_type else None
    if company_id is not None:
        comp = db.query(Company).filter(Company.id == company_id).first()
        if comp and not resolved_platform_type:
            resolved_platform_type = comp.platform_type

    # If auto-assign is enabled on the matched high-confidence rule, pick the top recommended agent
    if intel["auto_assign_agent"] and final_dept_id is not None:
        recs = recommend_agents(
            db,
            department_id=final_dept_id,
            category_name=intel["predicted_category_name"],
            priority=intel["suggested_priority"],
            limit=1,
        )
        if recs:
            assigned_agent_id = recs[0]["agent_id"]

    now = created_at_override or datetime.now(timezone.utc)
    ticket = Ticket(
        ticket_reference=generate_ticket_reference(db),
        customer_id=customer.id,
        subject=subject.strip(),
        description=description.strip(),
        product_reference=product_reference.strip() if product_reference else None,
        company_id=company_id,
        platform_type=resolved_platform_type,
        external_reference=external_reference.strip() if external_reference else None,
        verification_status="unverified",
        category_id=chosen_cat_id,
        subcategory_id=chosen_sub_id,
        priority=intel["suggested_priority"],
        priority_reason=intel["priority_reason"],
        department_id=final_dept_id,
        assigned_agent_id=assigned_agent_id,
        status="open" if assigned_agent_id else "new",
        source=source,
        is_demo_data=is_demo_data,
        sentiment_label=intel["sentiment"]["label"],
        sentiment_confidence=intel["sentiment"]["confidence"],
        sentiment_method=intel["sentiment"]["method"],
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()

    # Store prediction with model version and routing audit details
    prediction = TicketPrediction(
        ticket_id=ticket.id,
        model_version_id=intel["model_version_id"],
        predicted_category_id=intel["predicted_category_id"],
        predicted_subcategory_id=intel["predicted_subcategory_id"],
        suggested_department_id=intel["suggested_department_id"],
        final_department_id=final_dept_id,
        suggested_priority=intel["suggested_priority"],
        confidence=intel["confidence"],
        alternative_predictions=intel["alternatives"],
        explanation=intel["explanation"],
        routing_rule_applied=intel["routing_rule_applied"],
        routing_decision=intel["routing_decision"],
        created_at=now,
    )
    db.add(prediction)

    # Calculate SLA deadlines using business hours & holidays
    create_or_update_sla_tracking(db, ticket, reference_time=now)

    # Record initial creation event
    record_ticket_event(
        db,
        ticket.id,
        event_type="ticket_created",
        description=f"Ticket {ticket.ticket_reference} submitted via {source}.",
        actor_id=actor.id,
        new_value=ticket.status,
    )

    if assigned_agent_id:
        db.add(
            TicketAssignment(
                ticket_id=ticket.id,
                agent_id=assigned_agent_id,
                department_id=final_dept_id,
                assigned_by=None,
                assignment_reason="Automatic workload-balanced assignment under high-confidence routing rule.",
                assigned_at=now,
            )
        )
        record_ticket_event(
            db,
            ticket.id,
            event_type="ticket_assigned",
            description="Auto-assigned to eligible department agent based on workload rules.",
            actor_id=None,
            new_value=str(assigned_agent_id),
        )

    # Persist initial KB recommendations
    recommend_knowledge_articles(db, ticket, top_k=3, persist=True)

    log_audit_event(
        db,
        action="ticket.create",
        entity_type="ticket",
        entity_id=ticket.id,
        user_id=actor.id,
        details={"ticket_reference": ticket.ticket_reference, "routing_decision": intel["routing_decision"]},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def serialize_ticket_summary(ticket: Ticket, include_internal_fields: bool = True) -> Dict[str, Any]:
    sla_info = None
    if ticket.sla_tracking:
        sla_info = compute_sla_metrics(ticket.sla_tracking, ticket.created_at, ticket.status)

    latest_pred = ticket.predictions[0] if ticket.predictions else None

    data: Dict[str, Any] = {
        "id": ticket.id,
        "ticket_reference": ticket.ticket_reference,
        "subject": ticket.subject,
        "description": ticket.description,
        "product_reference": ticket.product_reference,
        "company_id": ticket.company_id,
        "company_name": ticket.company.name if ticket.company else None,
        "platform_type": ticket.platform_type or (ticket.company.platform_type if ticket.company else None),
        "external_reference": ticket.external_reference,
        "status": ticket.status,
        "is_demo_data": ticket.is_demo_data,
        "category_id": ticket.category_id,
        "category_name": ticket.category.name if ticket.category else None,
        "reopen_count": ticket.reopen_count,
        "satisfaction_rating": ticket.satisfaction_rating,
        "satisfaction_comment": ticket.satisfaction_comment,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "reopened_at": ticket.reopened_at.isoformat() if ticket.reopened_at else None,
    }

    if include_internal_fields:
        data.update(
            {
                "priority": ticket.priority,
                "source": ticket.source,
                "subcategory_id": ticket.subcategory_id,
                "subcategory_name": ticket.subcategory.name if ticket.subcategory else None,
                "department_id": ticket.department_id,
                "department_name": ticket.department.name if ticket.department else None,
                "verification_status": ticket.verification_status or "unverified",
                "company_case_reference": ticket.company_case_reference,
                "customer": {
                    "id": ticket.customer.id,
                    "customer_reference": ticket.customer.customer_reference,
                    "name": ticket.customer.user.name if ticket.customer.user else "Unknown",
                    "email": ticket.customer.user.email if ticket.customer.user else "",
                    "contact_information": ticket.customer.contact_information,
                }
                if ticket.customer
                else None,
                "assigned_agent": {
                    "id": ticket.assigned_agent.id,
                    "name": ticket.assigned_agent.user.name if ticket.assigned_agent.user else "Unknown",
                    "email": ticket.assigned_agent.user.email if ticket.assigned_agent.user else "",
                }
                if ticket.assigned_agent
                else None,
                "sla_state": sla_info["current_state"] if sla_info else "unknown",
                "sla_breached": sla_info["sla_breached"] if sla_info else False,
                "resolution_deadline": sla_info["resolution_deadline"].isoformat() if sla_info else None,
                "priority_reason": ticket.priority_reason,
                "sentiment": {
                    "label": ticket.sentiment_label,
                    "confidence": ticket.sentiment_confidence,
                    "method": ticket.sentiment_method,
                },
                "prediction_confidence": latest_pred.confidence if latest_pred else None,
                "routing_decision": latest_pred.routing_decision if latest_pred else None,
            }
        )
    else:
        data["has_assigned_support"] = ticket.assigned_agent_id is not None

    return data


def serialize_ticket_detail(db: Session, ticket: Ticket, viewer: User) -> Dict[str, Any]:
    """
    Serialize full ticket details with strict privacy boundaries:
    Customers NEVER receive internal notes, model internals, or agent-only metadata.
    """
    is_staff = viewer.role in ("agent", "manager", "admin")
    base = serialize_ticket_summary(ticket, include_internal_fields=is_staff)

    # Filter messages: strictly strip 'internal' visibility for customers
    messages = []
    customer_texts = [ticket.description]
    for msg in ticket.messages:
        if msg.visibility == "internal" and not is_staff:
            continue
        if msg.sender and msg.sender.role == "customer":
            customer_texts.append(msg.message)
        messages.append(
            {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_name": msg.sender.name if msg.sender else "System",
                "sender_role": msg.sender.role if msg.sender else "system",
                "message": msg.message,
                "visibility": msg.visibility,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
        )

    attachments = [
        {
            "id": att.id,
            "original_filename": att.original_filename,
            "mime_type": att.mime_type,
            "file_size": att.file_size,
            "uploaded_by": att.uploader.name if att.uploader else None,
            "created_at": att.created_at.isoformat() if att.created_at else None,
        }
        for att in ticket.attachments
    ]

    # Events visible to customers exclude internal-only actions
    customer_safe_events = {"ticket_created", "status_changed", "ticket_resolved", "ticket_closed", "ticket_reopened", "customer_reply", "agent_reply", "feedback_rated"}
    events = [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "actor_name": ev.actor.name if ev.actor else "System",
            "old_value": ev.old_value,
            "new_value": ev.new_value,
            "event_description": ev.event_description,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in ticket.events
        if is_staff or ev.event_type in customer_safe_events
    ]

    base["messages"] = messages
    base["attachments"] = attachments
    base["events"] = events
    base["reopen_reason"] = ticket.reopen_reason
    base["company"] = (
        {
            "id": ticket.company.id,
            "name": ticket.company.name,
            "platform_type": ticket.company.platform_type,
            "portal_url": ticket.company.portal_url,
            "support_email": ticket.company.support_email,
        }
        if ticket.company
        else None
    )
    if is_staff:
        base["verification"] = {
            "status": ticket.verification_status or "unverified",
            "notes": ticket.verification_notes,
            "recommended_company_action": ticket.recommended_company_action,
            "verified_by_name": ticket.verifier.name if ticket.verifier else None,
            "verified_at": ticket.verified_at.isoformat() if ticket.verified_at else None,
            "reported_to_company_at": ticket.reported_to_company_at.isoformat() if ticket.reported_to_company_at else None,
            "company_case_reference": ticket.company_case_reference,
        }
    else:
        # Customers see high-level status only, never internal verification notes
        base["verification"] = {
            "status": ticket.verification_status or "unverified",
            "company_case_reference": ticket.company_case_reference,
        }

    if ticket.sla_tracking and is_staff:
        sla = compute_sla_metrics(ticket.sla_tracking, ticket.created_at, ticket.status)
        base["sla"] = {
            **sla,
            "first_response_deadline": sla["first_response_deadline"].isoformat(),
            "resolution_deadline": sla["resolution_deadline"].isoformat(),
            "first_responded_at": sla["first_responded_at"].isoformat() if sla["first_responded_at"] else None,
            "resolved_at": sla["resolved_at"].isoformat() if sla["resolved_at"] else None,
            "escalated_at": sla["escalated_at"].isoformat() if sla["escalated_at"] else None,
        }

    if is_staff:
        latest_pred = ticket.predictions[0] if ticket.predictions else None
        base["prediction"] = (
            {
                "id": latest_pred.id,
                "model_version_id": latest_pred.model_version_id,
                "model_version": latest_pred.model_version.version if latest_pred.model_version else "rule_based_fallback",
                "predicted_category_id": latest_pred.predicted_category_id,
                "predicted_category_name": latest_pred.predicted_category.name if latest_pred.predicted_category else None,
                "predicted_subcategory_id": latest_pred.predicted_subcategory_id,
                "predicted_subcategory_name": latest_pred.predicted_subcategory.name if latest_pred.predicted_subcategory else None,
                "suggested_department_id": latest_pred.suggested_department_id,
                "suggested_department_name": latest_pred.suggested_department.name if latest_pred.suggested_department else None,
                "final_department_id": latest_pred.final_department_id,
                "final_department_name": latest_pred.final_department.name if latest_pred.final_department else None,
                "suggested_priority": latest_pred.suggested_priority,
                "confidence": latest_pred.confidence,
                "alternative_predictions": latest_pred.alternative_predictions or [],
                "explanation": latest_pred.explanation,
                "routing_rule_applied": latest_pred.routing_rule_applied,
                "routing_decision": latest_pred.routing_decision,
                "override_reason": latest_pred.override_reason,
                "created_at": latest_pred.created_at.isoformat() if latest_pred.created_at else None,
            }
            if latest_pred
            else None
        )

        base["feedback_history"] = [
            {
                "id": fb.id,
                "corrected_category_name": fb.corrected_category.name if fb.corrected_category else None,
                "corrected_subcategory_name": fb.corrected_subcategory.name if fb.corrected_subcategory else None,
                "corrected_priority": fb.corrected_priority,
                "corrected_department_name": fb.corrected_department.name if fb.corrected_department else None,
                "correction_reason": fb.correction_reason,
                "corrected_by_name": fb.corrector.name if fb.corrector else None,
                "created_at": fb.created_at.isoformat() if fb.created_at else None,
            }
            for fb in ticket.feedbacks
        ]

        trend, trend_points = analyze_conversation_trend(customer_texts)
        base["sentiment_trend"] = {"trend": trend, "points": trend_points}

        base["recommended_agents"] = recommend_agents(
            db,
            department_id=ticket.department_id or (latest_pred.suggested_department_id if latest_pred else None),
            category_name=ticket.category.name if ticket.category else None,
            priority=ticket.priority,
            limit=3,
        )

        base["knowledge_recommendations"] = recommend_knowledge_articles(db, ticket, top_k=3, persist=False)
        base["sla_risk"] = compute_ticket_sla_risk(db, ticket)
        base["customer_impact"] = compute_ticket_customer_impact(db, ticket)

    return base


def build_company_handoff_report(ticket: Ticket) -> Dict[str, Any]:
    """
    Generate a verified, investigation-ready handoff dossier for the target company
    so their support/finance/logistics team can resolve the customer's issue directly.
    """
    latest_pred = ticket.predictions[0] if ticket.predictions else None
    company_name = ticket.company.name if ticket.company else "Unassigned Company"
    platform = ticket.platform_type or (ticket.company.platform_type if ticket.company else "General Portal")
    cat_label = ticket.category.name if ticket.category else "Uncategorized"
    if ticket.subcategory:
        cat_label = f"{cat_label} / {ticket.subcategory.name}"

    attachments_list = [
        f"{a.original_filename} ({round(a.file_size / 1024, 1)} KB)"
        for a in ticket.attachments
    ]

    markdown_lines = [
        f"# QRYVANTA Verified Case Handoff Report — {ticket.ticket_reference}",
        "",
        "## 1. Target Platform & Company",
        f"- **Target Company:** {company_name}",
        f"- **Platform / Portal:** {platform}",
        f"- **Company Support Contact:** {ticket.company.support_email if (ticket.company and ticket.company.support_email) else 'N/A'}",
        f"- **External Order / Transaction Ref:** {ticket.external_reference or 'Not provided'}",
        f"- **Company Case Ref:** {ticket.company_case_reference or 'Pending company assignment'}",
        "",
        "## 2. Customer & Issue Summary",
        f"- **Customer Reference:** {ticket.customer.customer_reference if ticket.customer else 'N/A'}",
        f"- **Customer Name:** {ticket.customer.user.name if (ticket.customer and ticket.customer.user) else 'N/A'}",
        f"- **Customer Email:** {ticket.customer.user.email if (ticket.customer and ticket.customer.user) else 'N/A'}",
        f"- **Subject:** {ticket.subject}",
        f"- **Classified Category:** {cat_label}",
        f"- **Assessed Urgency:** {ticket.priority.upper()} ({ticket.priority_reason or 'Standard'})",
        f"- **Submitted At:** {ticket.created_at.isoformat() if ticket.created_at else 'N/A'}",
        "",
        "### Customer Statement",
        ticket.description,
        "",
        "## 3. QRYVANTA Pre-Verification & Evidence Summary",
        f"- **Verification Status:** {(ticket.verification_status or 'unverified').replace('_', ' ').title()}",
        f"- **Verified By:** {ticket.verifier.name if ticket.verifier else 'Pending staff verification'}",
        f"- **Verified At:** {ticket.verified_at.isoformat() if ticket.verified_at else 'Not yet verified'}",
        f"- **Reported To Company At:** {ticket.reported_to_company_at.isoformat() if ticket.reported_to_company_at else 'Not yet reported'}",
        f"- **Supporting Attachments ({len(attachments_list)}):** {', '.join(attachments_list) if attachments_list else 'None uploaded'}",
        f"- **ML Triage Confidence:** {round(latest_pred.confidence * 100, 1)}% ({latest_pred.model_version.version if (latest_pred and latest_pred.model_version) else 'rule-based'})" if latest_pred else "- **ML Triage Confidence:** N/A",
        "",
        "### Verification Findings",
        ticket.verification_notes or "No verification notes recorded yet.",
        "",
        "## 4. Recommended Direct Action for Company",
        ticket.recommended_company_action or "Pending verification recommendation.",
        "",
        "---",
        "*Generated by QRYVANTA Verification & Company Handoff Service to eliminate duplicate investigation and accelerate customer resolution.*",
    ]

    return {
        "ticket_id": ticket.id,
        "ticket_reference": ticket.ticket_reference,
        "company_name": company_name,
        "platform_type": platform,
        "external_reference": ticket.external_reference,
        "company_case_reference": ticket.company_case_reference,
        "verification_status": ticket.verification_status or "unverified",
        "verified_by": ticket.verifier.name if ticket.verifier else None,
        "verified_at": ticket.verified_at.isoformat() if ticket.verified_at else None,
        "reported_to_company_at": ticket.reported_to_company_at.isoformat() if ticket.reported_to_company_at else None,
        "category": cat_label,
        "priority": ticket.priority,
        "verification_notes": ticket.verification_notes,
        "recommended_company_action": ticket.recommended_company_action,
        "attachments": attachments_list,
        "report_markdown": "\n".join(markdown_lines),
    }
