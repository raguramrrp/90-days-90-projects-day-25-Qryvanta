import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  CartesianGrid,
} from "recharts";
import { apiRequest } from "../services/api";
import type { IncidentSummary } from "../types";
import {
  PageHeader,
  MetricSummary,
  StatusLabel,
  PriorityIndicator,
  IncidentStatusBadge,
  LoadingSkeleton,
  ErrorState,
  formatMinutes,
} from "../components/UI";

interface OverviewResponse {
  metrics: {
    total_tickets: number;
    open_tickets: number;
    unassigned_tickets: number;
    critical_and_high_open: number;
    overdue_tickets: number;
    high_sla_risk_open?: number;
    avg_first_response_minutes: number | null;
    avg_resolution_minutes: number | null;
    sla_compliance_rate: number | null;
    sla_completed_eligible: number;
    sla_completed_within_target: number;
  };
  attention_required?: {
    kind: string;
    severity: string;
    title: string;
    detail: string;
    link: string;
  }[];
  incident_summary?: {
    active_incidents: number;
    newly_detected: number;
    unique_affected_customers: number;
    most_reported: IncidentSummary | null;
    recent_active: IncidentSummary[];
  };
  operational_insights?: string[];
  volume_over_time: { date: string; created: number; resolved: number }[];
  by_department: { name: string; count: number }[];
  recent_tickets: {
    id: number;
    ticket_reference: string;
    subject: string;
    priority: string;
    status: string;
    category_name: string;
    department_name: string;
    created_at: string;
    is_demo_data: boolean;
  }[];
  low_confidence_tickets: {
    id: number;
    ticket_reference: string;
    subject: string;
    predicted_category: string | null;
    confidence: number;
    routing_decision: string | null;
  }[];
  has_demo_data: boolean;
}

export function OverviewPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["analytics-overview"],
    queryFn: () => apiRequest<OverviewResponse>("/api/analytics/overview"),
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load operations overview."}
        onRetry={() => refetch()}
      />
    );
  }

  const m = data.metrics;
  const incSum = data.incident_summary;
  const attention = data.attention_required || [];
  const insights = data.operational_insights || [];

  return (
    <div>
      <PageHeader
        title="Operations Overview"
        subtitle="Prioritized operational picture: what needs attention now, active multi-customer incidents, and live SLA performance."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {data.has_demo_data && (
              <span className="px-2.5 py-1 text-[11.5px] rounded border border-[#E3E7E4] bg-white text-[#78817D]">
                Includes seeded demo records
              </span>
            )}
            <Link to="/operations" className="btn-secondary">
              Risk & workload
            </Link>
            <Link to="/incidents" className="btn-primary">
              Incident Centre
            </Link>
          </div>
        }
      />

      {/* Core KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <MetricSummary label="Open tickets" value={m.open_tickets} sublabel={`${m.total_tickets} total recorded`} tone="accent" />
        <MetricSummary
          label="Unassigned open"
          value={m.unassigned_tickets}
          tone={m.unassigned_tickets > 0 ? "warning" : "default"}
        />
        <MetricSummary
          label="High / critical SLA risk"
          value={m.high_sla_risk_open ?? m.overdue_tickets}
          sublabel={`${m.overdue_tickets} currently overdue`}
          tone={(m.high_sla_risk_open ?? m.overdue_tickets) > 0 ? "critical" : "default"}
        />
        <MetricSummary
          label="SLA compliance"
          value={m.sla_compliance_rate !== null ? `${m.sla_compliance_rate}%` : "N/A"}
          sublabel={`Avg res ${formatMinutes(m.avg_resolution_minutes)} · FRT ${formatMinutes(m.avg_first_response_minutes)}`}
          tone="accent"
        />
      </div>

      {/* Section 1 & 2: Attention Required + Incident Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-6">
        <div className="lg:col-span-7 surface-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#E6EBE8] bg-[#FAFBF9] flex items-center justify-between">
            <h2 className="text-[14px] font-semibold text-[#1D2825]">
              Attention Required Now
            </h2>
            <Link to="/operations" className="text-[12.5px] font-medium text-[#2F6354] hover:underline">
              Full risk &amp; workload view
            </Link>
          </div>
          <div className="divide-y divide-[#E6EBE8]">
            {attention.length === 0 ? (
              <div className="py-8 px-5 text-center text-[13.5px] text-[#6E7C77]">
                No critical incidents, unassigned urgent tickets, or imminent SLA breaches right now.
              </div>
            ) : (
              attention.map((item, idx) => (
                <Link
                  key={idx}
                  to={item.link}
                  className="group block px-5 py-3.5 hover:bg-[#F7FAF8] transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[13.5px] font-medium text-[#1D2825] group-hover:text-[#2F6354] transition-colors truncate">
                      {item.title}
                    </span>
                    <PriorityIndicator priority={item.severity} />
                  </div>
                  <div className="text-[12px] text-[#6E7C77] mt-0.5">{item.detail}</div>
                </Link>
              ))
            )}
          </div>
        </div>

        <div className="lg:col-span-5 space-y-5">
          {/* Incident Summary */}
          <div className="surface-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#E6EBE8] bg-[#FAFBF9] flex items-center justify-between">
              <h2 className="text-[14px] font-semibold text-[#1D2825]">Incident Summary</h2>
              <Link to="/incidents" className="text-[12.5px] font-medium text-[#2F6354] hover:underline">
                Manage incidents
              </Link>
            </div>
            <div className="p-5 space-y-3.5">
              <div className="grid grid-cols-3 gap-2.5 text-center bg-[#F8FAF9] border border-[#E4EAE6] rounded-[8px] p-3">
                <div>
                  <div className="text-[20px] font-bold text-[#1D2825] tabular-nums">
                    {incSum?.active_incidents ?? 0}
                  </div>
                  <div className="text-[11px] font-medium text-[#6E7C77] mt-0.5">Active</div>
                </div>
                <div>
                  <div className="text-[20px] font-bold text-[#B03E3E] tabular-nums">
                    {incSum?.unique_affected_customers ?? 0}
                  </div>
                  <div className="text-[11px] font-medium text-[#6E7C77] mt-0.5">Affected customers</div>
                </div>
                <div>
                  <div className="text-[20px] font-bold text-[#A96F1F] tabular-nums">
                    {incSum?.newly_detected ?? 0}
                  </div>
                  <div className="text-[11px] font-medium text-[#6E7C77] mt-0.5">New clusters</div>
                </div>
              </div>
              {incSum?.most_reported ? (
                <Link
                  to="/incidents"
                  className="block border border-[#E1E6E3] rounded-[8px] p-3.5 hover:border-[#B6C8C0] hover:bg-[#F8FAF9] transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[11.5px] text-[#2F6354] font-semibold">
                      Most reported · {incSum.most_reported.incident_reference}
                    </span>
                    <IncidentStatusBadge status={incSum.most_reported.status} />
                  </div>
                  <div className="text-[13.5px] font-semibold text-[#1D2825] mt-1.5">
                    {incSum.most_reported.title}
                  </div>
                  <div className="text-[12px] text-[#6E7C77] mt-0.5">
                    {incSum.most_reported.ticket_count} tickets from{" "}
                    <strong className="text-[#1D2825]">{incSum.most_reported.affected_customer_count}</strong> unique customers
                  </div>
                </Link>
              ) : (
                <div className="text-[12.5px] text-[#6E7C77] py-2">No active incident clusters detected.</div>
              )}
            </div>
          </div>

          {/* Section 3: Data-Backed Operational Insights */}
          <div className="surface-card p-4">
            <h2 className="text-[13.5px] font-semibold text-[#222C2A] mb-2">
              Operational Insights (Live Database Summary)
            </h2>
            {insights.length === 0 ? (
              <div className="text-[12.5px] text-[#78817D]">Not enough ticket records yet for operational observations.</div>
            ) : (
              <ul className="space-y-1.5 text-[12.5px] text-[#222C2A] list-disc pl-4">
                {insights.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Primary Charts Row (Secondary distributions live cleanly in Analytics) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-5">
        <div className="lg:col-span-7 surface-card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[13.5px] font-semibold text-[#222C2A]">
              Ticket volume & resolution trend
            </span>
            <Link to="/analytics" className="text-[12px] text-[#38685A] hover:underline">
              All charts in Analytics
            </Link>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.volume_over_time}>
                <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#78817D" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="created"
                  name="Created"
                  stroke="#38685A"
                  fill="#38685A"
                  fillOpacity={0.14}
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="resolved"
                  name="Resolved"
                  stroke="#8AA397"
                  fill="#8AA397"
                  fillOpacity={0.14}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-5 surface-card p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[13.5px] font-semibold text-[#222C2A]">
              Department workload distribution
            </span>
            <Link to="/departments" className="text-[12px] text-[#38685A] hover:underline">
              Departments
            </Link>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_department} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11, fill: "#222C2A" }} />
                <Tooltip />
                <Bar dataKey="count" name="Tickets" fill="#38685A" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Tickets & Low-Confidence Triage */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] flex items-center justify-between">
            <h2 className="text-[13.5px] font-semibold text-[#222C2A]">Recent tickets</h2>
            <Link to="/tickets" className="text-[12px] text-[#38685A] hover:underline">
              Open full queue
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="table-header">
                  <th className="py-2 px-3">ID</th>
                  <th className="py-2 px-3">Subject</th>
                  <th className="py-2 px-3">Department</th>
                  <th className="py-2 px-3">Priority</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4] text-[13px]">
                {data.recent_tickets.map((t) => (
                  <tr key={t.id} className="hover:bg-[#FAFBF9]">
                    <td className="py-2 px-3 font-mono text-[12px]">
                      <Link to={`/tickets/${t.id}`} className="text-[#38685A] hover:underline">
                        {t.ticket_reference}
                      </Link>
                    </td>
                    <td className="py-2 px-3 max-w-xs truncate">{t.subject}</td>
                    <td className="py-2 px-3 text-[#78817D]">{t.department_name}</td>
                    <td className="py-2 px-3">
                      <PriorityIndicator priority={t.priority} />
                    </td>
                    <td className="py-2 px-3">
                      <StatusLabel status={t.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-4 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] flex items-center justify-between">
            <h2 className="text-[13.5px] font-semibold text-[#222C2A]">Low-confidence review</h2>
            <Link to="/intelligence" className="text-[12px] text-[#38685A] hover:underline">
              Intelligence
            </Link>
          </div>
          <div className="divide-y divide-[#E3E7E4]">
            {data.low_confidence_tickets.length === 0 ? (
              <div className="py-6 px-4 text-center text-[13px] text-[#78817D]">
                No open low-confidence tickets awaiting triage.
              </div>
            ) : (
              data.low_confidence_tickets.slice(0, 6).map((t) => (
                <Link
                  key={t.id}
                  to={`/tickets/${t.id}`}
                  className="block px-4 py-2.5 hover:bg-[#FAFBF9]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[12px] text-[#38685A]">{t.ticket_reference}</span>
                    <span className="text-[12px] font-medium text-[#C08A3E]">
                      {(t.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="text-[12.5px] text-[#222C2A] truncate mt-0.5">{t.subject}</div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
