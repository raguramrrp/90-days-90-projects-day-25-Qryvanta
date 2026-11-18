export type UserRole = "customer" | "agent" | "manager" | "admin";

export interface UserProfile {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  customer_id?: number | null;
  customer_reference?: string | null;
  contact_information?: string | null;
  agent_id?: number | null;
  department_id?: number | null;
  department_name?: string | null;
  availability_status?: string | null;
  created_at?: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface CategoryItem {
  id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  subcategories: {
    id: number;
    name: string;
    parent_category_id: number;
    description?: string | null;
    is_active: boolean;
  }[];
}

export interface CompanyItem {
  id: number;
  name: string;
  platform_type: string;
  portal_url?: string | null;
  support_email?: string | null;
  description?: string | null;
  is_active: boolean;
  total_tickets?: number;
  open_tickets?: number;
  verified_tickets?: number;
  reported_tickets?: number;
  resolved_tickets?: number;
  verification_rate?: number;
}

export interface TicketSummary {
  id: number;
  ticket_reference: string;
  subject: string;
  description: string;
  product_reference?: string | null;
  company_id?: number | null;
  company_name?: string | null;
  platform_type?: string | null;
  external_reference?: string | null;
  verification_status?: string;
  company_case_reference?: string | null;
  status: string;
  has_assigned_support?: boolean;
  priority: "critical" | "high" | "medium" | "low";
  source: string;
  is_demo_data: boolean;
  category_id?: number | null;
  category_name?: string | null;
  subcategory_id?: number | null;
  subcategory_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  customer?: {
    id: number;
    customer_reference: string;
    name: string;
    email: string;
    contact_information?: string | null;
  } | null;
  assigned_agent?: {
    id: number;
    name: string;
    email: string;
  } | null;
  sla_state: string;
  sla_breached: boolean;
  resolution_deadline?: string | null;
  reopen_count: number;
  satisfaction_rating?: number | null;
  satisfaction_comment?: string | null;
  priority_reason?: string | null;
  sentiment?: {
    label?: string | null;
    confidence?: number | null;
    method?: string | null;
  };
  prediction_confidence?: number | null;
  routing_decision?: string | null;
  sla_risk_level?: "critical" | "high" | "moderate" | "low" | null;
  sla_risk_score?: number | null;
  linked_incidents?: { id: number; incident_reference: string; status: string }[];
  created_at: string;
  updated_at?: string | null;
  resolved_at?: string | null;
  reopened_at?: string | null;
}

export interface TicketDetail extends TicketSummary {
  reopen_reason?: string | null;
  company?: {
    id: number;
    name: string;
    platform_type: string;
    portal_url?: string | null;
    support_email?: string | null;
  } | null;
  verification?: {
    status: string;
    notes?: string | null;
    recommended_company_action?: string | null;
    verified_by_name?: string | null;
    verified_at?: string | null;
    reported_to_company_at?: string | null;
    company_case_reference?: string | null;
  };
  messages: {
    id: number;
    sender_id?: number | null;
    sender_name: string;
    sender_role: string;
    message: string;
    visibility: "public" | "internal";
    created_at: string;
  }[];
  attachments: {
    id: number;
    original_filename: string;
    mime_type: string;
    file_size: number;
    uploaded_by?: string | null;
    created_at: string;
  }[];
  events: {
    id: number;
    event_type: string;
    actor_name: string;
    old_value?: string | null;
    new_value?: string | null;
    event_description: string;
    created_at: string;
  }[];
  sla?: {
    policy_id?: number | null;
    policy_name?: string | null;
    first_response_deadline?: string;
    resolution_deadline?: string;
    first_responded_at?: string | null;
    resolved_at?: string | null;
    paused_minutes?: number;
    current_state: string;
    time_remaining_minutes?: number;
    first_response_time_minutes?: number | null;
    resolution_time_minutes?: number | null;
    sla_breached?: boolean;
    escalated?: boolean;
    escalated_at?: string | null;
    escalation_notes?: string | null;
  };
  prediction?: {
    id: number;
    model_version_id?: number | null;
    model_version: string;
    predicted_category_id?: number | null;
    predicted_category_name?: string | null;
    predicted_subcategory_id?: number | null;
    predicted_subcategory_name?: string | null;
    suggested_department_id?: number | null;
    suggested_department_name?: string | null;
    final_department_id?: number | null;
    final_department_name?: string | null;
    suggested_priority?: string | null;
    confidence: number;
    alternative_predictions: { category: string; confidence: number }[];
    explanation?: string | null;
    routing_rule_applied?: string | null;
    routing_decision?: string | null;
    override_reason?: string | null;
    created_at: string;
  } | null;
  feedback_history?: {
    id: number;
    corrected_category_name?: string | null;
    corrected_subcategory_name?: string | null;
    corrected_priority?: string | null;
    corrected_department_name?: string | null;
    correction_reason: string;
    corrected_by_name?: string | null;
    created_at: string;
  }[];
  sentiment_trend?: {
    trend: string;
    points: { label: string; confidence: number; method: string; note: string }[];
  };
  recommended_agents?: AgentRecommendation[];
  knowledge_recommendations?: {
    recommendation_id?: number | null;
    article_id: number;
    title: string;
    content: string;
    category_name?: string | null;
    tags?: string | null;
    relevance_score: number;
    accepted?: boolean | null;
  }[];
  confirmed_relations?: {
    id: number;
    relation_type: string;
    similarity_score?: number | null;
    other_ticket_id: number;
    other_ticket_reference: string;
    other_ticket_subject: string;
    other_ticket_status: string;
    confirmed_by?: string | null;
    created_at: string;
  }[];
  sla_risk?: {
    risk_level: "critical" | "high" | "moderate" | "low";
    risk_score: number;
    method: string;
    sla_state: string;
    remaining_sla_minutes?: number | null;
    factors: string[];
    recommended_action: string;
  };
  customer_impact?: {
    unique_affected_customers: number;
    related_problem_ticket_count: number;
    related_incident_count: number;
    linked_incidents: {
      id: number;
      incident_reference: string;
      title: string;
      status: string;
      severity: string;
      ticket_count: number;
      affected_customer_count: number;
    }[];
    customer_total_tickets: number;
    customer_unresolved_tickets: number;
    customer_repeat_complaints_same_category: number;
    customer_prior_history: {
      id: number;
      ticket_reference: string;
      subject: string;
      status: string;
      category_name?: string | null;
      created_at?: string | null;
    }[];
    summary_note: string;
  };
}

export interface IncidentSummary {
  id: number;
  incident_reference: string;
  title: string;
  description?: string | null;
  severity: "critical" | "high" | "medium" | "low";
  status: string;
  department_id?: number | null;
  department_name?: string | null;
  owner_id?: number | null;
  owner_name?: string | null;
  common_symptoms: string[];
  ticket_count: number;
  open_ticket_count: number;
  affected_customer_count: number;
  is_auto_detected: boolean;
  is_demo_data: boolean;
  first_reported_at?: string | null;
  last_reported_at?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  investigation_notes?: string | null;
  resolution_summary?: string | null;
  customer_impact: {
    total_linked_tickets: number;
    unique_affected_customers: number;
    repeat_complaint_customers: number;
    clarification: string;
  };
  tickets: {
    link_id: number;
    ticket_id: number;
    ticket_reference: string;
    subject: string;
    status: string;
    priority: string;
    customer_id: number;
    customer_name: string;
    company_name?: string | null;
    category_name?: string | null;
    similarity_score?: number | null;
    created_at?: string | null;
  }[];
  events: {
    id: number;
    event_type: string;
    actor_name: string;
    old_value?: string | null;
    new_value?: string | null;
    description: string;
    created_at?: string | null;
  }[];
}

export interface AgentRecommendation {
  agent_id: number;
  user_id: number;
  name: string;
  email: string;
  department_id?: number | null;
  department_name?: string | null;
  availability_status: string;
  expertise?: string | null;
  open_ticket_count: number;
  max_open_tickets: number;
  utilization_pct: number;
  reason: string;
  method: string;
}

export interface DepartmentMetrics {
  department_id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  agent_count: number;
  total_tickets: number;
  open_tickets: number;
  unassigned_tickets: number;
  avg_resolution_minutes?: number | null;
  sla_compliance_rate?: number | null;
  escalation_rate: number;
  reassignment_rate: number;
  reopen_rate: number;
}

export interface AgentMetrics {
  agent_id: number;
  user_id: number;
  name: string;
  email: string;
  is_active: boolean;
  department_id?: number | null;
  department_name?: string | null;
  availability_status: string;
  expertise?: string | null;
  max_open_tickets: number;
  open_tickets: number;
  utilization_pct: number;
  total_assigned: number;
  resolved_tickets: number;
  high_priority_tickets: number;
  avg_first_response_minutes?: number | null;
  avg_resolution_minutes?: number | null;
  sla_compliance_rate?: number | null;
  avg_satisfaction?: number | null;
}

export interface ModelVersionRecord {
  id: number;
  model_name: string;
  version: string;
  algorithm: string;
  dataset_reference: string;
  training_date: string;
  evaluation_metrics: {
    accuracy?: number;
    macro_precision?: number;
    macro_recall?: number;
    macro_f1?: number;
    weighted_precision?: number;
    weighted_recall?: number;
    weighted_f1?: number;
    subcategory_test_accuracy?: number | null;
    train_samples?: number;
    test_samples?: number;
    duplicates_removed_before_split?: number;
    split_strategy?: string;
    labels?: string[];
    confusion_matrix?: number[][];
    warnings?: string[];
    per_category?: {
      category: string;
      precision: number;
      recall: number;
      f1: number;
      train_support: number;
      test_support: number;
      insufficient_data: boolean;
    }[];
  };
  model_path?: string | null;
  artifact_exists: boolean;
  is_active: boolean;
  created_at: string;
}
