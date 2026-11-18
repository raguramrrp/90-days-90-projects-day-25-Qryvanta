import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { DepartmentMetrics, IncidentDetail, IncidentSummary } from "../types";
import {
  PageHeader,
  MetricSummary,
  PriorityIndicator,
  IncidentStatusBadge,
  StatusLabel,
  LoadingSkeleton,
  ErrorState,
  EmptyState,
  formatShortDate,
} from "../components/UI";

interface IncidentsListResponse {
  items: IncidentSummary[];
  summary: {
    active_incidents: number;
    newly_detected: number;
    confirmed_or_investigating: number;
    unique_affected_customers_active: number;
  };
}

export function IncidentsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const isManagerOrAdmin = user?.role === "manager" || user?.role === "admin";

  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Create incident modal
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newSev, setNewSev] = useState<"critical" | "high" | "medium" | "low">("high");
  const [newDeptId, setNewDeptId] = useState("");

  // Investigation edit state
  const [notesInput, setNotesInput] = useState("");
  const [resSummaryInput, setResSummaryInput] = useState("");
  const [linkTicketId, setLinkTicketId] = useState("");

  const qs = new URLSearchParams();
  if (statusFilter) qs.set("status", statusFilter);
  if (severityFilter) qs.set("severity", severityFilter);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["incidents", qs.toString()],
    queryFn: () => apiRequest<IncidentsListResponse>(`/api/incidents?${qs.toString()}`),
  });

  const activeSelectionId = selectedId ?? data?.items[0]?.id ?? null;

  const { data: detail, isLoading: loadingDetail } = useQuery({
    queryKey: ["incident-detail", activeSelectionId],
    queryFn: () => apiRequest<IncidentDetail>(`/api/incidents/${activeSelectionId}`),
    enabled: Boolean(activeSelectionId),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
  });

  React.useEffect(() => {
    if (detail) {
      setNotesInput(detail.investigation_notes || "");
      setResSummaryInput(detail.resolution_summary || "");
    }
  }, [detail?.id, detail?.investigation_notes, detail?.resolution_summary]);

  const detectMutation = useMutation({
    mutationFn: () =>
      apiRequest<{ detected_count: number; scanned_tickets: number }>("/api/incidents/detect", {
        method: "POST",
        body: JSON.stringify({ window_days: 14, similarity_threshold: 0.25, min_cluster_size: 3 }),
      }),
    onSuccess: (res) => {
      notify(
        res.detected_count > 0
          ? `Detected ${res.detected_count} new candidate incident cluster(s) from ${res.scanned_tickets} open tickets.`
          : `Scanned ${res.scanned_tickets} open tickets — no new ungrouped incident clusters detected.`,
        res.detected_count > 0 ? "success" : "info"
      );
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Detection failed.", "error"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiRequest<IncidentDetail>("/api/incidents", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle,
          description: newDesc || null,
          severity: newSev,
          department_id: newDeptId ? Number(newDeptId) : null,
        }),
      }),
    onSuccess: (created) => {
      notify(`Created incident ${created.incident_reference}.`, "success");
      setCreateOpen(false);
      setNewTitle("");
      setNewDesc("");
      setSelectedId(created.id);
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create incident.", "error"),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiRequest<IncidentDetail>(`/api/incidents/${activeSelectionId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      notify("Incident updated.", "success");
      qc.invalidateQueries({ queryKey: ["incidents"] });
      qc.invalidateQueries({ queryKey: ["incident-detail", activeSelectionId] });
      qc.invalidateQueries({ queryKey: ["analytics-overview"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Update failed.", "error"),
  });

  const linkMutation = useMutation({
    mutationFn: (tid: number) =>
      apiRequest(`/api/incidents/${activeSelectionId}/tickets`, {
        method: "POST",
        body: JSON.stringify({ ticket_id: tid }),
      }),
    onSuccess: () => {
      setLinkTicketId("");
      notify("Ticket linked to incident.", "success");
      qc.invalidateQueries({ queryKey: ["incidents"] });
      qc.invalidateQueries({ queryKey: ["incident-detail", activeSelectionId] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Unable to link ticket.", "error"),
  });

  const unlinkMutation = useMutation({
    mutationFn: (tid: number) =>
      apiRequest(`/api/incidents/${activeSelectionId}/tickets/${tid}`, { method: "DELETE" }),
    onSuccess: () => {
      notify("Ticket unlinked from incident.", "info");
      qc.invalidateQueries({ queryKey: ["incidents"] });
      qc.invalidateQueries({ queryKey: ["incident-detail", activeSelectionId] });
    },
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) {
    return <ErrorState message="Failed to load Incident Centre." onRetry={() => refetch()} />;
  }

  return (
    <div>
      <PageHeader
        title="Incident Centre"
        subtitle="Automatically group semantically similar tickets into emerging incidents, track unique affected customers, and coordinate investigation."
        actions={
          isManagerOrAdmin && (
            <div className="flex flex-wrap gap-2">
              <button
                className="btn-secondary"
                disabled={detectMutation.isPending}
                onClick={() => detectMutation.mutate()}
              >
                {detectMutation.isPending ? "Scanning open tickets..." : "Scan for new incidents"}
              </button>
              <button className="btn-primary" onClick={() => setCreateOpen(true)}>
                Create incident
              </button>
            </div>
          )
        }
      />

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <MetricSummary label="Active incidents" value={data.summary.active_incidents} tone="accent" />
        <MetricSummary
          label="Newly detected (review)"
          value={data.summary.newly_detected}
          tone={data.summary.newly_detected > 0 ? "warning" : "default"}
          sublabel="Suggestions awaiting manager confirmation"
        />
        <MetricSummary
          label="Investigating / confirmed"
          value={data.summary.confirmed_or_investigating}
          tone={data.summary.confirmed_or_investigating > 0 ? "critical" : "default"}
        />
        <MetricSummary
          label="Unique affected customers"
          value={data.summary.unique_affected_customers_active}
          sublabel="Distinct customers across active incidents"
          tone="critical"
        />
      </div>

      {/* Filters */}
      <div className="surface-card p-3 mb-4 flex flex-wrap items-center gap-2.5">
        <select
          aria-label="Filter incident status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="field-input w-48"
        >
          <option value="">All active & resolved</option>
          <option value="detected">Detected (Review)</option>
          <option value="investigating">Investigating</option>
          <option value="confirmed">Confirmed</option>
          <option value="monitoring">Monitoring</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select
          aria-label="Filter incident severity"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="field-input w-40"
        >
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {data.items.length === 0 ? (
        <EmptyState
          title="No active incidents detected"
          description="Run 'Scan for new incidents' to cluster semantically similar open tickets, or create an incident manually."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left: Incident List */}
          <div className="lg:col-span-5 surface-card divide-y divide-[#E3E7E4]">
            {data.items.map((inc) => (
              <button
                key={inc.id}
                type="button"
                onClick={() => setSelectedId(inc.id)}
                className={`w-full text-left p-4 transition-colors ${
                  activeSelectionId === inc.id ? "bg-[#F0F4F2]" : "hover:bg-[#FAFBF9]"
                }`}
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-mono text-[12px] font-semibold text-[#38685A]">
                    {inc.incident_reference}
                  </span>
                  <div className="flex items-center gap-2">
                    <PriorityIndicator priority={inc.severity} />
                    <IncidentStatusBadge status={inc.status} />
                  </div>
                </div>
                <div className="text-[13.5px] font-semibold text-[#222C2A] mt-1">
                  {inc.title}
                </div>
                <div className="flex flex-wrap gap-3 text-[12px] text-[#78817D] mt-1.5">
                  <span>
                    <strong className="text-[#222C2A]">{inc.affected_customer_count}</strong> unique customers
                  </span>
                  <span>
                    <strong className="text-[#222C2A]">{inc.ticket_count}</strong> linked tickets
                  </span>
                  <span>{inc.department_name}</span>
                </div>
                {inc.common_symptoms.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {inc.common_symptoms.slice(0, 4).map((sym) => (
                      <span
                        key={sym}
                        className="text-[11px] px-1.5 py-0.5 bg-white border border-[#E3E7E4] rounded text-[#78817D]"
                      >
                        {sym}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Right: Incident Detail & Investigation Workspace */}
          <div className="lg:col-span-7 space-y-4">
            {loadingDetail || !detail ? (
              <LoadingSkeleton rows={6} />
            ) : (
              <>
                <div className="surface-card p-5 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#E3E7E4] pb-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-[13px] font-semibold text-[#38685A]">
                          {detail.incident_reference}
                        </span>
                        <PriorityIndicator priority={detail.severity} />
                        <IncidentStatusBadge status={detail.status} />
                        {detail.is_demo_data && (
                          <span className="text-[11px] px-1.5 py-0.5 rounded bg-[#F5F6F4] border border-[#E3E7E4] text-[#78817D]">
                            Demo scenario
                          </span>
                        )}
                      </div>
                      <h2 className="text-[16px] font-semibold text-[#222C2A] mt-1">
                        {detail.title}
                      </h2>
                      {detail.description && (
                        <p className="text-[12.5px] text-[#78817D] mt-1">{detail.description}</p>
                      )}
                    </div>

                    {isManagerOrAdmin && (
                      <div className="flex flex-wrap gap-1.5">
                        {detail.status === "detected" && (
                          <>
                            <button
                              className="btn-primary text-[12px]"
                              onClick={() => updateMutation.mutate({ status: "investigating" })}
                            >
                              Investigate
                            </button>
                            <button
                              className="btn-secondary text-[12px]"
                              onClick={() => updateMutation.mutate({ status: "confirmed" })}
                            >
                              Confirm incident
                            </button>
                            <button
                              className="btn-danger text-[12px]"
                              onClick={() => updateMutation.mutate({ status: "dismissed" })}
                            >
                              Dismiss
                            </button>
                          </>
                        )}
                        {detail.status !== "detected" && detail.status !== "resolved" && (
                          <select
                            aria-label="Update incident status"
                            value={detail.status}
                            onChange={(e) => updateMutation.mutate({ status: e.target.value })}
                            className="field-input w-40"
                          >
                            <option value="investigating">Investigating</option>
                            <option value="confirmed">Confirmed</option>
                            <option value="monitoring">Monitoring</option>
                            <option value="resolved">Resolved</option>
                            <option value="dismissed">Dismissed</option>
                          </select>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Customer Impact Strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#FAFBF9] border border-[#E3E7E4] rounded p-3">
                    <div>
                      <div className="text-[11.5px] text-[#78817D]">Unique affected customers</div>
                      <div className="text-[18px] font-semibold text-[#B84C4C]">
                        {detail.customer_impact.unique_affected_customers}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11.5px] text-[#78817D]">Linked tickets</div>
                      <div className="text-[18px] font-semibold text-[#222C2A]">
                        {detail.customer_impact.total_linked_tickets}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11.5px] text-[#78817D]">Repeat reporters</div>
                      <div className="text-[18px] font-semibold text-[#C08A3E]">
                        {detail.customer_impact.repeat_complaint_customers}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11.5px] text-[#78817D]">First / Last reported</div>
                      <div className="text-[12px] font-medium text-[#222C2A] mt-0.5">
                        {formatShortDate(detail.first_reported_at)} — {formatShortDate(detail.last_reported_at)}
                      </div>
                    </div>
                  </div>

                  {/* Investigation & Resolution Notes */}
                  <div className="space-y-3">
                    <div>
                      <label className="block text-[12px] font-medium text-[#222C2A] mb-1">
                        Investigation notes
                      </label>
                      <textarea
                        rows={3}
                        disabled={!isManagerOrAdmin}
                        value={notesInput}
                        onChange={(e) => setNotesInput(e.target.value)}
                        placeholder="Document root-cause findings, engineering ticket IDs, or partner updates..."
                        className="field-input"
                      />
                    </div>
                    <div>
                      <label className="block text-[12px] font-medium text-[#222C2A] mb-1">
                        Resolution summary
                      </label>
                      <textarea
                        rows={2}
                        disabled={!isManagerOrAdmin}
                        value={resSummaryInput}
                        onChange={(e) => setResSummaryInput(e.target.value)}
                        placeholder="Summarize verified remediation steps once resolved..."
                        className="field-input"
                      />
                    </div>
                    {isManagerOrAdmin && (
                      <div className="flex justify-end">
                        <button
                          className="btn-primary"
                          disabled={updateMutation.isPending}
                          onClick={() =>
                            updateMutation.mutate({
                              investigation_notes: notesInput,
                              resolution_summary: resSummaryInput,
                            })
                          }
                        >
                          Save investigation notes
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Linked Tickets */}
                <div className="surface-card overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#E3E7E4] flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[13.5px] font-semibold">
                      Linked Tickets ({detail.tickets.length})
                    </span>
                    <div className="flex gap-1.5 items-center">
                      <input
                        type="number"
                        min={1}
                        value={linkTicketId}
                        onChange={(e) => setLinkTicketId(e.target.value)}
                        placeholder="Ticket numeric ID..."
                        className="field-input w-40 py-1 text-[12px]"
                      />
                      <button
                        className="btn-secondary py-1 text-[12px]"
                        disabled={!linkTicketId}
                        onClick={() => linkMutation.mutate(Number(linkTicketId))}
                      >
                        Link ticket
                      </button>
                    </div>
                  </div>
                  <div className="overflow-x-auto max-h-72 overflow-y-auto">
                    <table className="w-full text-left border-collapse text-[12.5px]">
                      <thead>
                        <tr className="table-header">
                          <th className="py-2 px-3">Ticket</th>
                          <th className="py-2 px-3">Subject</th>
                          <th className="py-2 px-3">Customer</th>
                          <th className="py-2 px-3">Status</th>
                          <th className="py-2 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E3E7E4]">
                        {detail.tickets.map((t) => (
                          <tr key={t.ticket_id} className="hover:bg-[#FAFBF9]">
                            <td className="py-2 px-3 font-mono text-[12px]">
                              <Link to={`/tickets/${t.ticket_id}`} className="text-[#38685A] hover:underline">
                                {t.ticket_reference}
                              </Link>
                            </td>
                            <td className="py-2 px-3 max-w-xs truncate">{t.subject}</td>
                            <td className="py-2 px-3 text-[#78817D] whitespace-nowrap">{t.customer_name}</td>
                            <td className="py-2 px-3">
                              <StatusLabel status={t.status} />
                            </td>
                            <td className="py-2 px-3 text-right">
                              <button
                                className="text-[11.5px] text-[#B84C4C] hover:underline"
                                onClick={() => unlinkMutation.mutate(t.ticket_id)}
                              >
                                Unlink
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Create Incident Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-md w-full p-5 bg-white space-y-3">
            <h2 className="text-[15px] font-semibold">Create Incident</h2>
            <input
              placeholder="Incident title *"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="field-input"
            />
            <textarea
              rows={3}
              placeholder="Summary of symptoms and scope..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="field-input"
            />
            <div className="grid grid-cols-2 gap-2">
              <select
                value={newSev}
                onChange={(e) => setNewSev(e.target.value as any)}
                className="field-input"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select
                value={newDeptId}
                onChange={(e) => setNewDeptId(e.target.value)}
                className="field-input"
              >
                <option value="">Select department</option>
                {departments?.map((d) => (
                  <option key={d.department_id} value={String(d.department_id)}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={newTitle.trim().length < 4 || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                Create incident
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
