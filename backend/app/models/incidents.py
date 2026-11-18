"""Additive SQLAlchemy ORM models for Incidents, Resolution Feedback, and Knowledge Gaps."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_reference = Column(String(40), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="high", index=True)  # critical | high | medium | low
    status = Column(String(30), nullable=False, default="detected", index=True)
    # detected | investigating | confirmed | monitoring | resolved | dismissed
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    common_symptoms = Column(JSON, nullable=False, default=list)
    investigation_notes = Column(Text, nullable=True)
    resolution_summary = Column(Text, nullable=True)
    is_auto_detected = Column(Boolean, nullable=False, default=True)
    is_demo_data = Column(Boolean, nullable=False, default=False, index=True)
    first_reported_at = Column(DateTime(timezone=True), nullable=True)
    last_reported_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    department = relationship("Department")
    owner = relationship("User")
    ticket_links = relationship("IncidentTicket", back_populates="incident", cascade="all, delete-orphan")
    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentEvent.created_at.desc()")


class IncidentTicket(Base):
    __tablename__ = "incident_tickets"
    __table_args__ = (
        UniqueConstraint("incident_id", "ticket_id", name="uq_incident_ticket"),
    )

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=True)
    linked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    linked_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="ticket_links")
    ticket = relationship("Ticket")
    linker = relationship("User")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(60), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="events")
    actor = relationship("User")


class ResolutionFeedback(Base):
    __tablename__ = "resolution_feedback"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    source_ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_type = Column(String(30), nullable=False, default="similar_ticket")  # similar_ticket | knowledge_article
    rating = Column(String(30), nullable=False)  # helpful | partially_helpful | not_helpful
    applied_to_reply = Column(Boolean, nullable=False, default=False)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", foreign_keys=[ticket_id])
    source_ticket = relationship("Ticket", foreign_keys=[source_ticket_id])
    article = relationship("KnowledgeArticle")
    submitter = relationship("User")


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(180), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    related_ticket_count = Column(Integer, nullable=False, default=0)
    common_symptoms = Column(JSON, nullable=False, default=list)
    suggested_title = Column(String(220), nullable=False)
    priority = Column(String(20), nullable=False, default="medium")  # high | medium | low
    status = Column(String(30), nullable=False, default="open", index=True)  # open | draft_created | dismissed
    draft_article_id = Column(Integer, ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    category = relationship("Category")
    draft_article = relationship("KnowledgeArticle")
