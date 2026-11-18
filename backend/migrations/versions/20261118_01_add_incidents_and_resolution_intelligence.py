"""Add incidents, incident_tickets, incident_events, resolution_feedback, and knowledge_gaps tables.

Revision ID: 20261118_01
Revises:
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa


revision = "20261118_01"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("incidents"):
        op.create_table(
            "incidents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("incident_reference", sa.String(40), nullable=False, unique=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(20), nullable=False, server_default="high"),
            sa.Column("status", sa.String(30), nullable=False, server_default="detected"),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("common_symptoms", sa.JSON(), nullable=False),
            sa.Column("investigation_notes", sa.Text(), nullable=True),
            sa.Column("resolution_summary", sa.Text(), nullable=True),
            sa.Column("is_auto_detected", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("first_reported_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_reported_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_incidents_reference", "incidents", ["incident_reference"], unique=True)
        op.create_index("ix_incidents_status", "incidents", ["status"])
        op.create_index("ix_incidents_severity", "incidents", ["severity"])

    if not _table_exists("incident_tickets"):
        op.create_table(
            "incident_tickets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("similarity_score", sa.Float(), nullable=True),
            sa.Column("linked_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("incident_id", "ticket_id", name="uq_incident_ticket"),
        )
        op.create_index("ix_incident_tickets_incident_id", "incident_tickets", ["incident_id"])
        op.create_index("ix_incident_tickets_ticket_id", "incident_tickets", ["ticket_id"])

    if not _table_exists("incident_events"):
        op.create_table(
            "incident_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(60), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])

    if not _table_exists("resolution_feedback"):
        op.create_table(
            "resolution_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True),
            sa.Column("article_id", sa.Integer(), sa.ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("recommendation_type", sa.String(30), nullable=False, server_default="similar_ticket"),
            sa.Column("rating", sa.String(30), nullable=False),
            sa.Column("applied_to_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_resolution_feedback_ticket_id", "resolution_feedback", ["ticket_id"])

    if not _table_exists("knowledge_gaps"):
        op.create_table(
            "knowledge_gaps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("topic", sa.String(180), nullable=False),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("related_ticket_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("common_symptoms", sa.JSON(), nullable=False),
            sa.Column("suggested_title", sa.String(220), nullable=False),
            sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(30), nullable=False, server_default="open"),
            sa.Column("draft_article_id", sa.Integer(), sa.ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_knowledge_gaps_status", "knowledge_gaps", ["status"])


def downgrade() -> None:
    for table in ("knowledge_gaps", "resolution_feedback", "incident_events", "incident_tickets", "incidents"):
        if _table_exists(table):
            op.drop_table(table)
