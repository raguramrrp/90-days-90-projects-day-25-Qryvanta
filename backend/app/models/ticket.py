from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
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


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", "parent_category_id", name="uq_category_name_parent"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    parent_category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    parent = relationship("Category", remote_side=[id], backref="subcategories")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_reference = Column(String(40), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    product_reference = Column(String(120), nullable=True)

    # Multi-platform / Company Portal Intake & Verification Handoff
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    platform_type = Column(String(60), nullable=True, index=True)
    external_reference = Column(String(120), nullable=True, index=True)
    verification_status = Column(String(40), nullable=False, default="unverified", index=True)
    # unverified | under_verification | verified_ready | reported_to_company | company_acknowledged | company_resolved | insufficient_proof
    verification_notes = Column(Text, nullable=True)
    recommended_company_action = Column(Text, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    reported_to_company_at = Column(DateTime(timezone=True), nullable=True)
    company_case_reference = Column(String(120), nullable=True)

    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(String(20), nullable=False, default="medium", index=True)
    priority_reason = Column(Text, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="new", index=True)
    source = Column(String(40), nullable=False, default="web_portal")
    is_demo_data = Column(Boolean, nullable=False, default=False, index=True)

    sentiment_label = Column(String(20), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    sentiment_method = Column(String(60), nullable=True)

    reopen_count = Column(Integer, nullable=False, default=0)
    reopen_reason = Column(Text, nullable=True)
    satisfaction_rating = Column(Integer, nullable=True)
    satisfaction_comment = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    reopened_at = Column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", back_populates="tickets")
    company = relationship("Company", back_populates="tickets")
    verifier = relationship("User", foreign_keys=[verified_by])
    category = relationship("Category", foreign_keys=[category_id])
    subcategory = relationship("Category", foreign_keys=[subcategory_id])
    department = relationship("Department", back_populates="tickets")
    assigned_agent = relationship("Agent", back_populates="assigned_tickets")

    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketMessage.created_at")
    assignments = relationship("TicketAssignment", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketAssignment.assigned_at")
    events = relationship("TicketEvent", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketEvent.created_at")
    attachments = relationship("TicketAttachment", back_populates="ticket", cascade="all, delete-orphan")
    predictions = relationship("TicketPrediction", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketPrediction.created_at.desc()")
    feedbacks = relationship("TicketFeedback", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketFeedback.created_at.desc()")
    sla_tracking = relationship("SLATracking", back_populates="ticket", uselist=False, cascade="all, delete-orphan")
    knowledge_recommendations = relationship("KnowledgeRecommendation", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(Text, nullable=False)
    visibility = Column(String(20), nullable=False, default="public", index=True)  # public | internal
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    ticket = relationship("Ticket", back_populates="messages")
    sender = relationship("User")


class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignment_reason = Column(Text, nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", back_populates="assignments")
    agent = relationship("Agent")
    department = relationship("Department")
    assigner = relationship("User")


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(60), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    event_description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="events")
    actor = relationship("User")


class TicketRelation(Base):
    __tablename__ = "ticket_relations"
    __table_args__ = (
        UniqueConstraint("source_ticket_id", "related_ticket_id", "relation_type", name="uq_ticket_relation"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    related_ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(30), nullable=False, default="related")  # duplicate | related
    similarity_score = Column(Float, nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    source_ticket = relationship("Ticket", foreign_keys=[source_ticket_id])
    related_ticket = relationship("Ticket", foreign_keys=[related_ticket_id])
    confirmer = relationship("User")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("ticket_messages.id", ondelete="SET NULL"), nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="attachments")
    uploader = relationship("User")
