"""
Risk & Workload Optimization Service (Phase 2).
Surfaces SLA breach risks, agent capacity bands (available, nearing capacity, overloaded),
unassigned high-priority queues with explainable agent recommendations, and growing department backlogs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.user import Agent, Department
from app.services.routing_service import OPEN_TICKET_STATUSES, recommend_agents
from app.services.sla_risk_service import build_risk_caches, compute_ticket_sla_risk
from app.services.sla_service import ensure_utc


def compute_risk_and_workload_overview(db: Session) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    dept_counts, agent_counts, cat_avgs = build_risk_caches(db)

    open_tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_(OPEN_TICKET_STATUSES))
        .order_by(Ticket.created_at.desc())
        .all()
    )

    risk_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    at_risk_tickets: List[Dict[str, Any]] = []
    unassigned_high_priority: List[Dict[str, Any]] = []

    for t in open_tickets:
        risk = compute_ticket_sla_risk(db, t, dept_counts, agent_counts, cat_avgs, now)
        lvl = risk["risk_level"]
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1

        if lvl in ("critical", "high"):
            at_risk_tickets.append(
                {
                    "id": t.id,
                    "ticket_reference": t.ticket_reference,
                    "subject": t.subject,
                    "priority": t.priority,
                    "status": t.status,
                    "department_id": t.department_id,
                    "department_name": t.department.name if t.department else "Manual triage",
                    "assigned_agent_name": t.assigned_agent.user.name if (t.assigned_agent and t.assigned_agent.user) else None,
                    **risk,
                }
            )

        if t.assigned_agent_id is None and t.priority in ("critical", "high"):
            recs = recommend_agents(
                db,
                department_id=t.department_id,
                category_name=t.category.name if t.category else None,
                priority=t.priority,
                limit=2,
            )
            unassigned_high_priority.append(
                {
                    "id": t.id,
                    "ticket_reference": t.ticket_reference,
                    "subject": t.subject,
                    "priority": t.priority,
                    "department_id": t.department_id,
                    "department_name": t.department.name if t.department else "Manual triage",
                    "category_name": t.category.name if t.category else "Uncategorized",
                    "risk_level": risk["risk_level"],
                    "remaining_sla_minutes": risk["remaining_sla_minutes"],
                    "recommended_agents": recs,
                }
            )

    at_risk_tickets.sort(key=lambda r: (-r["risk_score"], r["remaining_sla_minutes"] or 999999))

    # Agent capacity categorization
    agents = db.query(Agent).all()
    available_agents = []
    nearing_capacity = []
    overloaded_agents = []

    for ag in agents:
        if not ag.user or not ag.user.is_active:
            continue
        open_cnt = agent_counts.get(ag.id, 0)
        max_cap = max(ag.max_open_tickets or 15, 1)
        util_pct = round((open_cnt / max_cap) * 100.0, 1)

        # Compute agent's historical average resolution for fair context
        resolved_by_ag = (
            db.query(Ticket)
            .filter(Ticket.assigned_agent_id == ag.id, Ticket.resolved_at.isnot(None))
            .all()
        )
        res_mins = [
            (ensure_utc(t.resolved_at) - ensure_utc(t.created_at)).total_seconds() / 60.0
            for t in resolved_by_ag
            if ensure_utc(t.resolved_at) >= ensure_utc(t.created_at)
        ]
        avg_res = round(sum(res_mins) / len(res_mins), 1) if res_mins else None

        card = {
            "agent_id": ag.id,
            "name": ag.user.name,
            "email": ag.user.email,
            "department_id": ag.department_id,
            "department_name": ag.primary_department.name if ag.primary_department else "Unassigned",
            "availability_status": ag.availability_status,
            "expertise": ag.expertise,
            "open_tickets": open_cnt,
            "max_open_tickets": max_cap,
            "utilization_pct": util_pct,
            "resolved_sample_size": len(res_mins),
            "avg_resolution_minutes": avg_res,
        }

        if open_cnt >= max_cap:
            overloaded_agents.append(card)
        elif util_pct >= 75.0:
            nearing_capacity.append(card)
        else:
            available_agents.append(card)

    # Department backlog momentum (last 7d created vs last 7d resolved)
    recent_cutoff = now - timedelta(days=7)
    departments = db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name.asc()).all()
    dept_backlogs = []
    for d in departments:
        d_tickets = db.query(Ticket).filter(Ticket.department_id == d.id).all()
        open_cnt = sum(1 for t in d_tickets if t.status in OPEN_TICKET_STATUSES)
        unassigned_cnt = sum(1 for t in d_tickets if t.status in OPEN_TICKET_STATUSES and t.assigned_agent_id is None)
        created_7d = sum(1 for t in d_tickets if ensure_utc(t.created_at) >= recent_cutoff)
        resolved_7d = sum(1 for t in d_tickets if t.resolved_at and ensure_utc(t.resolved_at) >= recent_cutoff)
        net_delta = created_7d - resolved_7d
        dept_backlogs.append(
            {
                "department_id": d.id,
                "name": d.name,
                "open_tickets": open_cnt,
                "unassigned_tickets": unassigned_cnt,
                "created_last_7d": created_7d,
                "resolved_last_7d": resolved_7d,
                "net_backlog_delta_7d": net_delta,
                "is_growing": net_delta >= 3,
            }
        )
    dept_backlogs.sort(key=lambda r: (-r["open_tickets"], -r["net_backlog_delta_7d"]))

    # Manager recommended actions derived strictly from real records
    manager_actions: List[Dict[str, Any]] = []
    if unassigned_high_priority:
        manager_actions.append(
            {
                "severity": "critical",
                "title": f"{len(unassigned_high_priority)} critical/high-priority ticket(s) are unassigned",
                "detail": "Review the unassigned high-priority queue below and approve recommended department agents.",
                "target_path": "/tickets?preset=unassigned",
            }
        )
    if overloaded_agents:
        names = ", ".join(a["name"] for a in overloaded_agents[:3])
        manager_actions.append(
            {
                "severity": "high",
                "title": f"{len(overloaded_agents)} agent(s) at or above open ticket capacity ({names})",
                "detail": "Rebalance open tickets to available peers in the same department before SLA deadlines approach.",
                "target_path": "/agents",
            }
        )
    growing_depts = [d for d in dept_backlogs if d["is_growing"]]
    if growing_depts:
        top_g = growing_depts[0]
        manager_actions.append(
            {
                "severity": "moderate",
                "title": f"{top_g['name']} backlog grew by +{top_g['net_backlog_delta_7d']} tickets in the last 7 days",
                "detail": f"{top_g['created_last_7d']} created vs {top_g['resolved_last_7d']} resolved ({top_g['unassigned_tickets']} unassigned).",
                "target_path": f"/tickets?department_id={top_g['department_id']}",
            }
        )

    return {
        "risk_method": "deterministic_risk_rules",
        "risk_summary": risk_counts,
        "at_risk_tickets": at_risk_tickets[:25],
        "unassigned_high_priority": unassigned_high_priority[:15],
        "agent_capacity": {
            "available": available_agents,
            "nearing_capacity": nearing_capacity,
            "overloaded": overloaded_agents,
        },
        "department_backlogs": dept_backlogs,
        "manager_actions": manager_actions,
    }
