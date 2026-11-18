"""Orchestrates ML classification, duplicate/related ticket similarity, sentiment, and KB recommendations."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config.settings import get_settings
from app.models.intelligence import KnowledgeArticle, KnowledgeRecommendation, ModelVersion
from app.models.operations import AppSetting
from app.models.ticket import Category, Ticket
from app.models.user import User
from app.services.priority_service import assess_priority
from app.services.routing_service import route_ticket_by_confidence
from ml.duplicate_detection.similarity import find_similar_tickets
from ml.prediction.predictor import TicketClassifierPredictor
from ml.preprocessing.text_cleaner import combine_ticket_text
from ml.sentiment.analyzer import analyze_sentiment


_predictor_cache: Dict[str, TicketClassifierPredictor] = {}


def get_active_predictor(db: Session) -> tuple[TicketClassifierPredictor, Optional[ModelVersion]]:
    """Load the active ModelVersion artifact from disk (cached by path) or return fallback predictor."""
    active = (
        db.query(ModelVersion)
        .filter(ModelVersion.is_active.is_(True))
        .order_by(ModelVersion.created_at.desc())
        .first()
    )
    if active and active.model_path and Path(active.model_path).exists():
        cached = _predictor_cache.get(active.model_path)
        if cached is None:
            cached = TicketClassifierPredictor(active.model_path)
            _predictor_cache[active.model_path] = cached
        return cached, active

    return TicketClassifierPredictor(None), None


def clear_predictor_cache() -> None:
    _predictor_cache.clear()


def get_similarity_threshold(db: Session) -> float:
    settings = get_settings()
    row = db.query(AppSetting).filter(AppSetting.key == "similarity_threshold").first()
    if row and isinstance(row.value, (int, float)):
        return float(row.value)
    if row and isinstance(row.value, dict) and "threshold" in row.value:
        return float(row.value["threshold"])
    return settings.SIMILARITY_THRESHOLD


def resolve_category_ids(
    db: Session,
    category_name: Optional[str],
    subcategory_name: Optional[str],
) -> tuple[Optional[int], Optional[int]]:
    cat_id = None
    sub_id = None
    if category_name:
        cat = (
            db.query(Category)
            .filter(Category.name == category_name, Category.parent_category_id.is_(None))
            .first()
        )
        if cat:
            cat_id = cat.id
            if subcategory_name:
                sub = (
                    db.query(Category)
                    .filter(Category.name == subcategory_name, Category.parent_category_id == cat.id)
                    .first()
                )
                if sub:
                    sub_id = sub.id
    return cat_id, sub_id


def classify_ticket_text(
    db: Session,
    subject: str,
    description: str,
    product_reference: Optional[str] = None,
) -> Dict[str, Any]:
    """Run full intelligence pipeline: hierarchical classification + priority + routing + sentiment."""
    predictor, active_model = get_active_predictor(db)
    pred = predictor.predict(subject, description, product_reference)

    cat_id, sub_id = resolve_category_ids(db, pred["category"], pred.get("subcategory"))
    routing = route_ticket_by_confidence(db, cat_id, pred["confidence"])
    priority, priority_reason = assess_priority(subject, description)
    sentiment = analyze_sentiment(f"{subject}. {description}")

    return {
        "model_version_id": active_model.id if active_model else None,
        "model_version": pred.get("model_version"),
        "prediction_source": pred.get("prediction_source"),
        "predicted_category_id": cat_id,
        "predicted_category_name": pred["category"],
        "predicted_subcategory_id": sub_id,
        "predicted_subcategory_name": pred.get("subcategory"),
        "confidence": pred["confidence"],
        "alternatives": pred.get("alternatives", []),
        "explanation": pred["explanation"],
        "low_support_warning": pred.get("low_support_warning"),
        "suggested_priority": priority,
        "priority_reason": priority_reason,
        "suggested_department_id": routing["suggested_department_id"],
        "final_department_id": routing["final_department_id"],
        "routing_rule_applied": routing["routing_rule_applied"],
        "routing_decision": routing["routing_decision"],
        "auto_assign_agent": routing["auto_assign_agent"],
        "sentiment": sentiment,
    }


def search_similar_tickets_for_user(
    db: Session,
    ticket: Ticket,
    current_user: User,
    threshold: Optional[float] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search similar tickets strictly within the caller's authorization scope.
    Customers may NEVER see other customers' tickets.
    """
    query = db.query(Ticket).filter(Ticket.id != ticket.id)

    if current_user.role == "customer":
        if not current_user.customer_profile:
            return []
        query = query.filter(Ticket.customer_id == current_user.customer_profile.id)
    elif current_user.role == "agent":
        # Agents can compare within authorized departments or their assigned tickets
        dept_ids = set()
        if current_user.agent_profile:
            if current_user.agent_profile.department_id:
                dept_ids.add(current_user.agent_profile.department_id)
            for link in current_user.agent_profile.department_links:
                dept_ids.add(link.department_id)
        if dept_ids:
            query = query.filter(
                (Ticket.department_id.in_(list(dept_ids))) | (Ticket.department_id.is_(None))
            )

    candidates = [
        {
            "id": t.id,
            "ticket_reference": t.ticket_reference,
            "subject": t.subject,
            "description": t.description,
            "category_name": t.category.name if t.category else None,
            "status": t.status,
            "priority": t.priority,
        }
        for t in query.order_by(Ticket.created_at.desc()).limit(300).all()
    ]

    eff_threshold = threshold if threshold is not None else get_similarity_threshold(db)
    return find_similar_tickets(
        query_subject=ticket.subject,
        query_description=ticket.description,
        candidates=candidates,
        threshold=eff_threshold,
        top_k=top_k,
    )


def recommend_knowledge_articles(
    db: Session,
    ticket: Ticket,
    top_k: int = 3,
    persist: bool = False,
) -> List[Dict[str, Any]]:
    """Recommend published knowledge base articles using TF-IDF similarity + category match bonus."""
    articles = db.query(KnowledgeArticle).filter(KnowledgeArticle.is_published.is_(True)).all()
    if not articles:
        return []

    ticket_text = combine_ticket_text(ticket.subject, ticket.description, ticket.product_reference)
    article_texts = [
        combine_ticket_text(a.title, f"{a.content} {a.tags or ''}")
        for a in articles
    ]

    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        mat = vec.fit_transform([ticket_text] + article_texts)
        sims = cosine_similarity(mat[0:1], mat[1:]).flatten()
    except ValueError:
        return []

    scored = []
    for idx, art in enumerate(articles):
        score = float(sims[idx])
        if ticket.category_id and art.category_id == ticket.category_id:
            score += 0.15
        if score >= 0.08:
            scored.append((round(min(score, 0.99), 4), art))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    results = []
    for score, art in top:
        rec_id = None
        accepted = None
        existing = (
            db.query(KnowledgeRecommendation)
            .filter(
                KnowledgeRecommendation.ticket_id == ticket.id,
                KnowledgeRecommendation.article_id == art.id,
            )
            .first()
        )
        if existing:
            rec_id = existing.id
            accepted = existing.accepted
        elif persist:
            rec = KnowledgeRecommendation(
                ticket_id=ticket.id,
                article_id=art.id,
                relevance_score=score,
            )
            db.add(rec)
            db.flush()
            rec_id = rec.id

        results.append(
            {
                "recommendation_id": rec_id,
                "article_id": art.id,
                "title": art.title,
                "content": art.content,
                "category_id": art.category_id,
                "category_name": art.category.name if art.category else None,
                "tags": art.tags,
                "relevance_score": score,
                "accepted": accepted,
            }
        )
    return results
