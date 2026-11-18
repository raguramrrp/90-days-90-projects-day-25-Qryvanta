"""Pytest fixtures providing an isolated SQLite database and FastAPI TestClient for QRYVANTA."""

from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.session import Base, get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401
from app.models.operations import AppSetting, RoutingRule, SLAPolicy
from app.models.ticket import Category
from app.models.user import Agent, AgentDepartment, Customer, Department, User
from app.services.auth_service import create_access_token, hash_password


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_file = tmp_path / "test_qryvanta.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # Seed baseline taxonomy, departments, rules, SLA policies, and test actors
    billing_dept = Department(name="Billing", description="Billing & payments")
    tech_dept = Department(name="Technical Support", description="Software engineering support")
    db.add_all([billing_dept, tech_dept])
    db.flush()

    billing_cat = Category(name="Billing and Payments", description="Billing issues")
    tech_cat = Category(name="Technical Support", description="Tech issues")
    db.add_all([billing_cat, tech_cat])
    db.flush()

    refund_sub = Category(name="Refund Request", parent_category_id=billing_cat.id)
    app_err_sub = Category(name="Application Error", parent_category_id=tech_cat.id)
    db.add_all([refund_sub, app_err_sub])
    db.flush()

    db.add_all([
        RoutingRule(name="Billing Rule", category_id=billing_cat.id, department_id=billing_dept.id, min_confidence=0.55),
        RoutingRule(name="Tech Rule", category_id=tech_cat.id, department_id=tech_dept.id, min_confidence=0.55),
        SLAPolicy(name="Critical SLA", priority="critical", first_response_minutes=30, resolution_minutes=240, business_hours_only=False),
        SLAPolicy(name="High SLA", priority="high", first_response_minutes=60, resolution_minutes=480, business_hours_only=True),
        SLAPolicy(name="Medium SLA", priority="medium", first_response_minutes=240, resolution_minutes=1440, business_hours_only=True),
        SLAPolicy(name="Low SLA", priority="low", first_response_minutes=480, resolution_minutes=2880, business_hours_only=True),
        AppSetting(key="confidence_thresholds", value={"high": 0.80, "medium": 0.55}),
    ])

    pw = hash_password("TestPass#2026")
    admin = User(name="Admin User", email="admin@test.local", password_hash=pw, role="admin")
    manager = User(name="Manager User", email="manager@test.local", password_hash=pw, role="manager")
    agent_u = User(name="Billing Agent", email="agent@test.local", password_hash=pw, role="agent")
    cust1_u = User(name="Customer One", email="cust1@test.local", password_hash=pw, role="customer")
    cust2_u = User(name="Customer Two", email="cust2@test.local", password_hash=pw, role="customer")
    db.add_all([admin, manager, agent_u, cust1_u, cust2_u])
    db.flush()

    agent_p = Agent(user_id=agent_u.id, department_id=billing_dept.id, expertise="Billing, Refunds", max_open_tickets=10)
    db.add(agent_p)
    db.flush()
    db.add(AgentDepartment(agent_id=agent_p.id, department_id=billing_dept.id))

    db.add_all([
        Customer(user_id=cust1_u.id, customer_reference="CUST-T-001", contact_information="cust1@test.local"),
        Customer(user_id=cust2_u.id, customer_reference="CUST-T-002", contact_information="cust2@test.local"),
    ])
    db.commit()

    yield db

    db.close()
    engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def auth_headers(db_session, email: str) -> dict:
    user = db_session.query(User).filter(User.email == email).first()
    token = create_access_token(user.id, user.role, user.email)
    return {"Authorization": f"Bearer {token}"}
