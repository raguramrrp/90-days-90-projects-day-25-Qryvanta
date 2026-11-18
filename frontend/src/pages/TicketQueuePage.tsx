import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Download, Search, Upload } from "lucide-react";
import { apiDownloadBlob, apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { AgentMetrics, CompanyItem, DepartmentMetrics, TicketSummary } from "../types";
import {
  PageHeader,
  StatusLabel,
  PriorityIndicator,
  SLAIndicator,
  RiskBadge,
  VerificationBadge,
  Pagination,
  LoadingSkeleton,
  ErrorState,
  EmptyState,
  formatShortDate,
} from "../components/UI";

interface TicketListResponse {
  items: TicketSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const PRESETS = [
  { key: "", label: "All tickets" },
  { key: "my_tickets", label: "My tickets", staffOnly: true },
  { key: "unassigned", label: "Unassigned", staffOnly: true },
  { key: "critical_high", label: "Critical & high", staffOnly: true },
  { key: "high_risk", label: "High SLA risk", staffOnly: true },
  { key: "overdue", label: "Overdue SLA", staffOnly: true },
  { key: "awaiting_response", label: "Awaiting response" },
  { key: "low_confidence", label: "Low confidence", staffOnly: true },
  { key: "reopened", label: "Reopened" },
];

export function TicketQueuePage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const isStaff = user?.role !== "customer";
  const isManagerOrAdmin = user?.role === "manager" || user?.role === "admin";

  const [preset, setPreset] = useState(searchParams.get("preset") || "");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState(searchParams.get("platform_type") || "");
  const [companyFilter, setCompanyFilter] = useState(searchParams.get("company_id") || "");
  const [verificationFilter, setVerificationFilter] = useState(searchParams.get("verification_status") || "");
  const [riskFilter, setRiskFilter] = useState(searchParams.get("risk_level") || "");
  const [incidentOnly, setIncidentOnly] = useState(searchParams.get("incident_linked") === "true");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(1);

  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAgentId, setBulkAgentId] = useState("");
  const [bulkStatus, setBulkStatus] = useState("");

  // CSV Bulk Import modal state
  const [importOpen, setImportOpen] = useState(false);
  const [importPreview, setImportPreview] = useState<{
    columns: string[];
    total_rows: number;
    preview_rows: Record<string, string>[];
    suggested_mapping: Record<string, string>;
    csv_text: string;
  } | null>(null);
  const [importMapping, setImportMapping] = useState<Record<string, string>>({});
  const [importResult, setImportResult] = useState<{
    imported_count: number;
    skipped_duplicates: number;
    failed_count: number;
  } | null>(null);

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("page_size", "15");
  queryParams.set("sort_by", sortBy);
  queryParams.set("sort_order", sortOrder);
  if (preset) queryParams.set("preset", preset);
  if (search.trim()) queryParams.set("search", search.trim());
  if (statusFilter) queryParams.set("status", statusFilter);
  if (priorityFilter) queryParams.set("priority", priorityFilter);
  if (deptFilter) queryParams.set("department_id", deptFilter);
  if (platformFilter) queryParams.set("platform_type", platformFilter);
  if (companyFilter) queryParams.set("company_id", companyFilter);
  if (verificationFilter) queryParams.set("verification_status", verificationFilter);
  if (riskFilter) queryParams.set("risk_level", riskFilter);
  if (incidentOnly) queryParams.set("incident_linked", "true");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["tickets", queryParams.toString()],
    queryFn: () => apiRequest<TicketListResponse>(`/api/tickets?${queryParams.toString()}`),
  });

  const { data: companiesData } = useQuery({
    queryKey: ["companies-list"],
    queryFn: () => apiRequest<{ platform_types: string[]; companies: CompanyItem[] }>("/api/companies"),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
    enabled: isStaff,
  });

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiRequest<AgentMetrics[]>("/api/agents"),
    enabled: isManagerOrAdmin,
  });

  const bulkMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiRequest<{ updated_count: number }>("/api/tickets/bulk-action", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (res) => {
      notify(`Updated ${res.updated_count} ticket(s).`, "success");
      setSelectedIds([]);
      setBulkAgentId("");
      setBulkStatus("");
      qc.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Bulk update failed.", "error"),
  });

  const handleExportCsv = async () => {
    try {
      const p = new URLSearchParams();
      if (statusFilter) p.set("status", statusFilter);
      if (priorityFilter) p.set("priority", priorityFilter);
      if (deptFilter) p.set("department_id", deptFilter);
      await apiDownloadBlob(`/api/tickets/export/csv?${p.toString()}`, "qryvanta_tickets.csv");
      notify("Exported tickets to CSV.", "success");
    } catch {
      notify("Failed to export CSV.", "error");
    }
  };

  const handleFilePreview = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiRequest<typeof importPreview>("/api/tickets/import/preview", {
        method: "POST",
        body: fd,
      });
      setImportPreview(res);
      setImportMapping(res?.suggested_mapping || {});
      setImportResult(null);
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Failed to parse CSV.", "error");
    }
  };

  const handleExecuteImport = async () => {
    if (!importPreview) return;
    try {
      const res = await apiRequest<{
        imported_count: number;
        skipped_duplicates: number;
        failed_count: number;
      }>("/api/tickets/import/execute", {
        method: "POST",
        body: JSON.stringify({
          csv_text: importPreview.csv_text,
          column_mapping: importMapping,
          is_demo_data: false,
        }),
      });
      setImportResult(res);
      notify(`Imported ${res.imported_count} tickets (${res.skipped_duplicates} duplicates skipped).`, "success");
      qc.invalidateQueries({ queryKey: ["tickets"] });
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Import failed.", "error");
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const visiblePresets = PRESETS.filter((p) => !p.staffOnly || isStaff);

  return (
    <div>
      <PageHeader
        title={isStaff ? "Ticket Queue" : "My Support Tickets"}
        subtitle={
          isStaff
            ? "Filter, triage, assign, and export operational support tickets."
            : "Track progress on your submitted support requests and reply to agents."
        }
        actions={
          <div className="flex flex-wrap gap-2">
            {isManagerOrAdmin && (
              <button className="btn-secondary inline-flex items-center gap-1.5" onClick={() => setImportOpen(true)}>
                <Upload className="w-3.5 h-3.5" />
                Bulk CSV import
              </button>
            )}
            {isStaff && (
              <button className="btn-secondary inline-flex items-center gap-1.5" onClick={handleExportCsv}>
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </button>
            )}
            <Link to="/submit" className="btn-primary">
              Submit ticket
            </Link>
          </div>
        }
      />

      {/* Quick Filter Presets */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {visiblePresets.map((p) => (
          <button
            key={p.key || "all"}
            onClick={() => {
              setPreset(p.key);
              setPage(1);
              if (p.key) setSearchParams({ preset: p.key });
              else setSearchParams({});
            }}
            className={`px-3 py-1.5 text-[12.5px] rounded border transition-colors ${
              preset === p.key
                ? "bg-[#38685A] text-white border-[#38685A] font-medium"
                : "bg-white text-[#222C2A] border-[#E3E7E4] hover:bg-[#F5F6F4]"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Search & Multi-filter Bar */}
      <div className="surface-card p-3.5 mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5">
        <div className="lg:col-span-2 relative">
          <Search className="w-3.5 h-3.5 text-[#78817D] absolute left-2.5 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search ID, subject, or customer..."
            className="field-input pl-8"
          />
        </div>

        <select
          aria-label="Filter by status"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="field-input"
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="awaiting_customer">Awaiting customer</option>
          <option value="reopened">Reopened</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>

        <select
          aria-label="Filter by priority"
          value={priorityFilter}
          onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}
          className="field-input"
        >
          <option value="">All priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        {isStaff && (
          <select
            aria-label="Filter by department"
            value={deptFilter}
            onChange={(e) => { setDeptFilter(e.target.value); setPage(1); }}
            className="field-input"
          >
            <option value="">All departments</option>
            {departments?.map((d) => (
              <option key={d.department_id} value={String(d.department_id)}>
                {d.name}
              </option>
            ))}
          </select>
        )}

        <select
          aria-label="Filter by portal"
          value={platformFilter}
          onChange={(e) => { setPlatformFilter(e.target.value); setPage(1); }}
          className="field-input"
        >
          <option value="">All platforms</option>
          {(companiesData?.platform_types || []).map((pt) => (
            <option key={pt} value={pt}>{pt}</option>
          ))}
        </select>

        <select
          aria-label="Filter by company"
          value={companyFilter}
          onChange={(e) => { setCompanyFilter(e.target.value); setPage(1); }}
          className="field-input"
        >
          <option value="">All companies</option>
          {(companiesData?.companies || []).map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>

        <select
          aria-label="Filter by verification status"
          value={verificationFilter}
          onChange={(e) => { setVerificationFilter(e.target.value); setPage(1); }}
          className="field-input"
        >
          <option value="">All verification stages</option>
          <option value="unverified">Unverified</option>
          <option value="under_verification">Under verification</option>
          <option value="verified_ready">Verified — ready</option>
          <option value="reported_to_company">Reported to company</option>
          <option value="company_acknowledged">Company acknowledged</option>
          <option value="company_resolved">Company resolved</option>
          <option value="insufficient_proof">Needs proof</option>
        </select>

        {isStaff && (
          <select
            aria-label="Filter by SLA risk"
            value={riskFilter}
            onChange={(e) => { setRiskFilter(e.target.value); setPage(1); }}
            className="field-input"
          >
            <option value="">All SLA risk</option>
            <option value="critical">Critical risk</option>
            <option value="high">High risk</option>
            <option value="moderate">Moderate risk</option>
            <option value="low">Low risk</option>
          </select>
        )}

        {isStaff && (
          <label className="inline-flex items-center gap-2 px-2.5 py-1.5 border border-[#E3E7E4] rounded bg-white text-[12.5px] text-[#222C2A] cursor-pointer">
            <input
              type="checkbox"
              checked={incidentOnly}
              onChange={(e) => { setIncidentOnly(e.target.checked); setPage(1); }}
            />
            Incident-linked only
          </label>
        )}

        <select
          aria-label="Sort tickets"
          value={`${sortBy}:${sortOrder}`}
          onChange={(e) => {
            const [col, ord] = e.target.value.split(":");
            setSortBy(col);
            setSortOrder(ord);
          }}
          className="field-input"
        >
          <option value="created_at:desc">Newest first</option>
          <option value="created_at:asc">Oldest first</option>
          <option value="priority:desc">Highest priority</option>
          <option value="sla:asc">Earliest SLA deadline</option>
        </select>
      </div>

      {/* Bulk Action Bar for Managers/Admins */}
      {isManagerOrAdmin && selectedIds.length > 0 && (
        <div className="surface-card p-3 mb-4 flex flex-wrap items-center gap-3 bg-[#F0F4F2] border-[#C9DBD3]">
          <span className="text-[13px] font-medium text-[#222C2A]">
            {selectedIds.length} selected
          </span>

          <div className="flex items-center gap-1.5">
            <select
              value={bulkAgentId}
              onChange={(e) => setBulkAgentId(e.target.value)}
              className="field-input w-44"
            >
              <option value="">Assign to agent...</option>
              {agents?.map((a) => (
                <option key={a.agent_id} value={String(a.agent_id)}>
                  {a.name} ({a.open_tickets}/{a.max_open_tickets})
                </option>
              ))}
            </select>
            <button
              className="btn-primary"
              disabled={!bulkAgentId || bulkMutation.isPending}
              onClick={() =>
                bulkMutation.mutate({
                  ticket_ids: selectedIds,
                  action: "assign",
                  agent_id: Number(bulkAgentId),
                })
              }
            >
              Assign
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <select
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
              className="field-input w-40"
            >
              <option value="">Update status...</option>
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="awaiting_customer">Awaiting customer</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
            <button
              className="btn-secondary"
              disabled={!bulkStatus || bulkMutation.isPending}
              onClick={() =>
                bulkMutation.mutate({
                  ticket_ids: selectedIds,
                  action: "status",
                  status: bulkStatus,
                })
              }
            >
              Apply
            </button>
          </div>

          <button className="text-[12px] text-[#78817D] ml-auto hover:underline" onClick={() => setSelectedIds([])}>
            Clear selection
          </button>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load tickets."}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No tickets match the current view"
          description="Try clearing search keywords or filter presets, or submit a new support ticket."
          action={
            <button
              className="btn-secondary"
              onClick={() => {
                setPreset("");
                setSearch("");
                setStatusFilter("");
                setPriorityFilter("");
                setDeptFilter("");
                setPlatformFilter("");
                setCompanyFilter("");
                setVerificationFilter("");
                setRiskFilter("");
                setIncidentOnly(false);
                setSearchParams({});
              }}
            >
              Reset filters
            </button>
          }
        />
      ) : (
        <>
          <div className="surface-card overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="table-header">
                  {isManagerOrAdmin && <th className="py-3 pl-4 pr-2 w-8" />}
                  <th className="py-3 px-3.5 min-w-[280px]">Ticket &amp; Subject</th>
                  <th className="py-3 px-3.5 whitespace-nowrap">Company &amp; Customer</th>
                  <th className="py-3 px-3.5 whitespace-nowrap">Category &amp; Owner</th>
                  <th className="py-3 px-3.5 whitespace-nowrap">Priority</th>
                  <th className="py-3 px-3.5 whitespace-nowrap">Verification</th>
                  <th className="py-3 px-3.5 whitespace-nowrap">SLA &amp; Risk</th>
                  <th className="py-3 px-3.5 whitespace-nowrap text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E6EBE8] text-[13px]">
                {data.items.map((t) => (
                  <tr key={t.id} className="hover:bg-[#F8FAF9] transition-colors">
                    {isManagerOrAdmin && (
                      <td className="py-3.5 pl-4 pr-2 align-top">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(t.id)}
                          onChange={() => toggleSelect(t.id)}
                          aria-label={`Select ${t.ticket_reference}`}
                          className="mt-1 accent-[#2F6354]"
                        />
                      </td>
                    )}
                    <td className="py-3.5 px-3.5 align-top max-w-[360px]">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Link
                          to={`/tickets/${t.id}`}
                          className="font-mono text-[12px] text-[#2F6354] font-semibold hover:underline whitespace-nowrap"
                        >
                          {t.ticket_reference}
                        </Link>
                        {t.linked_incidents && t.linked_incidents.length > 0 && (
                          <Link
                            to="/incidents"
                            className="text-[10.5px] font-mono px-1.5 py-0.5 bg-[#FEF2F2] text-[#B03E3E] border border-[#EBC3C3] rounded whitespace-nowrap"
                          >
                            {t.linked_incidents[0].incident_reference}
                          </Link>
                        )}
                        {t.is_demo_data && (
                          <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-[#F2F5F3] text-[#76847F] whitespace-nowrap">
                            Demo
                          </span>
                        )}
                      </div>
                      <Link
                        to={`/tickets/${t.id}`}
                        title={t.subject}
                        className="mt-1 text-[13.5px] text-[#1D2825] hover:text-[#2F6354] line-clamp-1 font-medium block"
                      >
                        {t.subject}
                      </Link>
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap">
                      <div className="text-[#1D2825] text-[13px] font-medium">
                        {isStaff ? (t.customer?.name || "—") : (t.company_name || "General")}
                      </div>
                      <div className="text-[11.5px] text-[#6E7C77] mt-0.5">
                        {t.company_name || "General"}
                        {t.external_reference ? ` · ${t.external_reference}` : ""}
                      </div>
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap">
                      <div className="text-[#1D2825] text-[12.5px] font-medium">
                        {t.category_name || "Uncategorized"}
                      </div>
                      <div className="text-[11.5px] text-[#6E7C77] mt-0.5">
                        {t.department_name || "Manual triage"}
                        {isStaff ? ` · ${t.assigned_agent?.name || "Unassigned"}` : ""}
                      </div>
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap">
                      <PriorityIndicator priority={t.priority} />
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap">
                      <VerificationBadge status={t.verification_status} />
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap">
                      <div className="flex flex-col items-start gap-1">
                        <SLAIndicator state={t.sla_state} />
                        {isStaff &&
                          t.sla_risk_level &&
                          (t.sla_risk_level === "critical" || t.sla_risk_level === "high") && (
                            <RiskBadge level={t.sla_risk_level} />
                          )}
                      </div>
                    </td>
                    <td className="py-3.5 px-3.5 align-top whitespace-nowrap text-right">
                      <div className="flex flex-col items-end gap-1">
                        <StatusLabel status={t.status} />
                        <span className="text-[11px] text-[#7D8B86]">
                          {formatShortDate(t.created_at)}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.total}
            onPageChange={(p) => setPage(p)}
          />
        </>
      )}

      {/* Bulk CSV Import Modal */}
      {importOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-2xl w-full p-5 bg-white max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E3E7E4] pb-3 mb-4">
              <h2 className="text-[15px] font-semibold">Bulk Ticket CSV Import</h2>
              <button className="btn-secondary" onClick={() => setImportOpen(false)}>
                Close
              </button>
            </div>

            <p className="text-[12.5px] text-[#78817D] mb-3">
              Upload a CSV file to preview records, map columns, detect duplicates, and run automatic classification on imported tickets.
            </p>

            <input type="file" accept=".csv" onChange={handleFilePreview} className="field-input mb-4" />

            {importPreview && (
              <div className="space-y-4">
                <div className="text-[12.5px] text-[#222C2A]">
                  Detected <strong>{importPreview.total_rows}</strong> rows with columns:{" "}
                  {importPreview.columns.join(", ")}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {(["subject", "description", "category", "product_reference"] as const).map((field) => (
                    <div key={field}>
                      <label className="block text-[12px] font-medium text-[#78817D] mb-1 capitalize">
                        {field.replace("_", " ")} {field === "subject" || field === "description" ? "*" : "(optional)"}
                      </label>
                      <select
                        value={importMapping[field] || ""}
                        onChange={(e) => setImportMapping((m) => ({ ...m, [field]: e.target.value }))}
                        className="field-input"
                      >
                        <option value="">-- Ignore --</option>
                        {importPreview.columns.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>

                <div className="border border-[#E3E7E4] rounded overflow-x-auto max-h-44">
                  <table className="w-full text-[12px] text-left">
                    <thead>
                      <tr className="table-header">
                        {importPreview.columns.slice(0, 4).map((c) => (
                          <th key={c} className="py-1.5 px-2">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E3E7E4]">
                      {importPreview.preview_rows.slice(0, 5).map((r, i) => (
                        <tr key={i}>
                          {importPreview.columns.slice(0, 4).map((c) => (
                            <td key={c} className="py-1.5 px-2 truncate max-w-[180px]">{r[c]}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end gap-2">
                  <button
                    className="btn-primary"
                    disabled={!importMapping.subject || !importMapping.description}
                    onClick={handleExecuteImport}
                  >
                    Run bulk import & classify
                  </button>
                </div>
              </div>
            )}

            {importResult && (
              <div className="mt-4 p-3 rounded border border-[#C9DBD3] bg-[#F0F4F2] text-[13px]">
                Import finished: <strong>{importResult.imported_count}</strong> imported,{" "}
                <strong>{importResult.skipped_duplicates}</strong> duplicate(s) skipped,{" "}
                <strong>{importResult.failed_count}</strong> failed validation.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
