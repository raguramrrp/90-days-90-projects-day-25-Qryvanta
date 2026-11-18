"""
Incident Detection, Grouping & Management Service (Phase 1).
Uses local TF-IDF cosine similarity + time-window connected-component clustering
to surface candidate multi-customer incidents for human review (never auto-confirmed).
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import random
import string
from typing import Any, Dict, List, Optional, Set
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.incidents import Incident, IncidentEvent, IncidentTicket
from app.models.ticket import Ticket
from app.models.user import Department, User
from app.services.routing_service import OPEN_TICKET_STATUSES
from app.services.sla_service import ensure_utc
from ml.preprocessing.text_cleaner import combine_ticket_text


ACTIVE_INCIDENT_STATUSES = ("detected", "investigating", "confirmed", "monitoring")


def generate_incident_reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    for _ in range(25):
        suffix = "".join(random.choices(string.digits, k=4))
        ref = f"INC-{year}-{suffix}"
        if not db.query(Incident.id).filter(Incident.incident_reference == ref).first():
            return ref
    return f"INC-{year}-{int(datetime.now(timezone.utc).timestamp()) % 10000:04d}"


def record_incident_event(
    db: Session,
    incident_id: int,
    event_type: str,
    description: str,
    actor_id: Optional[int] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> IncidentEvent:
    ev = IncidentEvent(
        incident_id=incident_id,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        description=description,
    )
    db.add(ev)
    return ev


def _extract_common_symptoms(texts: List[str], top_n: int = 6) -> List[str]:
    """Extract top descriptive TF-IDF n-grams across a cluster of related tickets."""
    if not texts:
        return []
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=300, min_df=1)
        mat = vec.fit_transform(texts)
        scores = np.asarray(mat.mean(axis=0)).flatten()
        features = vec.get_feature_names_out()
        ranked = scores.argsort()[::-1]
        symptoms: List[str] = []
        for idx in ranked:
            term = str(features[idx]).strip()
            if len(term) < 3 or term.isdigit():
                continue
            if any(term in existing for existing in symptoms):
                continue
            symptoms.append(term)
            if len(symptoms) >= top_n:
                break
        return symptoms
    except ValueError:
        return []


def _suggest_incident_title(tickets: List[Ticket], symptoms: List[str]) -> str:
    cat_counts = Counter(t.category.name for t in tickets if t.category)
    top_cat = cat_counts.most_common(1)[0][0] if cat_counts else "Support"
    top_sym = ", ".join(symptoms[:3]) if symptoms else "related customer reports"
    return f"Emerging {top_cat} cluster: {top_sym}"[:240]


def _estimate_cluster_severity(tickets: List[Ticket], unique_customers: int) -> str:
    crit_cnt = sum(1 for t in tickets if t.priority == "critical")
    high_cnt = sum(1 for t in tickets if t.priority == "high")
    if crit_cnt >= 2 or unique_customers >= 10 or len(tickets) >= 15:
        return "critical"
    if crit_cnt >= 1 or high_cnt >= 2 or unique_customers >= 4 or len(tickets) >= 5:
        return "high"
    if unique_customers >= 2 or len(tickets) >= 3:
        return "medium"
    return "low"


def detect_candidate_incidents(
    db: Session,
    window_days: int = 14,
    similarity_threshold: float = 0.28,
    min_cluster_size: int = 3,
    actor: Optional[User] = None,
) -> Dict[str, Any]:
    """
    Scan open tickets within a rolling time window using TF-IDF cosine similarity.
    Group strongly similar unlinked tickets into candidate incidents (status='detected')
    requiring human review before confirmation.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    open_tickets = (
        db.query(Ticket)
        .filter(
            Ticket.status.in_(OPEN_TICKET_STATUSES),
            Ticket.created_at >= cutoff,
        )
        .order_by(Ticket.created_at.desc())
        .limit(400)
        .all()
    )

    if len(open_tickets) < min_cluster_size:
        return {"detected_count": 0, "updated_count": 0, "incidents": [], "scanned_tickets": len(open_tickets)}

    # Check tickets already linked to active incidents
    active_links = (
        db.query(IncidentTicket)
        .join(Incident, IncidentTicket.incident_id == Incident.id)
        .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
        .all()
    )
    already_linked_ticket_ids: Set[int] = {lnk.ticket_id for lnk in active_links}

    unlinked = [t for t in open_tickets if t.id not in already_linked_ticket_ids]
    if len(unlinked) < min_cluster_size:
        return {"detected_count": 0, "updated_count": 0, "incidents": [], "scanned_tickets": len(open_tickets)}

    texts = [combine_ticket_text(t.subject, t.description, t.product_reference) for t in unlinked]
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        mat = vec.fit_transform(texts)
        sim_matrix = cosine_similarity(mat)
    except ValueError:
        return {"detected_count": 0, "updated_count": 0, "incidents": [], "scanned_tickets": len(open_tickets)}

    # Build adjacency graph for pairs above similarity threshold within same 7-day sub-window
    n = len(unlinked)
    adj: Dict[int, Set[int]] = defaultdict(set)
    for i in range(n):
        for j in range(i + 1, n):
            if float(sim_matrix[i, j]) >= similarity_threshold:
                dt_diff = abs((ensure_utc(unlinked[i].created_at) - ensure_utc(unlinked[j].created_at)).total_seconds())
                if dt_diff <= 7 * 86400:
                    adj[i].add(j)
                    adj[j].add(i)

    # Extract connected components
    visited: Set[int] = set()
    clusters: List[List[int]] = []
    for i in range(n):
        if i in visited:
            continue
        comp: List[int] = []
        stack = [i]
        visited.add(i)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj.get(cur, ()):
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if len(comp) >= min_cluster_size:
            clusters.append(comp)

    created_incidents: List[Incident] = []
    for comp in clusters:
        cluster_tickets = [unlinked[idx] for idx in comp]
        cluster_texts = [texts[idx] for idx in comp]
        unique_customers = len({t.customer_id for t in cluster_tickets})
        symptoms = _extract_common_symptoms(cluster_texts, top_n=6)
        title = _suggest_incident_title(cluster_tickets, symptoms)
        severity = _estimate_cluster_severity(cluster_tickets, unique_customers)

        dept_counts = Counter(t.department_id for t in cluster_tickets if t.department_id)
        dept_id = dept_counts.most_common(1)[0][0] if dept_counts else None

        timestamps = [ensure_utc(t.created_at) for t in cluster_tickets]
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        is_demo = all(t.is_demo_data for t in cluster_tickets)

        # Compute average pairwise similarity per ticket within the cluster
        inc = Incident(
            incident_reference=generate_incident_reference(db),
            title=title,
            description=(
                f"Automatically suggested incident cluster grouping {len(cluster_tickets)} semantically similar open tickets "
                f"from {unique_customers} unique customer(s) (TF-IDF cosine similarity >= {similarity_threshold:.2f}). "
                "Requires manager review before confirmation."
            ),
            severity=severity,
            status="detected",
            department_id=dept_id,
            common_symptoms=symptoms,
            is_auto_detected=True,
            is_demo_data=is_demo,
            first_reported_at=first_ts,
            last_reported_at=last_ts,
        )
        db.add(inc)
        db.flush()

        for pos_idx in comp:
            t = unlinked[pos_idx]
            peer_sims = [float(sim_matrix[pos_idx, other]) for other in comp if other != pos_idx]
            avg_sim = round(float(np.mean(peer_sims)), 4) if peer_sims else 1.0
            db.add(
                IncidentTicket(
                    incident_id=inc.id,
                    ticket_id=t.id,
                    similarity_score=avg_sim,
                    linked_by=actor.id if actor else None,
                )
            )

        record_incident_event(
            db,
            inc.id,
            "incident_detected",
            f"System detected candidate incident with {len(cluster_tickets)} tickets ({unique_customers} unique customers). Awaiting human review.",
            actor_id=actor.id if actor else None,
            new_value="detected",
        )
        created_incidents.append(inc)

    db.commit()
    for inc in created_incidents:
        db.refresh(inc)

    return {
        "detected_count": len(created_incidents),
        "scanned_tickets": len(open_tickets),
        "incidents": [serialize_incident_summary(inc) for inc in created_incidents],
    }


def recompute_incident_timestamps(inc: Incident) -> None:
    linked_tickets = [lnk.ticket for lnk in inc.ticket_links if lnk.ticket is not None]
    if not linked_tickets:
        return
    times = [ensure_utc(t.created_at) for t in linked_tickets]
    inc.first_reported_at = min(times)
    inc.last_reported_at = max(times)


def serialize_incident_summary(inc: Incident) -> Dict[str, Any]:
    linked_tickets = [lnk.ticket for lnk in inc.ticket_links if lnk.ticket is not None]
    unique_customer_ids = {t.customer_id for t in linked_tickets}
    open_linked = sum(1 for t in linked_tickets if t.status in OPEN_TICKET_STATUSES)

    return {
        "id": inc.id,
        "incident_reference": inc.incident_reference,
        "title": inc.title,
        "description": inc.description,
        "severity": inc.severity,
        "status": inc.status,
        "department_id": inc.department_id,
        "department_name": inc.department.name if inc.department else "Unassigned",
        "owner_id": inc.owner_id,
        "owner_name": inc.owner.name if inc.owner else None,
        "common_symptoms": inc.common_symptoms or [],
        "ticket_count": len(linked_tickets),
        "open_ticket_count": open_linked,
        "affected_customer_count": len(unique_customer_ids),
        "is_auto_detected": inc.is_auto_detected,
        "is_demo_data": inc.is_demo_data,
        "first_reported_at": inc.first_reported_at.isoformat() if inc.first_reported_at else None,
        "last_reported_at": inc.last_reported_at.isoformat() if inc.last_reported_at else None,
        "created_at": inc.created_at.isoformat() if inc.created_at else None,
        "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
    }


def serialize_incident_detail(inc: Incident) -> Dict[str, Any]:
    base = serialize_incident_summary(inc)
    linked_rows = []
    customer_ticket_counts: Counter = Counter()

    for lnk in inc.ticket_links:
        t = lnk.ticket
        if not t:
            continue
        customer_ticket_counts[t.customer_id] += 1
        linked_rows.append(
            {
                "link_id": lnk.id,
                "ticket_id": t.id,
                "ticket_reference": t.ticket_reference,
                "subject": t.subject,
                "status": t.status,
                "priority": t.priority,
                "customer_id": t.customer_id,
                "customer_name": t.customer.user.name if (t.customer and t.customer.user) else "Unknown",
                "company_name": t.company.name if t.company else None,
                "category_name": t.category.name if t.category else None,
                "similarity_score": lnk.similarity_score,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "linked_at": lnk.linked_at.isoformat() if lnk.linked_at else None,
            }
        )

    linked_rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    repeat_reporters = sum(1 for cnt in customer_ticket_counts.values() if cnt > 1)

    base["investigation_notes"] = inc.investigation_notes
    base["resolution_summary"] = inc.resolution_summary
    base["tickets"] = linked_rows
    base["customer_impact"] = {
        "total_linked_tickets": len(linked_rows),
        "unique_affected_customers": len(customer_ticket_counts),
        "repeat_complaint_customers": repeat_reporters,
        "clarification": (
            f"{len(linked_rows)} linked ticket(s) across {len(customer_ticket_counts)} unique customer(s)."
        ),
    }
    base["events"] = [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "actor_name": ev.actor.name if ev.actor else "System",
            "old_value": ev.old_value,
            "new_value": ev.new_value,
            "description": ev.description,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in inc.events
    ]
    return base
