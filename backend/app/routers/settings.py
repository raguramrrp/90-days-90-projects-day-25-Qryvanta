"""Settings, Categories, Routing Rules, SLA Policies, Holidays, Users, Knowledge Base & Audit Logs Router."""

from datetime import datetime, timezone
import random
import string
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.models.intelligence import KnowledgeArticle, KnowledgeRecommendation
from app.models.operations import AppSetting, AuditLog, Holiday, RoutingRule, SLAPolicy
from app.models.ticket import Category
from app.models.user import Agent, AgentDepartment, Customer, Department, User
from app.schemas.schemas import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    CategoryCreateRequest,
    CategoryUpdateRequest,
    HolidayCreateRequest,
    KnowledgeArticleCreateRequest,
    KnowledgeRecommendationFeedbackRequest,
    RoutingRuleCreateRequest,
    RoutingRuleUpdateRequest,
    SLAPolicyCreateRequest,
    SLAPolicyUpdateRequest,
    SettingsUpdateRequest,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import get_current_user, hash_password, require_roles
from app.services.routing_service import get_routing_thresholds
from app.services.sla_service import get_business_hours_config

router = APIRouter(tags=["Settings & Configuration"])


# --- Global Settings ---

@router.get("/api/settings")
def get_app_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    high_t, med_t = get_routing_thresholds(db)
    sim_row = db.query(AppSetting).filter(AppSetting.key == "similarity_threshold").first()
    sim_val = get_settings().SIMILARITY_THRESHOLD
    if sim_row:
        sim_val = float(sim_row.value.get("threshold", sim_val) if isinstance(sim_row.value, dict) else sim_row.value)
    notif_row = db.query(AppSetting).filter(AppSetting.key == "notifications").first()
    holidays = db.query(Holiday).order_by(Holiday.holiday_date.asc()).all()

    return {
        "confidence_thresholds": {"high": high_t, "medium": med_t},
        "similarity_threshold": sim_val,
        "business_hours": get_business_hours_config(db),
        "notifications": notif_row.value if notif_row else {"sla_warning_enabled": True, "reopen_alert_enabled": True},
        "holidays": [{"id": h.id, "holiday_date": h.holiday_date.isoformat(), "name": h.name} for h in holidays],
    }


@router.patch("/api/settings")
def update_app_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    def _upsert(key: str, value, desc: str):
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value, description=desc))

    if payload.confidence_thresholds is not None:
        high = float(payload.confidence_thresholds.get("high", 0.80))
        med = float(payload.confidence_thresholds.get("medium", 0.55))
        if not (0.1 <= med < high <= 0.99):
            raise HTTPException(status_code=400, detail="Thresholds must satisfy 0.10 <= medium < high <= 0.99.")
        _upsert("confidence_thresholds", {"high": high, "medium": med}, "Classification routing confidence thresholds")

    if payload.similarity_threshold is not None:
        _upsert("similarity_threshold", {"threshold": payload.similarity_threshold}, "Cosine similarity threshold for related tickets")

    if payload.business_hours is not None:
        _upsert("business_hours", payload.business_hours, "SLA business hours configuration")

    if payload.notifications is not None:
        _upsert("notifications", payload.notifications, "Operational notification preferences")

    log_audit_event(
        db, "settings.update", "app_settings", "global", current_user.id,
        payload.model_dump(exclude_none=True),
        request.client.host if request.client else None,
    )
    db.commit()
    return get_app_settings(current_user=current_user, db=db)


# --- SLA Policies ---

@router.get("/api/sla/policies")
def list_sla_policies(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    policies = db.query(SLAPolicy).order_by(SLAPolicy.priority.asc(), SLAPolicy.id.asc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "priority": p.priority,
            "department_id": p.department_id,
            "department_name": p.department.name if p.department else "All Departments",
            "first_response_minutes": p.first_response_minutes,
            "resolution_minutes": p.resolution_minutes,
            "business_hours_only": p.business_hours_only,
            "is_active": p.is_active,
        }
        for p in policies
    ]


@router.post("/api/sla/policies", status_code=status.HTTP_201_CREATED)
def create_sla_policy(
    payload: SLAPolicyCreateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    if db.query(SLAPolicy).filter(SLAPolicy.name == payload.name.strip()).first():
        raise HTTPException(status_code=409, detail="An SLA policy with this name already exists.")
    policy = SLAPolicy(
        name=payload.name.strip(),
        priority=payload.priority,
        department_id=payload.department_id,
        first_response_minutes=payload.first_response_minutes,
        resolution_minutes=payload.resolution_minutes,
        business_hours_only=payload.business_hours_only,
        is_active=True,
    )
    db.add(policy)
    db.flush()
    log_audit_event(db, "sla_policy.create", "sla_policy", policy.id, current_user.id, {"name": policy.name})
    db.commit()
    db.refresh(policy)
    return {"id": policy.id, "name": policy.name, "priority": policy.priority}


@router.patch("/api/sla/policies/{policy_id}")
def update_sla_policy(
    policy_id: int,
    payload: SLAPolicyUpdateRequest,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found.")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(policy, field, val)
    log_audit_event(db, "sla_policy.update", "sla_policy", policy.id, current_user.id, payload.model_dump(exclude_none=True))
    db.commit()
    return {"id": policy.id, "status": "updated"}


# --- Holidays ---

@router.post("/api/holidays", status_code=status.HTTP_201_CREATED)
def add_holiday(
    payload: HolidayCreateRequest,
    current_user: User = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    if db.query(Holiday).filter(Holiday.holiday_date == payload.holiday_date).first():
        raise HTTPException(status_code=409, detail="Holiday already configured for this date.")
    h = Holiday(holiday_date=payload.holiday_date, name=payload.name.strip())
    db.add(h)
    db.commit()
    db.refresh(h)
    return {"id": h.id, "holiday_date": h.holiday_date.isoformat(), "name": h.name}


@router.delete("/api/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    current_user: User = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    h = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holiday not found.")
    db.delete(h)
    db.commit()
    return {"deleted": True}


# --- Categories & Subcategories ---

@router.get("/api/categories")
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parents = (
        db.query(Category)
        .filter(Category.parent_category_id.is_(None))
        .order_by(Category.name.asc())
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "is_active": p.is_active,
            "subcategories": [
                {
                    "id": s.id,
                    "name": s.name,
                    "parent_category_id": s.parent_category_id,
                    "description": s.description,
                    "is_active": s.is_active,
                }
                for s in sorted(p.subcategories, key=lambda x: x.name)
            ],
        }
        for p in parents
    ]


@router.post("/api/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    cat = Category(
        name=payload.name.strip(),
        parent_category_id=payload.parent_category_id,
        description=payload.description,
        is_active=True,
    )
    db.add(cat)
    db.flush()
    log_audit_event(db, "category.create", "category", cat.id, current_user.id, {"name": cat.name})
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "parent_category_id": cat.parent_category_id}


@router.patch("/api/categories/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(cat, k, v)
    db.commit()
    return {"id": cat.id, "status": "updated"}


# --- Routing Rules ---

@router.get("/api/routing-rules")
def list_routing_rules(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rules = db.query(RoutingRule).order_by(RoutingRule.id.asc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "category_id": r.category_id,
            "category_name": r.category.name if r.category else None,
            "department_id": r.department_id,
            "department_name": r.department.name if r.department else None,
            "min_confidence": r.min_confidence,
            "auto_assign_agent": r.auto_assign_agent,
            "is_active": r.is_active,
        }
        for r in rules
    ]


@router.post("/api/routing-rules", status_code=status.HTTP_201_CREATED)
def create_routing_rule(
    payload: RoutingRuleCreateRequest,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    rule = RoutingRule(
        name=payload.name.strip(),
        category_id=payload.category_id,
        department_id=payload.department_id,
        min_confidence=payload.min_confidence,
        auto_assign_agent=payload.auto_assign_agent,
        is_active=True,
    )
    db.add(rule)
    db.flush()
    log_audit_event(db, "routing_rule.create", "routing_rule", rule.id, current_user.id, {"name": rule.name})
    db.commit()
    return {"id": rule.id, "name": rule.name}


@router.patch("/api/routing-rules/{rule_id}")
def update_routing_rule(
    rule_id: int,
    payload: RoutingRuleUpdateRequest,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    log_audit_event(db, "routing_rule.update", "routing_rule", rule.id, current_user.id, payload.model_dump(exclude_none=True))
    db.commit()
    return {"id": rule.id, "status": "updated"}


# --- User Management (Admin only) ---

@router.get("/api/users")
def list_users(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/api/users", status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: AdminUserCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    email_norm = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        name=payload.name.strip(),
        email=email_norm,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    if payload.role == "customer":
        ref = f"CUST-{datetime.now(timezone.utc).year}-{''.join(random.choices(string.digits, k=5))}"
        db.add(Customer(user_id=user.id, customer_reference=ref))
    elif payload.role in ("agent", "manager"):
        agent = Agent(
            user_id=user.id,
            department_id=payload.department_id,
            expertise=payload.expertise,
            max_open_tickets=payload.max_open_tickets,
        )
        db.add(agent)
        db.flush()
        if payload.department_id:
            db.add(AgentDepartment(agent_id=agent.id, department_id=payload.department_id))

    log_audit_event(db, "user.create", "user", user.id, current_user.id, {"email": user.email, "role": user.role})
    db.commit()
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@router.patch("/api/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    log_audit_event(db, "user.update", "user", user.id, current_user.id, payload.model_dump(exclude_none=True))
    db.commit()
    return {"id": user.id, "status": "updated"}


# --- Knowledge Base ---

@router.get("/api/knowledge")
def list_knowledge_articles(
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(KnowledgeArticle)
    if current_user.role == "customer":
        q = q.filter(KnowledgeArticle.is_published.is_(True))
    if category_id is not None:
        q = q.filter(KnowledgeArticle.category_id == category_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            KnowledgeArticle.title.ilike(term)
            | KnowledgeArticle.content.ilike(term)
            | KnowledgeArticle.tags.ilike(term)
        )
    articles = q.order_by(KnowledgeArticle.updated_at.desc()).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "category_id": a.category_id,
            "category_name": a.category.name if a.category else None,
            "tags": a.tags,
            "is_published": a.is_published,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in articles
    ]


@router.post("/api/knowledge", status_code=status.HTTP_201_CREATED)
def create_knowledge_article(
    payload: KnowledgeArticleCreateRequest,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    art = KnowledgeArticle(
        title=payload.title.strip(),
        content=payload.content.strip(),
        category_id=payload.category_id,
        tags=payload.tags,
        is_published=payload.is_published,
    )
    db.add(art)
    db.flush()
    log_audit_event(db, "knowledge.create", "knowledge_article", art.id, current_user.id, {"title": art.title})
    db.commit()
    return {"id": art.id, "title": art.title}


@router.post("/api/knowledge/recommendations/{rec_id}/feedback")
def rate_knowledge_recommendation(
    rec_id: int,
    payload: KnowledgeRecommendationFeedbackRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rec = db.query(KnowledgeRecommendation).filter(KnowledgeRecommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation record not found.")
    rec.accepted = payload.accepted
    db.commit()
    return {"id": rec.id, "accepted": rec.accepted}


# --- Audit Logs (Admin only) ---

@router.get("/api/audit-logs")
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_name": l.user.name if l.user else "System",
            "user_email": l.user.email if l.user else None,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
