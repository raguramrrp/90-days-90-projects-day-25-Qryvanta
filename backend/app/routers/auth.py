"""Authentication & Profile Router."""

from datetime import datetime, timezone
import random
import string
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import Customer, User
from app.schemas.schemas import (
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserProfileResponse,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.utils.security import auth_rate_limiter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _serialize_user(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        customer_id=user.customer_profile.id if user.customer_profile else None,
        customer_reference=user.customer_profile.customer_reference if user.customer_profile else None,
        contact_information=user.customer_profile.contact_information if user.customer_profile else None,
        agent_id=user.agent_profile.id if user.agent_profile else None,
        department_id=user.agent_profile.department_id if user.agent_profile else None,
        department_name=(
            user.agent_profile.primary_department.name
            if (user.agent_profile and user.agent_profile.primary_department)
            else None
        ),
        availability_status=user.agent_profile.availability_status if user.agent_profile else None,
        created_at=user.created_at,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    auth_rate_limiter.check(request, "register")
    email_norm = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        name=payload.name.strip(),
        email=email_norm,
        password_hash=hash_password(payload.password),
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.flush()

    cust_ref = f"CUST-{datetime.now(timezone.utc).year}-{''.join(random.choices(string.digits, k=5))}"
    customer = Customer(
        user_id=user.id,
        customer_reference=cust_ref,
        contact_information=payload.contact_information,
    )
    db.add(customer)
    log_audit_event(
        db,
        action="auth.register",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        details={"email": user.email, "role": "customer"},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user)}


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    auth_rate_limiter.check(request, "login")
    email_norm = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")

    token = create_access_token(user.id, user.role, user.email)
    log_audit_event(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        details={"role": user.role},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user)}


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.patch("/me", response_model=UserProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.name:
        current_user.name = payload.name.strip()
    if payload.contact_information is not None and current_user.customer_profile:
        current_user.customer_profile.contact_information = payload.contact_information.strip()
    if payload.availability_status is not None and current_user.agent_profile:
        current_user.agent_profile.availability_status = payload.availability_status
    db.commit()
    db.refresh(current_user)
    return _serialize_user(current_user)


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_audit_event(
        db,
        action="auth.logout",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"message": "Signed out successfully."}
