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
)
from sqlalchemy.orm import relationship
from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(120), nullable=False)
    version = Column(String(40), unique=True, nullable=False, index=True)
    algorithm = Column(String(120), nullable=False)
    dataset_reference = Column(String(255), nullable=False)
    training_date = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    evaluation_metrics = Column(JSON, nullable=False, default=dict)
    model_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TicketPrediction(Base):
    __tablename__ = "ticket_predictions"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    predicted_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    predicted_subcategory_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    suggested_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    final_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    suggested_priority = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0, index=True)
    alternative_predictions = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    routing_rule_applied = Column(String(120), nullable=True)
    routing_decision = Column(String(40), nullable=True)  # auto_routed | review_suggested | manual_triage | overridden
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="predictions")
    model_version = relationship("ModelVersion")
    predicted_category = relationship("Category", foreign_keys=[predicted_category_id])
    predicted_subcategory = relationship("Category", foreign_keys=[predicted_subcategory_id])
    suggested_department = relationship("Department", foreign_keys=[suggested_department_id])
    final_department = relationship("Department", foreign_keys=[final_department_id])


class TicketFeedback(Base):
    __tablename__ = "ticket_feedback"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id = Column(Integer, ForeignKey("ticket_predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    corrected_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    corrected_subcategory_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    corrected_priority = Column(String(20), nullable=True)
    corrected_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    correction_reason = Column(Text, nullable=False)
    corrected_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="feedbacks")
    prediction = relationship("TicketPrediction")
    corrected_category = relationship("Category", foreign_keys=[corrected_category_id])
    corrected_subcategory = relationship("Category", foreign_keys=[corrected_subcategory_id])
    corrected_department = relationship("Department", foreign_keys=[corrected_department_id])
    corrector = relationship("User")
    model_version = relationship("ModelVersion")


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    tags = Column(String(255), nullable=True)
    is_published = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    category = relationship("Category")


class KnowledgeRecommendation(Base):
    __tablename__ = "knowledge_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance_score = Column(Float, nullable=False, default=0.0)
    accepted = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="knowledge_recommendations")
    article = relationship("KnowledgeArticle")
