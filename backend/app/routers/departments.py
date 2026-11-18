"""Departments Router."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import Department, User
from app.schemas.schemas import DepartmentCreateRequest, DepartmentUpdateRequest
from app.services.analytics_service import compute_department_analytics
from app.services.audit_service import log_audit_event
from app.services.auth_service import get_current_user, require_roles

router = APIRouter(prefix="/api/departments", tags=["Departments"])


@router.get("")
def list_departments(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return compute_department_analytics(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    if db.query(Department).filter(Department.name == payload.name.strip()).first():
        raise HTTPException(status_code=409, detail="Department with this name already exists.")
    dept = Department(name=payload.name.strip(), description=payload.description)
    db.add(dept)
    db.flush()
    log_audit_event(
        db, "department.create", "department", dept.id, current_user.id, {"name": dept.name},
        request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "description": dept.description, "is_active": dept.is_active}


@router.patch("/{department_id}")
def update_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
    db: Session = Depends(get_db),
):
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")
    if payload.name is not None:
        dept.name = payload.name.strip()
    if payload.description is not None:
        dept.description = payload.description
    if payload.is_active is not None:
        dept.is_active = payload.is_active
    log_audit_event(
        db, "department.update", "department", dept.id, current_user.id,
        payload.model_dump(exclude_none=True),
        request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "description": dept.description, "is_active": dept.is_active}


@router.get("/{department_id}/metrics")
def get_department_metrics(
    department_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    all_depts = compute_department_analytics(db)
    for row in all_depts:
        if row["department_id"] == department_id:
            return row
    raise HTTPException(status_code=404, detail="Department not found.")
