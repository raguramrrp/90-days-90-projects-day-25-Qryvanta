"""
Customer Impact Analysis Service (Phase 1).
Provides transparent, database-backed customer impact counts for tickets and incidents.
Explicitly distinguishes unique affected customers from total ticket counts.
Never fabricates customer lifetime value (LTV) or revenue figures.
"""

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models.incidents import Incident, IncidentTicket
from app.models.ticket import Ticket, TicketRelation
from app.services.routing_service import OPEN_TICKET_STATUSES


def compute_ticket_customer_impact(db: Session, ticket: Ticket) -> Dict[str, Any]:
    """Calculate transparent customer impact metrics for a single ticket (staff-facing)."""
    cust_tickets = (
        db.query(Ticket)
        .filter(Ticket.customer_id == ticket.customer_id)
        .order_by(Ticket.created_at.desc())
        .all()
    )

    total_customer_history = len(cust_tickets)
    customer_unresolved = sum(1 for t in cust_tickets if t.status in OPEN_TICKET_STATUSES)
    customer_same_category = (
        sum(1 for t in cust_tickets if ticket.category_id and t.category_id == ticket.category_id)
        if ticket.category_id
        else 0
    )
    customer_repeat_complaints = max(0, customer_same_category - 1)

    # Related incidents linked to this ticket
    inc_links = (
        db.query(IncidentTicket)
        .join(Incident, IncidentTicket.incident_id == Incident.id)
        .filter(IncidentTicket.ticket_id == ticket.id, Incident.status != "dismissed")
        .all()
    )
    linked_incidents: List[Dict[str, Any]] = []
    co_affected_customers = {ticket.customer_id}
    related_problem_ticket_ids = {ticket.id}

    for lnk in inc_links:
        inc = lnk.incident
        if not inc:
            continue
        inc_tickets = [il.ticket for il in inc.ticket_links if il.ticket is not None]
        inc_unique_custs = {it.customer_id for it in inc_tickets}
        co_affected_customers.update(inc_unique_custs)
        related_problem_ticket_ids.update(it.id for it in inc_tickets)
        linked_incidents.append(
            {
                "id": inc.id,
                "incident_reference": inc.incident_reference,
                "title": inc.title,
                "status": inc.status,
                "severity": inc.severity,
                "ticket_count": len(inc_tickets),
                "affected_customer_count": len(inc_unique_custs),
            }
        )

    # Also include confirmed duplicate/related ticket relations
    relations = (
        db.query(TicketRelation)
        .filter(
            (TicketRelation.source_ticket_id == ticket.id)
            | (TicketRelation.related_ticket_id == ticket.id)
        )
        .all()
    )
    for rel in relations:
        other = rel.related_ticket if rel.source_ticket_id == ticket.id else rel.source_ticket
        if other:
            related_problem_ticket_ids.add(other.id)
            co_affected_customers.add(other.customer_id)

    prior_history = [
        {
            "id": t.id,
            "ticket_reference": t.ticket_reference,
            "subject": t.subject,
            "status": t.status,
            "category_name": t.category.name if t.category else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in cust_tickets
        if t.id != ticket.id
    ][:5]

    return {
        "unique_affected_customers": len(co_affected_customers),
        "related_problem_ticket_count": len(related_problem_ticket_ids),
        "related_incident_count": len(linked_incidents),
        "linked_incidents": linked_incidents,
        "customer_total_tickets": total_customer_history,
        "customer_unresolved_tickets": customer_unresolved,
        "customer_repeat_complaints_same_category": customer_repeat_complaints,
        "customer_prior_history": prior_history,
        "summary_note": (
            f"{len(related_problem_ticket_ids)} ticket(s) from {len(co_affected_customers)} unique customer(s) "
            f"linked to this issue. This customer has {customer_unresolved} unresolved ticket(s) out of {total_customer_history} total."
        ),
    }
