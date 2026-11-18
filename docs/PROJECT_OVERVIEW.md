# QRYVANTA — Project Overview

## Problem Statement

Growing software, e-commerce, and operations teams frequently struggle with unstructured customer support queues. Incoming requests arrive without consistent categorization, urgency signals are conflated with angry tone, duplicate incidents consume duplicate agent effort, and service-level agreement (SLA) deadlines are missed because calendars ignore business hours and holidays.

## Goals & Objectives

QRYVANTA (**Intelligent Customer Support Operations & Ticket Resolution Platform**) addresses these bottlenecks through six integrated functional layers:

1. **Customer Interaction**: Validated ticket submission, attachments, chronological replies, reopening, and satisfaction ratings.
2. **Ticket Operations**: Role-scoped queues, department queues, agent assignments, status tracking, and CSV import/export.
3. **Operational Intelligence**: Hierarchical TF-IDF + Logistic Regression classification, separate rule-based urgency assessment, TF-IDF cosine similarity duplicate detection, rule-based sentiment context, and knowledge article suggestions.
4. **Workflow Automation**: Confidence-threshold routing (high auto-route, medium suggested review, low manual triage), workload-aware agent recommendations, and business-hours/holiday SLA tracking.
5. **Analytics & Business Intelligence**: Database-calculated operational, department, customer experience, and classification metrics with documented formulas.
6. **Administration & Governance**: Role-based access control (Customer, Support Agent, Support Manager, Administrator), configurable taxonomy, controlled model retraining, and audit logs.

## Intended Users

- **Customer**: Submits requests, uploads permitted attachments, tracks only their own tickets, replies, reopens eligible tickets, and rates resolutions.
- **Support Agent**: Works assigned and authorized department queues, writes public replies and private internal notes, reviews ML predictions, submits classification corrections with reasons, and inspects similar tickets and KB guides.
- **Support Manager**: Monitors SLA compliance and department backlog, assigns/reassigns agents, overrides routing, reviews low-confidence predictions, manages bulk CSV imports, and analyzes team metrics.
- **Administrator**: Manages users, departments, categories, subcategories, routing rules, SLA policies, holidays, controlled model retraining/activation, and audit trails.

## Scope & MVP Boundaries

- Runs fully locally without paid APIs or external SaaS dependencies.
- Supports PostgreSQL as the primary relational database and SQLite as a frictionless local development fallback.
- Classification, priority, and agent assignment outputs are explicitly surfaced as **decision-support recommendations** requiring human oversight where appropriate.
