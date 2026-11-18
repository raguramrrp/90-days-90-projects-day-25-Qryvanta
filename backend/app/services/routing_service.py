"""Confidence-based automatic department routing and deterministic agent assignment recommendations."""

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models.operations import AppSetting, RoutingRule
from app.models.ticket import Category, Ticket
from app.models.user import Agent, AgentDepartment, Department


OPEN_TICKET_STATUSES = ("new", "open", "in_progress", "awaiting_customer", "reopened")


def get_routing_thresholds(db: Session) -> Tuple[float, float]:
    """Read configurable high/medium confidence thresholds from AppSettings or env defaults."""
    settings = get_settings()
    high_t = settings.HIGH_CONFIDENCE_THRESHOLD
    med_t = settings.MEDIUM_CONFIDENCE_THRESHOLD

    row = db.query(AppSetting).filter(AppSetting.key == "confidence_thresholds").first()
    if row and isinstance(row.value, dict):
        high_t = float(row.value.get("high", high_t))
        med_t = float(row.value.get("medium", med_t))
    return high_t, med_t


def route_ticket_by_confidence(
    db: Session,
    category_id: Optional[int],
    confidence: float,
) -> Dict[str, Any]:
    """
    Determine department routing decision based on configurable routing rules & confidence thresholds:
    - High confidence (>= high_threshold): automatic department routing.
    - Medium confidence (>= medium_threshold): route to suggested department flagged for review.
    - Low confidence (< medium_threshold): leave unassigned for manual triage.
    """
    high_t, med_t = get_routing_thresholds(db)

    rule = None
    if category_id is not None:
        rule = (
            db.query(RoutingRule)
            .filter(RoutingRule.category_id == category_id, RoutingRule.is_active.is_(True))
            .first()
        )

    suggested_department_id = rule.department_id if rule else None
    rule_name = rule.name if rule else "Unmapped category (manual triage)"

    if suggested_department_id is None:
        return {
            "suggested_department_id": None,
            "final_department_id": None,
            "routing_rule_applied": rule_name,
            "routing_decision": "manual_triage",
            "auto_assign_agent": False,
        }

    effective_min = max(med_t, rule.min_confidence if rule else med_t)
    if confidence >= high_t:
        return {
            "suggested_department_id": suggested_department_id,
            "final_department_id": suggested_department_id,
            "routing_rule_applied": f"{rule_name} (High confidence >= {high_t:.2f})",
            "routing_decision": "auto_routed",
            "auto_assign_agent": bool(rule.auto_assign_agent),
        }

    if confidence >= effective_min:
        return {
            "suggested_department_id": suggested_department_id,
            "final_department_id": suggested_department_id,
            "routing_rule_applied": f"{rule_name} (Medium confidence {effective_min:.2f}-{high_t:.2f}; review recommended)",
            "routing_decision": "review_suggested",
            "auto_assign_agent": False,
        }

    return {
        "suggested_department_id": suggested_department_id,
        "final_department_id": None,
        "routing_rule_applied": f"Low confidence (< {effective_min:.2f}); routed to manual triage",
        "routing_decision": "manual_triage",
        "auto_assign_agent": False,
    }


def get_agent_open_workload(db: Session, agent_id: int) -> int:
    return (
        db.query(Ticket)
        .filter(
            Ticket.assigned_agent_id == agent_id,
            Ticket.status.in_(OPEN_TICKET_STATUSES),
        )
        .count()
    )


def recommend_agents(
    db: Session,
    department_id: Optional[int],
    category_name: Optional[str] = None,
    priority: str = "medium",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Deterministic, workload-aware agent assignment recommendation engine.
    Considers department membership, availability, open workload vs max_open_tickets,
    and expertise keywords. Transparently explains every recommendation.
    """
    agents = db.query(Agent).all()
    scored: List[Tuple[float, Dict[str, Any]]] = []

    cat_tokens = set((category_name or "").lower().split())

    for agent in agents:
        if not agent.user or not agent.user.is_active:
            continue

        open_count = get_agent_open_workload(db, agent.id)
        max_cap = max(agent.max_open_tickets or 15, 1)
        capacity_ratio = open_count / max_cap

        member_dept_ids = {link.department_id for link in agent.department_links}
        if agent.department_id:
            member_dept_ids.add(agent.department_id)

        in_department = department_id is not None and department_id in member_dept_ids
        if department_id is not None and not in_department:
            continue

        if agent.availability_status == "offline":
            continue

        # Lower score is better; deterministic scoring
        avail_penalty = {"available": 0.0, "busy": 0.35, "away": 0.70}.get(agent.availability_status, 0.5)
        over_cap_penalty = 2.0 if open_count >= max_cap else 0.0

        expertise_text = (agent.expertise or "").lower()
        expertise_match = any(tok in expertise_text for tok in cat_tokens if len(tok) > 3)
        expertise_bonus = -0.25 if expertise_match else 0.0

        # Prioritize available agents with spare capacity for critical/high tickets
        priority_weight = 1.3 if priority in ("critical", "high") else 1.0
        rank_score = (capacity_ratio * priority_weight) + avail_penalty + over_cap_penalty + expertise_bonus

        reasons = []
        if in_department:
            reasons.append("belongs to the assigned department")
        if agent.availability_status == "available":
            reasons.append("is currently available")
        else:
            reasons.append(f"is currently marked {agent.availability_status}")
        reasons.append(f"has {open_count}/{max_cap} open tickets")
        if expertise_match:
            reasons.append("matches category expertise")

        recommendation_reason = (
            f"Recommended (rule-based workload scoring) because this agent {', '.join(reasons)}."
        )

        scored.append(
            (
                rank_score,
                {
                    "agent_id": agent.id,
                    "user_id": agent.user_id,
                    "name": agent.user.name,
                    "email": agent.user.email,
                    "department_id": agent.department_id,
                    "department_name": agent.primary_department.name if agent.primary_department else None,
                    "availability_status": agent.availability_status,
                    "expertise": agent.expertise,
                    "open_ticket_count": open_count,
                    "max_open_tickets": max_cap,
                    "utilization_pct": round(capacity_ratio * 100, 1),
                    "reason": recommendation_reason,
                    "method": "deterministic_workload_rules",
                },
            )
        )

    scored.sort(key=lambda item: (item[0], item[1]["open_ticket_count"], item[1]["agent_id"]))
    return [item[1] for item in scored[:limit]]
