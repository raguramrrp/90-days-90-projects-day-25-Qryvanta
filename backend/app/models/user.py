from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="customer", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    customer_profile = relationship("Customer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    agent_profile = relationship("Agent", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    customer_reference = Column(String(50), unique=True, nullable=False, index=True)
    contact_information = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="customer_profile")
    tickets = relationship("Ticket", back_populates="customer")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    agents = relationship("Agent", back_populates="primary_department")
    agent_memberships = relationship("AgentDepartment", back_populates="department", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="department")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    availability_status = Column(String(30), nullable=False, default="available", index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    expertise = Column(Text, nullable=True)
    max_open_tickets = Column(Integer, nullable=False, default=15)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="agent_profile")
    primary_department = relationship("Department", back_populates="agents")
    department_links = relationship("AgentDepartment", back_populates="agent", cascade="all, delete-orphan")
    assigned_tickets = relationship("Ticket", back_populates="assigned_agent")


class AgentDepartment(Base):
    __tablename__ = "agent_departments"
    __table_args__ = (
        UniqueConstraint("agent_id", "department_id", name="uq_agent_department"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)

    agent = relationship("Agent", back_populates="department_links")
    department = relationship("Department", back_populates="agent_memberships")
