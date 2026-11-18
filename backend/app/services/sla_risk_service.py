"""
Transparent Rule-Based SLA Breach Risk Engine (Phase 2).
Uses existing SLA tracking as the strict source of truth.
Explicitly labeled `deterministic_risk_rules` (never pretends to be a trained ML model).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.services.routing_service import OPEN_TICKET_STATUSES, get_agent_open_workload
from app.services.sla_service import compute_sla_metrics, ensure_utc


def _historical_category_avg_resolution(db: Session, category_id: Optional[int]) -> Optional[float]:
    if not category_id:
        return None
    resolved = (
        db.query(Ticket)
        .filter(
            Ticket.category_id == category_id,
            Ticket.resolved_at.isnot(None),
        )
        .all()
    )
    durations = []
    for t in resolved:
        mins = (ensure_utc(t.resolved_at) - ensure_utc(t.created_at)).total_seconds() / 60.0
        if mins >= 0:
            durations.append(mins)
    if len(durations) < 3:
        return None
    return round(sum(durations) / len(durations), 1)


def compute_ticket_sla_risk(
    db: Session,
    ticket: Ticket,
    dept_open_counts: Optional[Dict[int, int]] = None,
    agent_open_counts: Optional[Dict[int, int]] = None,
    category_avg_res: Optional[Dict[int, Optional[float]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Estimate SLA breach risk for an open ticket using transparent weighted operational rules.
    Returns risk_level (low|moderate|high|critical), score (0-100), contributing factors,
    remaining SLA time, and recommended action.
    """
    current = ensure_utc(now or datetime.now(timezone.utc))

    if not ticket.sla_tracking:
        return {
            "risk_level": "low",
            "risk_score": 0,
            "method": "deterministic_risk_rules",
            "sla_state": "unknown",
            "remaining_sla_minutes": None,
            "factors": ["No SLA policy tracking record attached to this ticket."],
            "recommended_action": "Verify SLA policy coverage in Settings.",
        }

    sla = compute_sla_metrics(ticket.sla_tracking, ticket.created_at, ticket.status, current)
    state = sla["current_state"]
    rem = sla["time_remaining_minutes"]

    if state == "completed":
        return {
            "risk_level": "low",
            "risk_score": 0,
            "method": "deterministic_risk_rules",
            "sla_state": "completed",
            "remaining_sla_minutes": 0.0,
            "factors": ["Ticket is resolved/closed; SLA clock is complete."],
            "recommended_action": "No action required.",
        }

    if state == "paused":
        return {
            "risk_level": "low",
            "risk_score": 15,
            "method": "deterministic_risk_rules",
            "sla_state": "paused",
            "remaining_sla_minutes": rem,
            "factors": ["SLA clock is currently paused awaiting customer response."],
            "recommended_action": "Follow up with customer if no reply arrives within 24 hours.",
        }

    score = 0
    factors: List[str] = []

    # 1. Remaining SLA time vs policy window
    if state == "overdue" or (rem is not None and rem <= 0):
        score += 65
        factors.append(f"SLA deadline already exceeded ({abs(round(rem or 0))} min overdue).")
    elif rem is not None and rem <= 60:
        score += 48
        factors.append(f"Less than 1 hour remaining before resolution deadline ({round(rem)} min left).")
    elif rem is not None and rem <= 240:
        score += 32
        factors.append(f"Under 4 hours remaining before SLA deadline ({round(rem / 60, 1)}h left).")
    elif rem is not None and rem <= 720:
        score += 18
        factors.append(f"Resolution deadline within 12 hours ({round(rem / 60, 1)}h left).")
    else:
        score += 5

    # 2. First response still missing
    if sla["first_responded_at"] is None:
        fr_rem = (sla["first_response_deadline"] - current).total_seconds() / 60.0
        if fr_rem <= 0:
            score += 20
            factors.append("First public agent response is overdue.")
        elif fr_rem <= 30:
            score += 14
            factors.append(f"First response due within {max(1, round(fr_rem))} minutes.")

    # 3. Priority weight
    if ticket.priority == "critical":
        score += 18
        factors.append("Critical priority carries strict SLA targets.")
    elif ticket.priority == "high":
        score += 10
        factors.append("High priority ticket.")

    # 4. Unassigned or overloaded agent
    if ticket.assigned_agent_id is None:
        score += 18
        factors.append("Ticket has no assigned agent.")
    elif ticket.assigned_agent:
        if agent_open_counts is not None:
            ag_open = agent_open_counts.get(ticket.assigned_agent_id, 0)
        else:
            ag_open = get_agent_open_workload(db, ticket.assigned_agent_id)
        max_cap = max(ticket.assigned_agent.max_open_tickets or 15, 1)
        util = ag_open / max_cap
        if util >= 1.0:
            score += 15
            factors.append(f"Assigned agent is at or over capacity ({ag_open}/{max_cap} open tickets).")
        elif util >= 0.75:
            score += 8
            factors.append(f"Assigned agent is nearing capacity ({ag_open}/{max_cap} open tickets).")

    # 5. Department backlog pressure
    if ticket.department_id is not None:
        if dept_open_counts is not None:
            dept_open = dept_open_counts.get(ticket.department_id, 0)
        else:
            dept_open = (
                db.query(Ticket)
                .filter(Ticket.department_id == ticket.department_id, Ticket.status.in_(OPEN_TICKET_STATUSES))
                .count()
            )
        if dept_open >= 12:
            score += 10
            factors.append(f"Department backlog is elevated ({dept_open} open tickets).")

    # 6. Historical category resolution duration vs remaining time
    if ticket.category_id and rem is not None and rem > 0:
        if category_avg_res is not None and ticket.category_id in category_avg_res:
            hist_avg = category_avg_res[ticket.category_id]
        else:
            hist_avg = _historical_category_avg_resolution(db, ticket.category_id)
        if hist_avg is not None and rem < hist_avg * 0.75:
            score += 12
            factors.append(
                f"Remaining time ({round(rem / 60, 1)}h) is shorter than historical category avg ({round(hist_avg / 60, 1)}h)."
            )

    # 7. Reopened ticket pressure
    if (ticket.reopen_count or 0) > 0:
        score += 10
        factors.append(f"Ticket has been reopened {ticket.reopen_count} time(s).")

    score = min(100, score)
    if score >= 75:
        risk_level = "critical"
    elif score >= 50:
        risk_level = "high"
    elif score >= 25:
        risk_level = "moderate"
    else:
        risk_level = "low"

    if ticket.assigned_agent_id is None and risk_level in ("critical", "high"):
        action = "Assign immediately to an available department specialist with lowest active workload."
    elif state == "overdue":
        action = "Escalate immediately, notify department lead, and send a status update to the customer."
    elif risk_level == "critical":
        action = "Prioritize active investigation or reassign from overloaded queue before breach."
    elif risk_level == "high":
        action = "Review queue ordering and send first/follow-up response before approaching deadline."
    elif risk_level == "moderate":
        action = "Monitor progress within normal shift SLA window."
    else:
        action = "On track under standard handling."

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "method": "deterministic_risk_rules",
        "sla_state": state,
        "remaining_sla_minutes": rem,
        "factors": factors or ["Sufficient SLA buffer and balanced workload."],
        "recommended_action": action,
    }


def build_risk_caches(db: Session) -> tuple[Dict[int, int], Dict[int, int], Dict[int, Optional[float]]]:
    """Precompute department backlogs, agent open loads, and category resolution averages for batch evaluation."""
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(OPEN_TICKET_STATUSES)).all()
    dept_counts: Dict[int, int] = {}
    agent_counts: Dict[int, int] = {}
    for t in open_tickets:
        if t.department_id:
            dept_counts[t.department_id] = dept_counts.get(t.department_id, 0) + 1
        if t.assigned_agent_id:
            agent_counts[t.assigned_agent_id] = agent_counts.get(t.assigned_agent_id, 0) + 1

    resolved = db.query(Ticket).filter(Ticket.resolved_at.isnot(None), Ticket.category_id.isnot(None)).all()
    cat_durations: Dict[int, List[float]] = {}
    for t in resolved:
        mins = (ensure_utc(t.resolved_at) - ensure_utc(t.created_at)).total_seconds() / 60.0
        if mins >= 0:
            cat_durations.setdefault(t.category_id, []).append(mins)
    cat_avgs: Dict[int, Optional[float]] = {
        cid: (round(sum(vals) / len(vals), 1) if len(vals) >= 3 else None)
        for cid, vals in cat_durations.items()
    }
    return dept_counts, agent_counts, cat_avgs
