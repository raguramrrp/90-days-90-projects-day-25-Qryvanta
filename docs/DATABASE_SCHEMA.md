# QRYVANTA — Database Schema

QRYVANTA uses SQLAlchemy ORM with normalized relational tables, foreign key constraints (with `PRAGMA foreign_keys=ON` enforced on SQLite), unique constraints, and indexes. Alembic migrations live in `backend/migrations/`.

## Core Entity Tables

| Table | Purpose | Key Columns & Constraints |
|---|---|---|
| `users` | Authentication & RBAC accounts | `id`, `name`, `email` (UNIQUE, indexed), `password_hash`, `role` (`customer\|agent\|manager\|admin`), `is_active` |
| `customers` | Customer profile metadata | `id`, `user_id` (FK `users.id`, UNIQUE), `customer_reference` (UNIQUE), `contact_information` |
| `departments` | Support operational queues | `id`, `name` (UNIQUE), `description`, `is_active` |
| `agents` | Support specialist profiles | `id`, `user_id` (FK `users.id`, UNIQUE), `department_id` (FK), `availability_status`, `expertise`, `max_open_tickets` |
| `agent_departments` | Multi-department agent memberships | `id`, `agent_id` (FK), `department_id` (FK), UNIQUE(`agent_id`, `department_id`) |
| `categories` | Hierarchical category/subcategory taxonomy | `id`, `name`, `parent_category_id` (self FK), `description`, `is_active` |
| `tickets` | Core support ticket record | `id`, `ticket_reference` (UNIQUE), `customer_id` (FK), `subject`, `description`, `category_id`, `subcategory_id`, `priority`, `priority_reason`, `department_id`, `assigned_agent_id`, `status`, `is_demo_data`, `sentiment_*`, `reopen_count`, `satisfaction_rating` |
| `ticket_messages` | Chronological replies & internal notes | `id`, `ticket_id` (FK), `sender_id` (FK), `message`, `visibility` (`public\|internal`) |
| `ticket_assignments` | Historical assignment ledger | `id`, `ticket_id` (FK), `agent_id` (FK), `department_id` (FK), `assigned_by`, `assignment_reason`, `assigned_at`, `ended_at` |
| `ticket_events` | Immutable ticket timeline | `id`, `ticket_id` (FK), `actor_id`, `event_type`, `old_value`, `new_value`, `event_description` |
| `ticket_relations` | Staff-confirmed duplicate/related links | `id`, `source_ticket_id`, `related_ticket_id`, `relation_type` (`duplicate\|related`), `similarity_score`, `confirmed_by` |
| `ticket_attachments` | Validated uploaded file metadata | `id`, `ticket_id`, `message_id`, `original_filename`, `stored_filename`, `mime_type`, `file_size`, `storage_path` |
| `ticket_predictions` | Persisted ML predictions & routing decisions | `id`, `ticket_id`, `model_version_id`, `predicted_category_id`, `predicted_subcategory_id`, `suggested_department_id`, `final_department_id`, `confidence`, `alternative_predictions` (JSON), `explanation`, `routing_decision` |
| `ticket_feedback` | Human-in-the-loop correction records | `id`, `ticket_id`, `prediction_id`, `corrected_category_id`, `corrected_subcategory_id`, `corrected_priority`, `corrected_department_id`, `correction_reason`, `corrected_by`, `model_version_id` |
| `sla_policies` | Configurable priority/department targets | `id`, `name` (UNIQUE), `priority`, `department_id` (nullable), `first_response_minutes`, `resolution_minutes`, `business_hours_only` |
| `sla_tracking` | Per-ticket live SLA state & deadlines | `id`, `ticket_id` (UNIQUE FK), `policy_id`, `first_response_deadline`, `resolution_deadline`, `first_responded_at`, `resolved_at`, `paused_minutes`, `paused_at`, `current_state`, `escalated` |
| `knowledge_articles` | Support resolution guides | `id`, `title`, `content`, `category_id`, `tags`, `is_published` |
| `knowledge_recommendations` | Tracked KB suggestion usefulness | `id`, `ticket_id`, `article_id`, `relevance_score`, `accepted` |
| `model_versions` | Versioned ML models & evaluation metrics | `id`, `model_name`, `version` (UNIQUE), `algorithm`, `dataset_reference`, `training_date`, `evaluation_metrics` (JSON), `model_path`, `is_active` |
| `routing_rules` | Category-to-department routing config | `id`, `name` (UNIQUE), `category_id`, `department_id`, `min_confidence`, `auto_assign_agent`, `is_active` |
| `holidays` | Non-working dates excluded from SLA clocks | `id`, `holiday_date` (UNIQUE), `name` |
| `app_settings` | Configurable thresholds & business hours | `id`, `key` (UNIQUE), `value` (JSON), `description` |
| `audit_logs` | Security & administrative audit trail | `id`, `user_id`, `action`, `entity_type`, `entity_id`, `details` (JSON), `ip_address`, `created_at` |
