import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { AgentRecommendation } from "../types";
import {
  PageHeader,
  MetricSummary,
  PriorityIndicator,
  RiskBadge,
  SLAIndicator,
  LoadingSkeleton,
  ErrorState,
  formatMinutes,
} from "../components/UI";

interface AgentCapCard {
  agent_id: number;
  name: string;
  email: string;
  department_name: string;
  availability_status: string;
  open_tickets: number;
  max_open_tickets: number;
  utilization_pct: number;
  avg_resolution_minutes: number | null;
  resolved_sample_size: number;
}

interface OperationsOverview {
  risk_method: string;
  risk_summary: { critical: number; high: number; moderate: number; low: number };
  at_risk_tickets: {
    id: number;
    ticket_reference: string;
    subject: string;
    priority: string;
    department_name: string;
    assigned_agent_name: string | null;
    risk_level: string;
    risk_score: number;
    sla_state: string;
    remaining_sla_minutes: number | null;
    factors: string[];
    recommended_action: string;
  }[];
  unassigned_high_priority: {
    id: number;
    ticket_reference: string;
    subject: string;
    priority: string;
    department_name: string;
    category_name: string;
    risk_level: string;
    remaining_sla_minutes: number | null;
    recommended_agents: AgentRecommendation[];
  }[];
  agent_capacity: {
    available: AgentCapCard[];
    nearing_capacity: AgentCapCard[];
    overloaded: AgentCapCard[];
  };
  department_backlogs: {
    department_id: number;
    name: string;
    open_tickets: number;
    unassigned_tickets: number;
    created_last_7d: number;
    resolved_last_7d: number;
    net_backlog_delta_7d: number;
    is_growing: boolean;
  }[];
  manager_actions: {
    severity: string;
    title: string;
    detail: string;
    target_path: string;
  }[];
}

export function OperationsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const canAssign = user?.role === "manager" || user?.role === "admin" || user?.role === "agent";

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["operations-overview"],
    queryFn: () => apiRequest<OperationsOverview>("/api/operations/overview"),
  });

  const approveAssignMutation = useMutation({
    mutationFn: ({ ticketId, agentId, reason }: { ticketId: number; agentId: number; reason: string }) =>
      apiRequest(`/api/tickets/${ticketId}/assign`, {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, reason }),
      }),
    onSuccess: () => {
      notify("Assignment recommendation approved and applied.", "success");
      qc.invalidateQueries({ queryKey: ["operations-overview"] });
      qc.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Assignment failed.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) return <ErrorState message="Failed to load Risk & Workload view." onRetry={() => refetch()} />;

  return (
    <div>
      <PageHeader
        title="Risk & Workload Operations"
        subtitle="Deterministic SLA breach risk analysis, agent capacity distribution, department backlogs, and explainable assignment recommendations."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/departments" className="btn-secondary">
              Departments
            </Link>
            <Link to="/agents" className="btn-secondary">
              Manage agents
            </Link>
            <Link to="/tickets?preset=high_risk" className="btn-primary">
              High-risk queue
            </Link>
          </div>
        }
      />

      {/* Risk KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <MetricSummary
          label="Critical SLA risk"
          value={data.risk_summary.critical}
          tone={data.risk_summary.critical > 0 ? "critical" : "default"}
          sublabel="Rule-based risk score >= 75"
        />
        <MetricSummary
          label="High SLA risk"
          value={data.risk_summary.high}
          tone={data.risk_summary.high > 0 ? "warning" : "default"}
          sublabel="Rule-based risk score 50–74"
        />
        <MetricSummary
          label="Unassigned critical/high"
          value={data.unassigned_high_priority.length}
          tone={data.unassigned_high_priority.length > 0 ? "critical" : "default"}
        />
        <MetricSummary
          label="Overloaded agents"
          value={data.agent_capacity.overloaded.length}
          sublabel={`${data.agent_capacity.nearing_capacity.length} nearing capacity · ${data.agent_capacity.available.length} available`}
          tone={data.agent_capacity.overloaded.length > 0 ? "warning" : "accent"}
        />
      </div>

      {/* Manager Recommended Actions */}
      {data.manager_actions.length > 0 && (
        <div className="surface-card p-4 mb-5 border-[#E8D7BC] bg-[#FBF8F1] space-y-2">
          <div className="text-[13px] font-semibold text-[#222C2A]">Recommended Operational Actions</div>
          {data.manager_actions.map((act, i) => (
            <div key={i} className="flex flex-wrap items-center justify-between gap-2 text-[12.5px] border-t border-[#E8D7BC]/60 pt-2 first:border-t-0 first:pt-0">
              <div>
                <span className="font-medium text-[#222C2A]">{act.title}</span>
                <span className="text-[#78817D] ml-2">{act.detail}</span>
              </div>
              <Link to={act.target_path} className="text-[12px] text-[#38685A] font-medium hover:underline">
                Review &rarr;
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* Unassigned High-Priority Tickets + Explainable Recommendations */}
      <div className="surface-card overflow-hidden mb-5">
        <div className="px-4 py-3 border-b border-[#E3E7E4] flex items-center justify-between">
          <div>
            <h2 className="text-[13.5px] font-semibold text-[#222C2A]">
              Unassigned High-Priority Tickets & Assignment Recommendations
            </h2>
            <p className="text-[12px] text-[#78817D]">
              Recommendations use department fit, availability, open workload vs. capacity, and expertise. Managers explicitly approve before assignment.
            </p>
          </div>
        </div>
        {data.unassigned_high_priority.length === 0 ? (
          <div className="p-6 text-center text-[13px] text-[#78817D]">
            All critical and high-priority open tickets currently have an assigned agent.
          </div>
        ) : (
          <div className="divide-y divide-[#E3E7E4]">
            {data.unassigned_high_priority.map((t) => {
              const topRec = t.recommended_agents[0];
              return (
                <div key={t.id} className="p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link to={`/tickets/${t.id}`} className="font-mono text-[12px] text-[#38685A] font-semibold hover:underline">
                        {t.ticket_reference}
                      </Link>
                      <PriorityIndicator priority={t.priority} />
                      <RiskBadge level={t.risk_level} />
                      <span className="text-[12px] text-[#78817D]">
                        {t.department_name} · Remaining: {formatMinutes(t.remaining_sla_minutes)}
                      </span>
                    </div>
                    <div className="text-[13.5px] font-medium text-[#222C2A] mt-0.5">{t.subject}</div>
                    {topRec ? (
                      <div className="text-[12px] text-[#78817D] mt-1">
                        <strong className="text-[#38685A]">Suggested: {topRec.name}</strong> — {topRec.reason}
                      </div>
                    ) : (
                      <div className="text-[12px] text-[#78817D] mt-1">
                        No available department specialist found under capacity limits.
                      </div>
                    )}
                  </div>
                  {canAssign && topRec && (
                    <button
                      className="btn-primary shrink-0"
                      disabled={approveAssignMutation.isPending}
                      onClick={() =>
                        approveAssignMutation.mutate({
                          ticketId: t.id,
                          agentId: topRec.agent_id,
                          reason: topRec.reason,
                        })
                      }
                    >
                      Approve & assign {topRec.name.split(" ")[0]}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Agent Capacity & Department Backlogs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-5">
        <div className="lg:col-span-7 surface-card p-4 space-y-3">
          <div className="text-[13.5px] font-semibold text-[#222C2A]">
            Team Workload & Capacity Bands
          </div>
          {(["overloaded", "nearing_capacity", "available"] as const).map((band) => {
            const list = data.agent_capacity[band];
            const label =
              band === "overloaded"
                ? "Overloaded (>= 100% capacity)"
                : band === "nearing_capacity"
                ? "Nearing capacity (75–99%)"
                : "Available capacity (< 75%)";
            const tone =
              band === "overloaded" ? "text-[#B84C4C]" : band === "nearing_capacity" ? "text-[#C08A3E]" : "text-[#38685A]";
            return (
              <div key={band} className="border-t border-[#E3E7E4] pt-2.5 first:border-t-0 first:pt-0">
                <div className={`text-[12px] font-semibold mb-1.5 ${tone}`}>
                  {label} ({list.length})
                </div>
                {list.length === 0 ? (
                  <div className="text-[12px] text-[#78817D]">None in this band.</div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {list.map((ag) => (
                      <div key={ag.agent_id} className="border border-[#E3E7E4] rounded p-2.5 text-[12px]">
                        <div className="flex justify-between font-medium text-[#222C2A]">
                          <span>{ag.name}</span>
                          <span>
                            {ag.open_tickets}/{ag.max_open_tickets} ({ag.utilization_pct}%)
                          </span>
                        </div>
                        <div className="text-[#78817D] mt-0.5">
                          {ag.department_name} · {ag.availability_status} · Avg res: {formatMinutes(ag.avg_resolution_minutes)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="lg:col-span-5 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Department Backlog Momentum (7 Days)
          </div>
          <table className="w-full text-left border-collapse text-[12.5px]">
            <thead>
              <tr className="table-header">
                <th className="py-2 px-3">Department</th>
                <th className="py-2 px-2">Open</th>
                <th className="py-2 px-2">Unassigned</th>
                <th className="py-2 px-3 text-right">7d Net</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7E4]">
              {data.department_backlogs.map((d) => (
                <tr key={d.department_id}>
                  <td className="py-2 px-3 font-medium">
                    <Link to={`/tickets?department_id=${d.department_id}`} className="hover:text-[#38685A] hover:underline">
                      {d.name}
                    </Link>
                  </td>
                  <td className="py-2 px-2">{d.open_tickets}</td>
                  <td className="py-2 px-2 text-[#C08A3E]">{d.unassigned_tickets}</td>
                  <td className={`py-2 px-3 text-right font-medium ${d.is_growing ? "text-[#B84C4C]" : "text-[#38685A]"}`}>
                    {d.net_backlog_delta_7d > 0 ? `+${d.net_backlog_delta_7d}` : d.net_backlog_delta_7d}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Highest SLA Breach Risk Table */}
      <div className="surface-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[#E3E7E4] flex items-center justify-between">
          <span className="text-[13.5px] font-semibold">
            Tickets at High & Critical SLA Breach Risk (Deterministic Risk Rules)
          </span>
          <span className="text-[11.5px] text-[#78817D]">Method: {data.risk_method.replace(/_/g, " ")}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-[12.5px]">
            <thead>
              <tr className="table-header">
                <th className="py-2 px-3">Ticket</th>
                <th className="py-2 px-3">Subject</th>
                <th className="py-2 px-3">Risk</th>
                <th className="py-2 px-3">SLA Status</th>
                <th className="py-2 px-3">Primary Risk Factor</th>
                <th className="py-2 px-3">Recommended Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7E4]">
              {data.at_risk_tickets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-[#78817D]">
                    No open tickets currently flagged at High or Critical SLA risk.
                  </td>
                </tr>
              ) : (
                data.at_risk_tickets.map((t) => (
                  <tr key={t.id} className="hover:bg-[#FAFBF9]">
                    <td className="py-2.5 px-3 font-mono text-[12px] whitespace-nowrap">
                      <Link to={`/tickets/${t.id}`} className="text-[#38685A] hover:underline">
                        {t.ticket_reference}
                      </Link>
                    </td>
                    <td className="py-2.5 px-3 max-w-[220px] truncate">{t.subject}</td>
                    <td className="py-2.5 px-3">
                      <RiskBadge level={t.risk_level} />
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <SLAIndicator state={t.sla_state} /> ({formatMinutes(t.remaining_sla_minutes)})
                    </td>
                    <td className="py-2.5 px-3 text-[#78817D] max-w-xs">{t.factors[0]}</td>
                    <td className="py-2.5 px-3 text-[#222C2A] max-w-xs">{t.recommended_action}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
