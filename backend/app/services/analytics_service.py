"""Database-backed Analytics & Operational Intelligence calculations with documented metric formulas."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.models.incidents import Incident
from app.models.intelligence import ModelVersion, TicketFeedback, TicketPrediction
from app.models.operations import SLATracking
from app.models.ticket import Category, Ticket, TicketAssignment
from app.models.user import Agent, Department
from app.services.incident_service import ACTIVE_INCIDENT_STATUSES, serialize_incident_summary
from app.services.routing_service import OPEN_TICKET_STATUSES, get_routing_thresholds
from app.services.sla_risk_service import build_risk_caches, compute_ticket_sla_risk
from app.services.sla_service import compute_sla_metrics, ensure_utc


def _apply_date_filters(query, start_date: Optional[datetime], end_date: Optional[datetime]):
    if start_date:
        query = query.filter(Ticket.created_at >= ensure_utc(start_date))
    if end_date:
        query = query.filter(Ticket.created_at <= ensure_utc(end_date))
    return query


def _safe_avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_overview_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    department_id: Optional[int] = None,
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute operational overview KPIs, time series, distributions, and actionable lists."""
    q = db.query(Ticket)
    q = _apply_date_filters(q, start_date, end_date)
    if department_id is not None:
        q = q.filter(Ticket.department_id == department_id)
    if priority:
        q = q.filter(Ticket.priority == priority)

    tickets = q.order_by(Ticket.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    _, med_threshold = get_routing_thresholds(db)

    total = len(tickets)
    open_tickets = [t for t in tickets if t.status in OPEN_TICKET_STATUSES]
    unassigned = [t for t in open_tickets if t.assigned_agent_id is None]
    critical_high = [t for t in open_tickets if t.priority in ("critical", "high")]

    fr_times: List[float] = []
    res_times: List[float] = []
    completed_eligible = 0
    completed_within_sla = 0
    overdue_tickets = []
    upcoming_deadlines = []

    volume_by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: {"created": 0, "resolved": 0})
    cat_counts: Counter = Counter()
    prio_counts: Counter = Counter()
    dept_counts: Counter = Counter()

    low_conf_items = []

    for t in tickets:
        day_key = ensure_utc(t.created_at).strftime("%Y-%m-%d")
        volume_by_day[day_key]["created"] += 1
        if t.resolved_at:
            res_day = ensure_utc(t.resolved_at).strftime("%Y-%m-%d")
            volume_by_day[res_day]["resolved"] += 1

        cat_counts[t.category.name if t.category else "Uncategorized"] += 1
        prio_counts[t.priority] += 1
        dept_counts[t.department.name if t.department else "Unassigned / Triage"] += 1

        if t.sla_tracking:
            m = compute_sla_metrics(t.sla_tracking, t.created_at, t.status, now)
            if m["first_response_time_minutes"] is not None:
                fr_times.append(m["first_response_time_minutes"])
            if m["resolution_time_minutes"] is not None:
                res_times.append(m["resolution_time_minutes"])
            if m["current_state"] == "completed":
                completed_eligible += 1
                if not m["sla_breached"]:
                    completed_within_sla += 1
            elif m["current_state"] == "overdue":
                overdue_tickets.append((t, m))
            elif m["current_state"] in ("approaching_deadline", "on_track"):
                if m["time_remaining_minutes"] <= 480:
                    upcoming_deadlines.append((t, m))

        latest_pred = t.predictions[0] if t.predictions else None
        if latest_pred and latest_pred.confidence < med_threshold and t.status in OPEN_TICKET_STATUSES:
            low_conf_items.append(
                {
                    "id": t.id,
                    "ticket_reference": t.ticket_reference,
                    "subject": t.subject,
                    "predicted_category": latest_pred.predicted_category.name if latest_pred.predicted_category else None,
                    "confidence": latest_pred.confidence,
                    "routing_decision": latest_pred.routing_decision,
                    "created_at": t.created_at.isoformat(),
                }
            )

    sla_compliance_rate = (
        round((completed_within_sla / completed_eligible) * 100.0, 1)
        if completed_eligible > 0
        else None
    )

    sorted_days = sorted(volume_by_day.keys())[-30:]
    volume_series = [
        {"date": d, "created": volume_by_day[d]["created"], "resolved": volume_by_day[d]["resolved"]}
        for d in sorted_days
    ]

    upcoming_deadlines.sort(key=lambda pair: pair[1]["time_remaining_minutes"])

    attention_tickets = [
        {
            "id": t.id,
            "ticket_reference": t.ticket_reference,
            "subject": t.subject,
            "priority": t.priority,
            "status": t.status,
            "department_name": t.department.name if t.department else "Triage",
            "sla_state": m["current_state"],
            "time_remaining_minutes": m["time_remaining_minutes"],
        }
        for t, m in (overdue_tickets + upcoming_deadlines)[:8]
    ]

    recent_tickets = [
        {
            "id": t.id,
            "ticket_reference": t.ticket_reference,
            "subject": t.subject,
            "priority": t.priority,
            "status": t.status,
            "category_name": t.category.name if t.category else "Uncategorized",
            "department_name": t.department.name if t.department else "Triage",
            "created_at": t.created_at.isoformat(),
            "is_demo_data": t.is_demo_data,
        }
        for t in tickets[:8]
    ]

    # --- Upgraded Operational Summary: Attention Required, Incident Summary & Data-Backed Insights ---
    active_incidents_orm = (
        db.query(Incident)
        .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
        .order_by(Incident.created_at.desc())
        .all()
    )
    active_incidents_ser = [serialize_incident_summary(i) for i in active_incidents_orm]
    unique_inc_customers = set()
    for inc in active_incidents_orm:
        for lnk in inc.ticket_links:
            if lnk.ticket:
                unique_inc_customers.add(lnk.ticket.customer_id)

    most_reported_inc = (
        max(active_incidents_ser, key=lambda x: x["ticket_count"]) if active_incidents_ser else None
    )
    incident_summary = {
        "active_incidents": len(active_incidents_ser),
        "newly_detected": sum(1 for i in active_incidents_ser if i["status"] == "detected"),
        "unique_affected_customers": len(unique_inc_customers),
        "most_reported": most_reported_inc,
        "recent_active": active_incidents_ser[:5],
    }

    dept_c, agent_c, cat_avgs = build_risk_caches(db)
    high_risk_open = []
    unassigned_critical = []
    for t in open_tickets:
        r = compute_ticket_sla_risk(db, t, dept_c, agent_c, cat_avgs, now)
        if r["risk_level"] in ("critical", "high"):
            high_risk_open.append((t, r))
        if t.assigned_agent_id is None and t.priority in ("critical", "high"):
            unassigned_critical.append(t)
    high_risk_open.sort(key=lambda pair: -pair[1]["risk_score"])

    # Repeat unresolved customer complaints (>=2 open tickets from same customer)
    open_by_customer: Counter = Counter(t.customer_id for t in open_tickets)
    repeat_open_customers = [cid for cid, cnt in open_by_customer.items() if cnt >= 2]

    attention_required: List[Dict[str, Any]] = []
    for inc in active_incidents_ser[:3]:
        attention_required.append(
            {
                "kind": "incident",
                "severity": inc["severity"],
                "title": f"{inc['incident_reference']}: {inc['title']}",
                "detail": f"{inc['ticket_count']} linked tickets · {inc['affected_customer_count']} unique affected customers · Status: {inc['status']}",
                "link": "/incidents",
            }
        )
    for t in unassigned_critical[:3]:
        attention_required.append(
            {
                "kind": "unassigned_priority",
                "severity": t.priority,
                "title": f"Unassigned {t.priority} ticket {t.ticket_reference}: {t.subject}",
                "detail": f"Department: {t.department.name if t.department else 'Manual triage'} · Needs immediate agent assignment",
                "link": f"/tickets/{t.id}",
            }
        )
    for t, r in high_risk_open[:3]:
        attention_required.append(
            {
                "kind": "sla_risk",
                "severity": r["risk_level"],
                "title": f"SLA {r['risk_level']} risk — {t.ticket_reference}: {t.subject}",
                "detail": r["factors"][0] if r["factors"] else r["recommended_action"],
                "link": f"/tickets/{t.id}",
            }
        )

    # Operational Insights generated strictly from actual DB records
    operational_insights: List[str] = []
    open_by_dept = Counter(t.department.name for t in open_tickets if t.department)
    if open_by_dept:
        top_d, top_d_cnt = open_by_dept.most_common(1)[0]
        operational_insights.append(
            f"{top_d} currently has the highest open ticket load ({top_d_cnt} open ticket(s))."
        )
    if unassigned_critical:
        operational_insights.append(
            f"{len(unassigned_critical)} critical or high-priority open ticket(s) currently have no assigned agent."
        )
    if active_incidents_ser:
        operational_insights.append(
            f"{len(active_incidents_ser)} active incident cluster(s) affect {len(unique_inc_customers)} unique customer(s)."
        )
    if repeat_open_customers:
        operational_insights.append(
            f"{len(repeat_open_customers)} customer(s) currently have multiple unresolved tickets open simultaneously."
        )
    if high_risk_open:
        operational_insights.append(
            f"{len(high_risk_open)} open ticket(s) are currently flagged at High or Critical SLA breach risk."
        )

    return {
        "metrics": {
            "total_tickets": total,
            "open_tickets": len(open_tickets),
            "unassigned_tickets": len(unassigned),
            "critical_and_high_open": len(critical_high),
            "overdue_tickets": len(overdue_tickets),
            "high_sla_risk_open": len(high_risk_open),
            "avg_first_response_minutes": _safe_avg(fr_times),
            "avg_resolution_minutes": _safe_avg(res_times),
            "sla_compliance_rate": sla_compliance_rate,
            "sla_completed_eligible": completed_eligible,
            "sla_completed_within_target": completed_within_sla,
        },
        "attention_required": attention_required,
        "incident_summary": incident_summary,
        "operational_insights": operational_insights,
        "metric_definitions": {
            "avg_first_response_minutes": "Mean minutes from ticket creation to first public agent response across tickets with a recorded first response.",
            "avg_resolution_minutes": "Mean minutes from ticket creation to final resolution timestamp across resolved/closed tickets.",
            "sla_compliance_rate": "Completed tickets meeting both first-response and resolution SLA deadlines divided by total completed eligible tickets, multiplied by 100.",
        },
        "volume_over_time": volume_series,
        "by_category": [{"name": k, "count": v} for k, v in cat_counts.most_common()],
        "by_priority": [
            {"name": p, "count": prio_counts.get(p, 0)}
            for p in ("critical", "high", "medium", "low")
        ],
        "by_department": [{"name": k, "count": v} for k, v in dept_counts.most_common()],
        "recent_tickets": recent_tickets,
        "attention_tickets": attention_tickets,
        "low_confidence_tickets": low_conf_items[:8],
        "upcoming_sla_deadlines": [
            {
                "id": t.id,
                "ticket_reference": t.ticket_reference,
                "subject": t.subject,
                "priority": t.priority,
                "resolution_deadline": m["resolution_deadline"].isoformat(),
                "time_remaining_minutes": m["time_remaining_minutes"],
                "sla_state": m["current_state"],
            }
            for t, m in upcoming_deadlines[:8]
        ],
        "has_demo_data": any(t.is_demo_data for t in tickets),
    }


def compute_department_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    departments = db.query(Department).order_by(Department.name.asc()).all()
    now = datetime.now(timezone.utc)
    results = []

    for dept in departments:
        q = db.query(Ticket).filter(Ticket.department_id == dept.id)
        q = _apply_date_filters(q, start_date, end_date)
        tickets = q.all()

        open_count = sum(1 for t in tickets if t.status in OPEN_TICKET_STATUSES)
        unassigned_count = sum(1 for t in tickets if t.status in OPEN_TICKET_STATUSES and t.assigned_agent_id is None)
        res_times = []
        completed_sla = 0
        within_sla = 0
        escalated = 0
        reopened = 0
        reassigned = 0

        for t in tickets:
            if t.reopen_count > 0:
                reopened += 1
            if len(t.assignments) > 1:
                reassigned += 1
            if t.sla_tracking:
                m = compute_sla_metrics(t.sla_tracking, t.created_at, t.status, now)
                if m["resolution_time_minutes"] is not None:
                    res_times.append(m["resolution_time_minutes"])
                if m["current_state"] == "completed":
                    completed_sla += 1
                    if not m["sla_breached"]:
                        within_sla += 1
                if m["escalated"]:
                    escalated += 1

        total = len(tickets)
        results.append(
            {
                "department_id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "is_active": dept.is_active,
                "agent_count": len(dept.agents),
                "total_tickets": total,
                "open_tickets": open_count,
                "unassigned_tickets": unassigned_count,
                "avg_resolution_minutes": _safe_avg(res_times),
                "sla_compliance_rate": round((within_sla / completed_sla) * 100.0, 1) if completed_sla else None,
                "escalation_rate": round((escalated / total) * 100.0, 1) if total else 0.0,
                "reassignment_rate": round((reassigned / total) * 100.0, 1) if total else 0.0,
                "reopen_rate": round((reopened / total) * 100.0, 1) if total else 0.0,
            }
        )
    return results


def compute_agent_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    agents = db.query(Agent).all()
    now = datetime.now(timezone.utc)
    rows = []

    for agent in agents:
        if not agent.user:
            continue
        q = db.query(Ticket).filter(Ticket.assigned_agent_id == agent.id)
        q = _apply_date_filters(q, start_date, end_date)
        tickets = q.all()

        open_tickets = [t for t in tickets if t.status in OPEN_TICKET_STATUSES]
        resolved_tickets = [t for t in tickets if t.status in ("resolved", "closed")]
        high_prio_handled = sum(1 for t in tickets if t.priority in ("critical", "high"))
        res_times = []
        fr_times = []
        ratings = []
        completed_sla = 0
        within_sla = 0

        for t in tickets:
            if t.satisfaction_rating is not None:
                ratings.append(float(t.satisfaction_rating))
            if t.sla_tracking:
                m = compute_sla_metrics(t.sla_tracking, t.created_at, t.status, now)
                if m["first_response_time_minutes"] is not None:
                    fr_times.append(m["first_response_time_minutes"])
                if m["resolution_time_minutes"] is not None:
                    res_times.append(m["resolution_time_minutes"])
                if m["current_state"] == "completed":
                    completed_sla += 1
                    if not m["sla_breached"]:
                        within_sla += 1

        max_cap = max(agent.max_open_tickets or 15, 1)
        rows.append(
            {
                "agent_id": agent.id,
                "user_id": agent.user_id,
                "name": agent.user.name,
                "email": agent.user.email,
                "is_active": agent.user.is_active,
                "department_id": agent.department_id,
                "department_name": agent.primary_department.name if agent.primary_department else None,
                "availability_status": agent.availability_status,
                "expertise": agent.expertise,
                "max_open_tickets": max_cap,
                "open_tickets": len(open_tickets),
                "utilization_pct": round((len(open_tickets) / max_cap) * 100.0, 1),
                "total_assigned": len(tickets),
                "resolved_tickets": len(resolved_tickets),
                "high_priority_tickets": high_prio_handled,
                "avg_first_response_minutes": _safe_avg(fr_times),
                "avg_resolution_minutes": _safe_avg(res_times),
                "sla_compliance_rate": round((within_sla / completed_sla) * 100.0, 1) if completed_sla else None,
                "avg_satisfaction": round(sum(ratings) / len(ratings), 2) if ratings else None,
            }
        )
    return rows


def compute_customer_experience_and_trends(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    q = _apply_date_filters(db.query(Ticket), start_date, end_date)
    tickets = q.all()

    ratings = [t.satisfaction_rating for t in tickets if t.satisfaction_rating is not None]
    resolved_pop = [t for t in tickets if t.resolved_at is not None or t.status in ("resolved", "closed") or t.reopen_count > 0]
    reopened = [t for t in tickets if t.reopen_count > 0]

    sentiment_counts = Counter(t.sentiment_label or "unknown" for t in tickets)
    reopen_by_cat = Counter(t.category.name if t.category else "Uncategorized" for t in reopened)
    reopen_reasons = Counter((t.reopen_reason or "No reason specified") for t in reopened)

    # Demand spike detection using configurable z-score (> 1.5 std dev over recent baseline)
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=7)
    prior_cutoff = now - timedelta(days=28)

    recent_counts: Counter = Counter()
    weekly_baseline: Dict[str, List[int]] = defaultdict(lambda: [0, 0, 0])
    for t in tickets:
        cat_name = t.category.name if t.category else "Uncategorized"
        created = ensure_utc(t.created_at)
        if created >= recent_cutoff:
            recent_counts[cat_name] += 1
        elif created >= prior_cutoff:
            days_ago = (recent_cutoff - created).days
            week_bin = min(max(days_ago // 7, 0), 2)
            weekly_baseline[cat_name][week_bin] += 1

    demand_alerts = []
    for cat_name, cur_vol in recent_counts.items():
        hist = weekly_baseline.get(cat_name, [0, 0, 0])
        mean_val = float(np.mean(hist))
        std_val = float(np.std(hist))
        z_score = (cur_vol - mean_val) / max(std_val, 1.0)
        if cur_vol >= 3 and z_score >= 1.5:
            demand_alerts.append(
                {
                    "category": cat_name,
                    "last_7_days_volume": cur_vol,
                    "prior_weekly_avg": round(mean_val, 1),
                    "z_score": round(z_score, 2),
                    "evidence": f"{cur_vol} tickets in the last 7 days vs {mean_val:.1f}/week prior 3-week average (z={z_score:.2f}).",
                }
            )
    demand_alerts.sort(key=lambda x: x["z_score"], reverse=True)

    return {
        "avg_satisfaction_score": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "total_rated_tickets": len(ratings),
        "rating_distribution": [
            {"stars": s, "count": ratings.count(s)} for s in (5, 4, 3, 2, 1)
        ],
        "reopened_count": len(reopened),
        "resolved_population": len(resolved_pop),
        "reopen_rate": round((len(reopened) / len(resolved_pop)) * 100.0, 1) if resolved_pop else 0.0,
        "reopen_by_category": [{"category": k, "count": v} for k, v in reopen_by_cat.most_common()],
        "top_reopen_reasons": [{"reason": k, "count": v} for k, v in reopen_reasons.most_common(5)],
        "sentiment_distribution": [
            {"sentiment": s, "count": sentiment_counts.get(s, 0)}
            for s in ("positive", "neutral", "negative")
        ],
        "demand_alerts": demand_alerts,
        "reopen_formula": "Reopened tickets divided by total tickets ever resolved or reopened, multiplied by 100.",
    }


def compute_classification_and_feedback_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    pred_q = db.query(TicketPrediction).join(Ticket, TicketPrediction.ticket_id == Ticket.id)
    if start_date:
        pred_q = pred_q.filter(Ticket.created_at >= ensure_utc(start_date))
    if end_date:
        pred_q = pred_q.filter(Ticket.created_at <= ensure_utc(end_date))
    predictions = pred_q.all()

    fb_q = db.query(TicketFeedback).join(Ticket, TicketFeedback.ticket_id == Ticket.id)
    if start_date:
        fb_q = fb_q.filter(Ticket.created_at >= ensure_utc(start_date))
    if end_date:
        fb_q = fb_q.filter(Ticket.created_at <= ensure_utc(end_date))
    feedbacks = fb_q.all()

    high_t, med_t = get_routing_thresholds(db)

    conf_buckets = {"high": 0, "medium": 0, "low": 0}
    routing_decisions = Counter()
    dept_matches = 0
    dept_evaluated = 0

    for p in predictions:
        if p.confidence >= high_t:
            conf_buckets["high"] += 1
        elif p.confidence >= med_t:
            conf_buckets["medium"] += 1
        else:
            conf_buckets["low"] += 1
        routing_decisions[p.routing_decision or "unknown"] += 1
        if p.suggested_department_id and p.ticket and p.ticket.department_id:
            dept_evaluated += 1
            if p.suggested_department_id == p.ticket.department_id:
                dept_matches += 1

    corrected_ticket_ids = {fb.ticket_id for fb in feedbacks}
    total_preds = len(predictions)
    correction_rate = round((len(corrected_ticket_ids) / total_preds) * 100.0, 1) if total_preds else 0.0

    corrected_cats = Counter()
    dept_mismatches = Counter()
    for fb in feedbacks:
        orig_cat = fb.prediction.predicted_category.name if (fb.prediction and fb.prediction.predicted_category) else "Unknown"
        new_cat = fb.corrected_category.name if fb.corrected_category else orig_cat
        if orig_cat != new_cat:
            corrected_cats[f"{orig_cat} -> {new_cat}"] += 1
        orig_dept = fb.prediction.suggested_department.name if (fb.prediction and fb.prediction.suggested_department) else "Unassigned"
        new_dept = fb.corrected_department.name if fb.corrected_department else orig_dept
        if orig_dept != new_dept:
            dept_mismatches[f"{orig_dept} -> {new_dept}"] += 1

    active_model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()

    return {
        "total_predictions": total_preds,
        "corrected_predictions": len(feedbacks),
        "unique_tickets_corrected": len(corrected_ticket_ids),
        "correction_rate": correction_rate,
        "correction_rate_formula": "Unique tickets whose prediction was corrected divided by total predictions in scope, multiplied by 100.",
        "department_agreement_rate": round((dept_matches / dept_evaluated) * 100.0, 1) if dept_evaluated else None,
        "confidence_thresholds": {"high": high_t, "medium": med_t},
        "confidence_distribution": [
            {"band": f"High (>= {int(high_t*100)}%)", "count": conf_buckets["high"]},
            {"band": f"Medium ({int(med_t*100)}-{int(high_t*100)-1}%)", "count": conf_buckets["medium"]},
            {"band": f"Low (< {int(med_t*100)}%)", "count": conf_buckets["low"]},
        ],
        "routing_decisions": [{"decision": k, "count": v} for k, v in routing_decisions.most_common()],
        "most_corrected_categories": [{"transition": k, "count": v} for k, v in corrected_cats.most_common(8)],
        "department_mismatches": [{"transition": k, "count": v} for k, v in dept_mismatches.most_common(8)],
        "active_model": {
            "id": active_model.id,
            "version": active_model.version,
            "algorithm": active_model.algorithm,
            "training_date": active_model.training_date.isoformat(),
            "evaluation_metrics": active_model.evaluation_metrics,
        }
        if active_model
        else None,
    }
