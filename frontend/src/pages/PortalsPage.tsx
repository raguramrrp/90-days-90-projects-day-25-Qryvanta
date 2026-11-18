import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { PageHeader, MetricSummary, LoadingSkeleton, ErrorState } from "../components/UI";

interface PortalAnalyticsResponse {
  platform_types: string[];
  total_tickets: number;
  verification_pipeline: { status: string; count: number }[];
  by_portal: {
    platform_type: string;
    total: number;
    open: number;
    resolved: number;
    unverified: number;
    under_verification: number;
    verified_ready: number;
    reported_to_company: number;
    company_acknowledged: number;
    company_resolved: number;
    insufficient_proof: number;
  }[];
  by_company: {
    company_id: number | null;
    company_name: string;
    platform_type: string;
    support_email?: string | null;
    total: number;
    open: number;
    unverified: number;
    verified_ready: number;
    reported_to_company: number;
    company_acknowledged: number;
    company_resolved: number;
    verification_rate: number;
    sla_compliance_rate: number | null;
  }[];
}

export function PortalsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const canManage = user?.role === "manager" || user?.role === "admin";

  const [portalFilter, setPortalFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [cName, setCName] = useState("");
  const [cPlatform, setCPlatform] = useState("E-Commerce");
  const [cUrl, setCUrl] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cDesc, setCDesc] = useState("");

  const qs = portalFilter ? `?platform_type=${encodeURIComponent(portalFilter)}` : "";
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["analytics-portals", portalFilter],
    queryFn: () => apiRequest<PortalAnalyticsResponse>(`/api/analytics/portals${qs}`),
  });

  const createCompanyMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/companies", {
        method: "POST",
        body: JSON.stringify({
          name: cName,
          platform_type: cPlatform,
          portal_url: cUrl || null,
          support_email: cEmail || null,
          description: cDesc || null,
        }),
      }),
    onSuccess: () => {
      notify("Company added to portal registry.", "success");
      setModalOpen(false);
      setCName(""); setCUrl(""); setCEmail(""); setCDesc("");
      qc.invalidateQueries({ queryKey: ["analytics-portals"] });
      qc.invalidateQueries({ queryKey: ["companies-active"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to register company.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) return <ErrorState message="Failed to load portal & company reporting." onRetry={() => refetch()} />;

  const pipeMap = Object.fromEntries(data.verification_pipeline.map((p) => [p.status, p.count]));
  const totalVerifiedOrBeyond =
    (pipeMap.verified_ready || 0) +
    (pipeMap.reported_to_company || 0) +
    (pipeMap.company_acknowledged || 0) +
    (pipeMap.company_resolved || 0);

  return (
    <div>
      <PageHeader
        title="Portals, Companies & Verification Handoff"
        subtitle="Portal-wise reporting, company case statuses, and QRYVANTA pre-verification pipeline so partner companies can resolve verified claims directly."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter by platform portal"
              value={portalFilter}
              onChange={(e) => setPortalFilter(e.target.value)}
              className="field-input w-48"
            >
              <option value="">All platforms / portals</option>
              {data.platform_types.map((pt) => (
                <option key={pt} value={pt}>
                  {pt}
                </option>
              ))}
            </select>
            {canManage && (
              <button className="btn-primary" onClick={() => setModalOpen(true)}>
                Register company
              </button>
            )}
          </div>
        }
      />

      {/* Verification Pipeline Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
        <MetricSummary label="Total portal tickets" value={data.total_tickets} />
        <MetricSummary
          label="Pending verification"
          value={(pipeMap.unverified || 0) + (pipeMap.under_verification || 0)}
          tone="warning"
          sublabel="Needs QRYVANTA proof check"
        />
        <MetricSummary
          label="Verified — ready"
          value={pipeMap.verified_ready || 0}
          tone="accent"
          sublabel="Dossier ready to dispatch"
        />
        <MetricSummary
          label="Reported to company"
          value={(pipeMap.reported_to_company || 0) + (pipeMap.company_acknowledged || 0)}
          sublabel="Active with target company"
        />
        <MetricSummary
          label="Company resolved"
          value={pipeMap.company_resolved || 0}
          tone="accent"
          sublabel={`${data.total_tickets ? Math.round((totalVerifiedOrBeyond / data.total_tickets) * 100) : 0}% pre-verified overall`}
        />
      </div>

      {/* Portal-Wise Chart & Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-5">
        <div className="lg:col-span-7 surface-card p-4">
          <div className="text-[13.5px] font-semibold text-[#222C2A] mb-3">
            Portal-Wise Ticket Status & Handoff Progress
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_portal}>
                <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="platform_type" tick={{ fontSize: 11, fill: "#222C2A" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11.5 }} />
                <Bar dataKey="unverified" name="Unverified" stackId="a" fill="#C08A3E" />
                <Bar dataKey="verified_ready" name="Verified ready" stackId="a" fill="#8AA397" />
                <Bar dataKey="reported_to_company" name="Reported to company" stackId="a" fill="#38685A" />
                <Bar dataKey="company_resolved" name="Company resolved" stackId="a" fill="#222C2A" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-5 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Portal Summary
          </div>
          <div className="divide-y divide-[#E3E7E4] text-[13px]">
            {data.by_portal.map((p) => (
              <div key={p.platform_type} className="px-4 py-3 flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium text-[#222C2A]">{p.platform_type}</div>
                  <div className="text-[11.5px] text-[#78817D]">
                    {p.verified_ready} ready · {p.reported_to_company + p.company_acknowledged} reported · {p.company_resolved} resolved
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-[#38685A]">{p.total} tickets</div>
                  <Link
                    to={`/tickets?platform_type=${encodeURIComponent(p.platform_type)}`}
                    className="text-[11.5px] text-[#38685A] hover:underline"
                  >
                    Open queue
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Company-Wise Table */}
      <div className="surface-card overflow-x-auto">
        <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
          Company-Wise Reporting & Verification Status
        </div>
        <table className="w-full text-left border-collapse text-[13px]">
          <thead>
            <tr className="table-header">
              <th className="py-2.5 px-4">Company</th>
              <th className="py-2.5 px-3">Portal</th>
              <th className="py-2.5 px-3">Total</th>
              <th className="py-2.5 px-3">Open</th>
              <th className="py-2.5 px-3">Verified Ready</th>
              <th className="py-2.5 px-3">Reported / Ack</th>
              <th className="py-2.5 px-3">Company Resolved</th>
              <th className="py-2.5 px-3">Pre-Verified %</th>
              <th className="py-2.5 px-3 text-right">Queue</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E3E7E4]">
            {data.by_company.map((c) => (
              <tr key={c.company_id ?? c.company_name} className="hover:bg-[#FAFBF9]">
                <td className="py-2.5 px-4">
                  <div className="font-medium text-[#222C2A]">{c.company_name}</div>
                  {c.support_email && (
                    <div className="text-[11.5px] text-[#78817D]">{c.support_email}</div>
                  )}
                </td>
                <td className="py-2.5 px-3 text-[#78817D]">{c.platform_type}</td>
                <td className="py-2.5 px-3 font-medium">{c.total}</td>
                <td className="py-2.5 px-3">{c.open}</td>
                <td className="py-2.5 px-3 text-[#38685A] font-medium">{c.verified_ready}</td>
                <td className="py-2.5 px-3">{c.reported_to_company + c.company_acknowledged}</td>
                <td className="py-2.5 px-3">{c.company_resolved}</td>
                <td className="py-2.5 px-3 font-medium text-[#38685A]">{c.verification_rate}%</td>
                <td className="py-2.5 px-3 text-right">
                  {c.company_id && (
                    <Link
                      to={`/tickets?company_id=${c.company_id}`}
                      className="btn-secondary py-1 px-2.5 text-[12px]"
                    >
                      View tickets
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Register Company Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-md w-full p-5 bg-white space-y-3">
            <h2 className="text-[15px] font-semibold">Register Target Company / Portal</h2>
            <input placeholder="Company name * (e.g., FreshCart E-Commerce)" value={cName} onChange={(e) => setCName(e.target.value)} className="field-input" />
            <select value={cPlatform} onChange={(e) => setCPlatform(e.target.value)} className="field-input">
              {data.platform_types.map((pt) => (
                <option key={pt} value={pt}>{pt}</option>
              ))}
            </select>
            <input placeholder="Portal URL (optional)" value={cUrl} onChange={(e) => setCUrl(e.target.value)} className="field-input" />
            <input placeholder="Company resolution email (optional)" value={cEmail} onChange={(e) => setCEmail(e.target.value)} className="field-input" />
            <textarea rows={2} placeholder="Brief description..." value={cDesc} onChange={(e) => setCDesc(e.target.value)} className="field-input" />
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button
                className="btn-primary"
                disabled={cName.trim().length < 2 || createCompanyMutation.isPending}
                onClick={() => createCompanyMutation.mutate()}
              >
                Register company
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
