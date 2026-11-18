"""Agents & Workload Recommendation Router."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.ticket import Ticket
from app.models.user import Agent, AgentDepartment, Department, User
from app.schemas.schemas import AgentCreateRequest, AgentRecommendRequest, AgentUpdateRequest
from app.services.analytics_service import compute_agent_analytics
from app.services.audit_service import log_audit_event
from app.services.auth_service import hash_password, require_roles
from app.services.routing_service import OPEN_TICKET_STATUSES, recommend_agents

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.get("")
def list_agents(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_agent_analytics(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    email_norm = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")
    dept = db.query(Department).filter(Department.id == payload.department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Primary department not found.")

    user = User(
        name=payload.name.strip(),
        email=email_norm,
        password_hash=hash_password(payload.password),
        role="agent",
        is_active=True,
    )
    db.add(user)
    db.flush()

    agent = Agent(
        user_id=user.id,
        department_id=dept.id,
        expertise=payload.expertise,
        max_open_tickets=payload.max_open_tickets,
        availability_status=payload.availability_status,
    )
    db.add(agent)
    db.flush()

    dept_ids = {dept.id} | set(payload.additional_department_ids)
    for did in dept_ids:
        db.add(AgentDepartment(agent_id=agent.id, department_id=did))

    log_audit_event(
        db, "agent.create", "agent", agent.id, current_user.id,
        {"email": user.email, "department_id": dept.id},
        request.client.host if request.client else None,
    )
    db.commit()
    return {"agent_id": agent.id, "user_id": user.id, "name": user.name, "email": user.email, "department_id": dept.id}


@router.patch("/{agent_id}")
def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    if payload.department_id is not None:
        agent.department_id = payload.department_id
        if not db.query(AgentDepartment).filter(
            AgentDepartment.agent_id == agent.id,
            AgentDepartment.department_id == payload.department_id,
        ).first():
            db.add(AgentDepartment(agent_id=agent.id, department_id=payload.department_id))
    if payload.additional_department_ids is not None:
        db.query(AgentDepartment).filter(AgentDepartment.agent_id == agent.id).delete()
        all_depts = set(payload.additional_department_ids)
        if agent.department_id:
            all_depts.add(agent.department_id)
        for did in all_depts:
            db.add(AgentDepartment(agent_id=agent.id, department_id=did))
    if payload.expertise is not None:
        agent.expertise = payload.expertise
    if payload.max_open_tickets is not None:
        agent.max_open_tickets = payload.max_open_tickets
    if payload.availability_status is not None:
        agent.availability_status = payload.availability_status
    if payload.is_active is not None and agent.user:
        agent.user.is_active = payload.is_active

    log_audit_event(
        db, "agent.update", "agent", agent.id, current_user.id,
        payload.model_dump(exclude_none=True),
        request.client.host if request.client else None,
    )
    db.commit()
    return {"agent_id": agent.id, "status": "updated"}


@router.get("/{agent_id}/workload")
def get_agent_workload(
    agent_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    open_tickets = (
        db.query(Ticket)
        .filter(Ticket.assigned_agent_id == agent.id, Ticket.status.in_(OPEN_TICKET_STATUSES))
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return {
        "agent_id": agent.id,
        "name": agent.user.name if agent.user else None,
        "availability_status": agent.availability_status,
        "max_open_tickets": agent.max_open_tickets,
        "open_count": len(open_tickets),
        "tickets": [
            {
                "id": t.id,
                "ticket_reference": t.ticket_reference,
                "subject": t.subject,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in open_tickets
        ],
    }


@router.post("/recommend")
def recommend_agent_for_ticket(
    payload: AgentRecommendRequest,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    recs = recommend_agents(
        db,
        department_id=payload.department_id,
        category_name=payload.category_name,
        priority=payload.priority,
        limit=payload.limit,
    )
    return {"recommendations": recs}
