"""
Resolution Intelligence, Knowledge Gap Detection & Resolution Effectiveness Service (Phase 3).
- Retrieves ONLY genuine previously resolved tickets within authorized scope (strict privacy).
- Tracks agent feedback (helpful / partially_helpful / not_helpful) on resolution suggestions.
- Detects real Knowledge Gaps from unresolved/repeated topics without KB coverage; creates unpublished drafts only.
- Computes Resolution Effectiveness Analytics (FCR, reopen rate, repeat issue rate, recurrence after closure).
"""

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.incidents import KnowledgeGap, ResolutionFeedback
from app.models.intelligence import KnowledgeArticle
from app.models.ticket import Category, Ticket
from app.models.user import Department, User
from app.services.auth_service import get_agent_authorized_department_ids
from app.services.routing_service import OPEN_TICKET_STATUSES
from app.services.sla_service import ensure_utc
from ml.preprocessing.text_cleaner import combine_ticket_text


def _extract_actual_resolution(ticket: Ticket) -> Optional[str]:
    """Return the genuine last public staff reply from a resolved/closed ticket (never invented)."""
    staff_public = [
        m
        for m in ticket.messages
        if m.visibility == "public" and m.sender and m.sender.role in ("agent", "manager", "admin")
    ]
    if not staff_public:
        return None
    return staff_public[-1].message.strip()


def find_similar_resolved_tickets(
    db: Session,
    ticket: Ticket,
    viewer: User,
    threshold: float = 0.15,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retrieve genuinely resolved/closed historical tickets similar to `ticket`,
    strictly respecting viewer authorization and never fabricating resolutions.
    """
    q = db.query(Ticket).filter(
        Ticket.id != ticket.id,
        Ticket.status.in_(("resolved", "closed")),
    )

    if viewer.role == "customer":
        if not viewer.customer_profile:
            return []
        q = q.filter(Ticket.customer_id == viewer.customer_profile.id)
    elif viewer.role == "agent":
        dept_ids = list(get_agent_authorized_department_ids(viewer))
        if dept_ids:
            q = q.filter((Ticket.department_id.in_(dept_ids)) | (Ticket.department_id.is_(None)))

    candidates = q.order_by(Ticket.resolved_at.desc()).limit(250).all()
    if not candidates:
        return []

    query_text = combine_ticket_text(ticket.subject, ticket.description, ticket.product_reference)
    cand_texts = [combine_ticket_text(c.subject, c.description, c.product_reference) for c in candidates]
    if not query_text:
        return []

    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        mat = vec.fit_transform([query_text] + cand_texts)
        sims = cosine_similarity(mat[0:1], mat[1:]).flatten()
    except ValueError:
        return []

    ranked = sims.argsort()[::-1]
    results: List[Dict[str, Any]] = []

    for idx in ranked:
        score = float(sims[idx])
        if score < threshold:
            break
        cand = candidates[int(idx)]
        resolution_text = _extract_actual_resolution(cand)
        if not resolution_text:
            continue

        # Count historical helpful ratings for this resolution source
        fb_rows = db.query(ResolutionFeedback).filter(ResolutionFeedback.source_ticket_id == cand.id).all()
        helpful_cnt = sum(1 for f in fb_rows if f.rating == "helpful")

        results.append(
            {
                "source_ticket_id": cand.id,
                "ticket_reference": cand.ticket_reference,
                "subject": cand.subject,
                "problem_description": cand.description,
                "actual_resolution": resolution_text,
                "category_name": cand.category.name if cand.category else None,
                "department_name": cand.department.name if cand.department else None,
                "similarity_score": round(score, 4),
                "reopened_previously": (cand.reopen_count or 0) > 0,
                "satisfaction_rating": cand.satisfaction_rating,
                "helpful_votes": helpful_cnt,
                "resolved_at": cand.resolved_at.isoformat() if cand.resolved_at else None,
            }
        )
        if len(results) >= top_k:
            break

    return results


def detect_knowledge_gaps(db: Session) -> List[Dict[str, Any]]:
    """
    Identify customer issue topics lacking effective Knowledge Base documentation:
    - Categories/subcategories with repeated open or unresolved tickets & zero/low KB coverage.
    - Topics where existing KB articles received negative feedback.
    Syncs detected gaps into `knowledge_gaps` without auto-publishing any articles.
    """
    tickets = db.query(Ticket).all()
    articles = db.query(KnowledgeArticle).filter(KnowledgeArticle.is_published.is_(True)).all()
    categories = db.query(Category).filter(Category.parent_category_id.is_(None)).all()

    articles_by_cat: Dict[int, List[KnowledgeArticle]] = defaultdict(list)
    for art in articles:
        if art.category_id:
            articles_by_cat[art.category_id].append(art)

    # Check negative feedback on articles
    neg_article_ids = {
        fb.article_id
        for fb in db.query(ResolutionFeedback)
        .filter(
            ResolutionFeedback.recommendation_type == "knowledge_article",
            ResolutionFeedback.rating == "not_helpful",
            ResolutionFeedback.article_id.isnot(None),
        )
        .all()
    }

    tickets_by_cat: Dict[int, List[Ticket]] = defaultdict(list)
    for t in tickets:
        if t.category_id:
            tickets_by_cat[t.category_id].append(t)

    detected_topics: List[Dict[str, Any]] = []

    for cat in categories:
        cat_tkts = tickets_by_cat.get(cat.id, [])
        if len(cat_tkts) < 2:
            continue

        cat_articles = articles_by_cat.get(cat.id, [])
        open_cnt = sum(1 for t in cat_tkts if t.status in OPEN_TICKET_STATUSES)
        reopen_cnt = sum(1 for t in cat_tkts if (t.reopen_count or 0) > 0)
        has_poor_art = any(a.id in neg_article_ids for a in cat_articles)

        # Group by subcategory to find fine-grained undocumented sub-topics
        by_sub: Dict[str, List[Ticket]] = defaultdict(list)
        for t in cat_tkts:
            sub_name = t.subcategory.name if t.subcategory else cat.name
            by_sub[sub_name].append(t)

        for topic_name, sub_tkts in by_sub.items():
            if len(sub_tkts) < 2:
                continue

            # Check if any published KB article explicitly covers this subcategory/topic
            topic_tokens = {tok for tok in topic_name.lower().split() if len(tok) > 3}
            covered = any(
                any(tok in f"{a.title} {a.tags or ''}".lower() for tok in topic_tokens)
                for a in cat_articles
            )

            sub_open = sum(1 for t in sub_tkts if t.status in OPEN_TICKET_STATUSES)
            needs_gap = (not covered and len(sub_tkts) >= 2) or (sub_open >= 5) or has_poor_art
            if not needs_gap:
                continue

            texts = [combine_ticket_text(t.subject, t.description) for t in sub_tkts]
            symptoms: List[str] = []
            try:
                vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=80, min_df=1)
                mat = vec.fit_transform(texts)
                scores = np.asarray(mat.mean(axis=0)).flatten()
                feats = vec.get_feature_names_out()
                symptoms = [str(feats[i]) for i in scores.argsort()[::-1][:4] if len(str(feats[i])) > 2]
            except ValueError:
                pass

            priority = "high" if (not covered and len(sub_tkts) >= 5) or sub_open >= 6 else ("medium" if not covered else "low")
            suggested_title = f"Troubleshooting & Resolution Guide: {cat.name} — {topic_name}"

            # Upsert persistent KnowledgeGap row (preserve draft_created / dismissed status if already acted on)
            gap = (
                db.query(KnowledgeGap)
                .filter(KnowledgeGap.topic == f"{cat.name}: {topic_name}")
                .first()
            )
            if not gap:
                gap = KnowledgeGap(
                    topic=f"{cat.name}: {topic_name}",
                    category_id=cat.id,
                    related_ticket_count=len(sub_tkts),
                    common_symptoms=symptoms,
                    suggested_title=suggested_title,
                    priority=priority,
                    status="open",
                )
                db.add(gap)
                db.flush()
            else:
                gap.related_ticket_count = len(sub_tkts)
                gap.common_symptoms = symptoms
                gap.priority = priority

            detected_topics.append(
                {
                    "id": gap.id,
                    "topic": gap.topic,
                    "category_id": cat.id,
                    "category_name": cat.name,
                    "related_ticket_count": len(sub_tkts),
                    "unresolved_count": sub_open,
                    "reopened_count": reopen_cnt,
                    "existing_article_count": len(cat_articles),
                    "topic_covered_by_kb": covered,
                    "has_negative_kb_feedback": has_poor_art,
                    "common_symptoms": symptoms,
                    "suggested_title": gap.suggested_title,
                    "priority": gap.priority,
                    "status": gap.status,
                    "draft_article_id": gap.draft_article_id,
                }
            )

    db.commit()
    detected_topics.sort(key=lambda g: ({"high": 0, "medium": 1, "low": 2}.get(g["priority"], 3), -g["related_ticket_count"]))
    return detected_topics


def compute_resolution_effectiveness(db: Session) -> Dict[str, Any]:
    """
    Measure whether closed tickets were truly resolved effectively:
    - First Contact Resolution (FCR): resolved/closed tickets with <=1 public agent reply and 0 reopens.
    - Reopen Rate & Recurrence After Closure (same customer opening same-category ticket within 14d of closure).
    - Category & Department breakdowns with explicit sample sizes.
    """
    all_tickets = db.query(Ticket).all()
    resolved_pop = [
        t for t in all_tickets if t.status in ("resolved", "closed") or t.resolved_at is not None or (t.reopen_count or 0) > 0
    ]
    n_res = len(resolved_pop)

    if n_res == 0:
        return {
            "insufficient_data": True,
            "sample_size": 0,
            "metrics": {},
            "by_category": [],
            "by_department": [],
            "recommendation_effectiveness": _compute_feedback_stats(db),
            "metric_definitions": {},
        }

    # Index customer tickets by category for repeat-issue / post-closure recurrence detection
    cust_cat_tickets: Dict[tuple[int, int], List[Ticket]] = defaultdict(list)
    for t in all_tickets:
        if t.category_id:
            cust_cat_tickets[(t.customer_id, t.category_id)].append(t)

    fcr_count = 0
    reopened_count = 0
    recurrence_after_closure = 0
    res_durations: List[float] = []
    csat_scores: List[float] = []

    cat_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"resolved": 0, "fcr": 0, "reopened": 0, "res_mins": [], "csat": []})
    dept_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"resolved": 0, "fcr": 0, "reopened": 0, "res_mins": [], "csat": []})

    for t in resolved_pop:
        cat_name = t.category.name if t.category else "Uncategorized"
        dept_name = t.department.name if t.department else "Unassigned"

        public_agent_replies = sum(
            1
            for m in t.messages
            if m.visibility == "public" and m.sender and m.sender.role in ("agent", "manager", "admin")
        )
        is_reopened = (t.reopen_count or 0) > 0
        is_fcr = (t.status in ("resolved", "closed")) and (not is_reopened) and (public_agent_replies <= 1)

        if is_fcr:
            fcr_count += 1
            cat_stats[cat_name]["fcr"] += 1
            dept_stats[dept_name]["fcr"] += 1
        if is_reopened:
            reopened_count += 1
            cat_stats[cat_name]["reopened"] += 1
            dept_stats[dept_name]["reopened"] += 1

        cat_stats[cat_name]["resolved"] += 1
        dept_stats[dept_name]["resolved"] += 1

        if t.resolved_at:
            mins = (ensure_utc(t.resolved_at) - ensure_utc(t.created_at)).total_seconds() / 60.0
            if mins >= 0:
                res_durations.append(mins)
                cat_stats[cat_name]["res_mins"].append(mins)
                dept_stats[dept_name]["res_mins"].append(mins)

            # Check recurrence: did same customer file another same-category ticket within 14d after resolution?
            if t.category_id:
                peers = cust_cat_tickets.get((t.customer_id, t.category_id), [])
                res_ts = ensure_utc(t.resolved_at)
                if any(
                    p.id != t.id and res_ts < ensure_utc(p.created_at) <= res_ts + timedelta(days=14)
                    for p in peers
                ):
                    recurrence_after_closure += 1

        if t.satisfaction_rating is not None:
            csat_scores.append(float(t.satisfaction_rating))
            cat_stats[cat_name]["csat"].append(float(t.satisfaction_rating))
            dept_stats[dept_name]["csat"].append(float(t.satisfaction_rating))

    # Repeat issue rate across all customer-category pairs
    total_pairs = len(cust_cat_tickets)
    repeat_pairs = sum(1 for lst in cust_cat_tickets.values() if len(lst) >= 2)
    repeat_issue_rate = round((repeat_pairs / total_pairs) * 100.0, 1) if total_pairs else 0.0

    def _fmt_breakdown(bucket: Dict[str, Dict[str, Any]], label_key: str) -> List[Dict[str, Any]]:
        rows = []
        for name, st in bucket.items():
            n = st["resolved"]
            rows.append(
                {
                    label_key: name,
                    "sample_size": n,
                    "small_sample_warning": n < 3,
                    "fcr_rate": round((st["fcr"] / n) * 100.0, 1) if n else None,
                    "reopen_rate": round((st["reopened"] / n) * 100.0, 1) if n else None,
                    "avg_resolution_minutes": round(sum(st["res_mins"]) / len(st["res_mins"]), 1) if st["res_mins"] else None,
                    "avg_csat": round(sum(st["csat"]) / len(st["csat"]), 2) if st["csat"] else None,
                }
            )
        rows.sort(key=lambda r: -r["sample_size"])
        return rows

    return {
        "insufficient_data": n_res < 5,
        "sample_size": n_res,
        "metrics": {
            "fcr_rate": round((fcr_count / n_res) * 100.0, 1),
            "reopen_rate": round((reopened_count / n_res) * 100.0, 1),
            "repeat_issue_rate": repeat_issue_rate,
            "recurrence_after_closure_rate": round((recurrence_after_closure / n_res) * 100.0, 1),
            "avg_resolution_minutes": round(sum(res_durations) / len(res_durations), 1) if res_durations else None,
            "avg_csat": round(sum(csat_scores) / len(csat_scores), 2) if csat_scores else None,
            "csat_sample_size": len(csat_scores),
        },
        "by_category": _fmt_breakdown(cat_stats, "category"),
        "by_department": _fmt_breakdown(dept_stats, "department"),
        "recommendation_effectiveness": _compute_feedback_stats(db),
        "metric_definitions": {
            "fcr_rate": f"Resolved/closed tickets solved in <=1 public agent reply with 0 reopens (n={n_res}).",
            "reopen_rate": f"Tickets reopened at least once divided by resolved/reopened population (n={n_res}).",
            "repeat_issue_rate": f"Customer-category pairs with >=2 tickets divided by total customer-category pairs (n={total_pairs}).",
            "recurrence_after_closure_rate": f"Resolved tickets followed by a new same-category ticket from the same customer within 14 days (n={n_res}).",
        },
    }


def _compute_feedback_stats(db: Session) -> Dict[str, Any]:
    rows = db.query(ResolutionFeedback).all()
    total = len(rows)
    counts = Counter(r.rating for r in rows)
    applied = sum(1 for r in rows if r.applied_to_reply)
    return {
        "total_ratings": total,
        "helpful": counts.get("helpful", 0),
        "partially_helpful": counts.get("partially_helpful", 0),
        "not_helpful": counts.get("not_helpful", 0),
        "applied_to_replies": applied,
        "helpful_rate": round(((counts.get("helpful", 0) + 0.5 * counts.get("partially_helpful", 0)) / total) * 100.0, 1)
        if total
        else None,
    }
