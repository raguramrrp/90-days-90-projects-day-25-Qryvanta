"""Pydantic v2 request and response validation schemas for QRYVANTA."""

from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

EmailAddress = Annotated[str, Field(min_length=5, max_length=180, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


# --- Auth ---

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailAddress
    password: str = Field(..., min_length=8, max_length=128)
    contact_information: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(..., min_length=1, max_length=128)


class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    customer_id: Optional[int] = None
    customer_reference: Optional[str] = None
    contact_information: Optional[str] = None
    agent_id: Optional[int] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    availability_status: Optional[str] = None
    created_at: Optional[datetime] = None


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    contact_information: Optional[str] = Field(None, max_length=255)
    availability_status: Optional[Literal["available", "busy", "away", "offline"]] = None


class AdminUserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailAddress
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["customer", "agent", "manager", "admin"]
    department_id: Optional[int] = None
    expertise: Optional[str] = None
    max_open_tickets: int = Field(15, ge=1, le=200)


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    role: Optional[Literal["customer", "agent", "manager", "admin"]] = None
    is_active: Optional[bool] = None


# --- Tickets ---

class TicketCreateRequest(BaseModel):
    subject: str = Field(..., min_length=4, max_length=255)
    description: str = Field(..., min_length=10, max_length=8000)
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    product_reference: Optional[str] = Field(None, max_length=120)
    contact_information: Optional[str] = Field(None, max_length=255)
    company_id: Optional[int] = None
    platform_type: Optional[str] = Field(None, max_length=60)
    external_reference: Optional[str] = Field(None, max_length=120)


class TicketVerifyRequest(BaseModel):
    verification_status: Literal[
        "unverified",
        "under_verification",
        "verified_ready",
        "reported_to_company",
        "company_acknowledged",
        "company_resolved",
        "insufficient_proof",
    ]
    verification_notes: str = Field(..., min_length=5, max_length=3000)
    recommended_company_action: Optional[str] = Field(None, max_length=2000)
    company_case_reference: Optional[str] = Field(None, max_length=120)


class CompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=140)
    platform_type: str = Field(..., min_length=2, max_length=60)
    portal_url: Optional[str] = Field(None, max_length=255)
    support_email: Optional[EmailAddress] = None
    description: Optional[str] = Field(None, max_length=500)


class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=140)
    platform_type: Optional[str] = Field(None, min_length=2, max_length=60)
    portal_url: Optional[str] = Field(None, max_length=255)
    support_email: Optional[EmailAddress] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class TicketUpdateRequest(BaseModel):
    status: Optional[Literal["new", "open", "in_progress", "awaiting_customer", "resolved", "closed", "reopened"]] = None
    priority: Optional[Literal["critical", "high", "medium", "low"]] = None
    priority_override_reason: Optional[str] = Field(None, max_length=500)
    department_id: Optional[int] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    override_reason: Optional[str] = Field(None, max_length=500)


class TicketReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    visibility: Literal["public", "internal"] = "public"
    new_status: Optional[Literal["open", "in_progress", "awaiting_customer", "resolved"]] = None


class TicketAssignRequest(BaseModel):
    agent_id: Optional[int] = None
    department_id: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


class TicketReclassifyRequest(BaseModel):
    corrected_category_id: int
    corrected_subcategory_id: Optional[int] = None
    corrected_priority: Optional[Literal["critical", "high", "medium", "low"]] = None
    corrected_department_id: Optional[int] = None
    correction_reason: str = Field(..., min_length=3, max_length=500)


class TicketCloseRequest(BaseModel):
    resolution_note: Optional[str] = Field(None, max_length=2000)
    status: Literal["resolved", "closed"] = "resolved"


class TicketReopenRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class TicketRatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class TicketRelationCreateRequest(BaseModel):
    related_ticket_id: int
    relation_type: Literal["duplicate", "related"] = "related"
    similarity_score: Optional[float] = None


class BulkTicketActionRequest(BaseModel):
    ticket_ids: List[int] = Field(..., min_length=1, max_length=100)
    action: Literal["assign", "status", "department"]
    agent_id: Optional[int] = None
    department_id: Optional[int] = None
    status: Optional[Literal["open", "in_progress", "awaiting_customer", "resolved", "closed"]] = None
    reason: Optional[str] = None


# --- Intelligence ---

class ClassifyRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=8000)
    product_reference: Optional[str] = None


class BulkClassifyRequest(BaseModel):
    items: List[ClassifyRequest] = Field(..., min_length=1, max_length=100)


class BulkImportExecuteRequest(BaseModel):
    csv_text: str = Field(..., min_length=5)
    column_mapping: Dict[str, str]
    is_demo_data: bool = False


# --- Departments & Agents ---

class DepartmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailAddress
    password: str = Field(..., min_length=8, max_length=128)
    department_id: int
    additional_department_ids: List[int] = Field(default_factory=list)
    expertise: Optional[str] = Field(None, max_length=500)
    max_open_tickets: int = Field(15, ge=1, le=200)
    availability_status: Literal["available", "busy", "away", "offline"] = "available"


class AgentUpdateRequest(BaseModel):
    department_id: Optional[int] = None
    additional_department_ids: Optional[List[int]] = None
    expertise: Optional[str] = Field(None, max_length=500)
    max_open_tickets: Optional[int] = Field(None, ge=1, le=200)
    availability_status: Optional[Literal["available", "busy", "away", "offline"]] = None
    is_active: Optional[bool] = None


class AgentRecommendRequest(BaseModel):
    department_id: Optional[int] = None
    category_name: Optional[str] = None
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    limit: int = Field(3, ge=1, le=10)


# --- Categories, Routing, SLA, Knowledge, Settings ---

class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    parent_category_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class RoutingRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    category_id: int
    department_id: int
    min_confidence: float = Field(0.55, ge=0.0, le=1.0)
    auto_assign_agent: bool = False


class RoutingRuleUpdateRequest(BaseModel):
    department_id: Optional[int] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_assign_agent: Optional[bool] = None
    is_active: Optional[bool] = None


class SLAPolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    priority: Literal["critical", "high", "medium", "low"]
    department_id: Optional[int] = None
    first_response_minutes: int = Field(..., ge=5, le=43200)
    resolution_minutes: int = Field(..., ge=15, le=129600)
    business_hours_only: bool = True


class SLAPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    first_response_minutes: Optional[int] = Field(None, ge=5, le=43200)
    resolution_minutes: Optional[int] = Field(None, ge=15, le=129600)
    business_hours_only: Optional[bool] = None
    is_active: Optional[bool] = None


class HolidayCreateRequest(BaseModel):
    holiday_date: date
    name: str = Field(..., min_length=2, max_length=120)


class SettingsUpdateRequest(BaseModel):
    confidence_thresholds: Optional[Dict[str, float]] = None
    similarity_threshold: Optional[float] = Field(None, ge=0.05, le=0.95)
    business_hours: Optional[Dict[str, Any]] = None
    notifications: Optional[Dict[str, Any]] = None


class KnowledgeArticleCreateRequest(BaseModel):
    title: str = Field(..., min_length=4, max_length=200)
    content: str = Field(..., min_length=10, max_length=12000)
    category_id: Optional[int] = None
    tags: Optional[str] = Field(None, max_length=255)
    is_published: bool = True


class KnowledgeRecommendationFeedbackRequest(BaseModel):
    accepted: bool


class ModelTrainRequest(BaseModel):
    include_feedback_corrections: bool = True
    activate_immediately: bool = False
    version_label: Optional[str] = Field(None, max_length=40)


# --- Incidents (Phase 1) ---

class IncidentDetectRequest(BaseModel):
    window_days: int = Field(14, ge=1, le=90)
    similarity_threshold: float = Field(0.28, ge=0.10, le=0.90)
    min_cluster_size: int = Field(3, ge=2, le=20)


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=4, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    severity: Literal["critical", "high", "medium", "low"] = "high"
    department_id: Optional[int] = None
    owner_id: Optional[int] = None
    ticket_ids: List[int] = Field(default_factory=list)
    common_symptoms: List[str] = Field(default_factory=list)


class IncidentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=4, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    severity: Optional[Literal["critical", "high", "medium", "low"]] = None
    status: Optional[Literal["detected", "investigating", "confirmed", "monitoring", "resolved", "dismissed"]] = None
    department_id: Optional[int] = None
    owner_id: Optional[int] = None
    investigation_notes: Optional[str] = Field(None, max_length=6000)
    resolution_summary: Optional[str] = Field(None, max_length=4000)


class IncidentLinkTicketRequest(BaseModel):
    ticket_id: int
    similarity_score: Optional[float] = None


# --- Resolution Intelligence & Knowledge Gaps (Phase 3) ---

class ResolutionFeedbackCreateRequest(BaseModel):
    ticket_id: int
    source_ticket_id: Optional[int] = None
    article_id: Optional[int] = None
    recommendation_type: Literal["similar_ticket", "knowledge_article"] = "similar_ticket"
    rating: Literal["helpful", "partially_helpful", "not_helpful"]
    applied_to_reply: bool = False


class KnowledgeGapDraftRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=4, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=12000)
