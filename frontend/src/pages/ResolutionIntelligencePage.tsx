import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { PageHeader, MetricSummary, LoadingSkeleton, ErrorState, formatMinutes } from "../components/UI";

interface ResolutionOverviewResponse {
  effectiveness: {
    insufficient_data: boolean;
    sample_size: number;
    metrics: {
      fcr_rate?: number;
      reopen_rate?: number;
      repeat_issue_rate?: number;
      recurrence_after_closure_rate?: number;
      avg_resolution_minutes?: number | null;
      avg_csat?: number | null;
      csat_sample_size?: number;
    };
    by_category: {
      category: string;
      sample_size: number;
      small_sample_warning: boolean;
      fcr_rate: number | null;
      reopen_rate: number | null;
      avg_resolution_minutes: number | null;
      avg_csat: number | null;
    }[];
    by_department: {
      department: string;
      sample_size: number;
      small_sample_warning: boolean;
      fcr_rate: number | null;
      reopen_rate: number | null;
      avg_resolution_minutes: number | null;
      avg_csat: number | null;
    }[];
    recommendation_effectiveness: {
      total_ratings: number;
      helpful: number;
      partially_helpful: number;
      not_helpful: number;
      applied_to_replies: number;
      helpful_rate: number | null;
    };
    metric_definitions: Record<string, string>;
  };
  knowledge_gaps: {
    id: number;
    topic: string;
    category_name: string;
    related_ticket_count: number;
    unresolved_count: number;
    existing_article_count: number;
    topic_covered_by_kb: boolean;
    common_symptoms: string[];
    suggested_title: string;
    priority: string;
    status: string;
    draft_article_id: number | null;
  }[];
  recent_verified_resolutions: {
    ticket_id: number;
    ticket_reference: string;
    subject: string;
    category_name: string;
    department_name: string;
    resolution_excerpt: string;
    reopened: boolean;
    satisfaction_rating: number | null;
  }[];
}

export function ResolutionIntelligencePage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const isManagerOrAdmin = user?.role === "manager" || user?.role === "admin";

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["resolution-overview"],
    queryFn: () => apiRequest<ResolutionOverviewResponse>("/api/resolution/overview"),
  });

  const draftMutation = useMutation({
    mutationFn: (gapId: number) =>
      apiRequest<{ title: string }>(`/api/resolution/knowledge-gaps/${gapId}/draft`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (res) => {
      notify(`Created unpublished draft KB article: "${res.title}". Review in Settings -> Knowledge Base before publishing.`, "success");
      qc.invalidateQueries({ queryKey: ["resolution-overview"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create draft.", "error"),
  });

  const dismissMutation = useMutation({
    mutationFn: (gapId: number) =>
      apiRequest(`/api/resolution/knowledge-gaps/${gapId}/dismiss`, { method: "PATCH" }),
    onSuccess: () => {
      notify("Knowledge gap dismissed.", "info");
      qc.invalidateQueries({ queryKey: ["resolution-overview"] });
    },
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) return <ErrorState message="Failed to load Resolution Intelligence." onRetry={() => refetch()} />;

  const eff = data.effectiveness;
  const m = eff.metrics;
  const fb = eff.recommendation_effectiveness;

  return (
    <div>
      <PageHeader
        title="Resolution Intelligence & Knowledge Gaps"
        subtitle="Track genuine resolution quality (FCR, reopen & recurrence rates), reuse verified historical fixes, and close documentation gaps."
        actions={
          <div className="flex gap-2">
            <Link to="/intelligence" className="btn-secondary">
              Classification Intelligence
            </Link>
            <Link to="/models" className="btn-secondary">
              Model Centre
            </Link>
          </div>
        }
      />

      {/* Effectiveness Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
        <MetricSummary
          label="First Contact Resolution"
          value={m.fcr_rate !== undefined ? `${m.fcr_rate}%` : "N/A"}
          sublabel={`<=1 reply, 0 reopens (n=${eff.sample_size})`}
          tone="accent"
        />
        <MetricSummary
          label="Ticket reopen rate"
          value={m.reopen_rate !== undefined ? `${m.reopen_rate}%` : "N/A"}
          tone={(m.reopen_rate || 0) > 15 ? "warning" : "default"}
        />
        <MetricSummary
          label="Post-closure recurrence"
          value={m.recurrence_after_closure_rate !== undefined ? `${m.recurrence_after_closure_rate}%` : "N/A"}
          sublabel="Same customer/category within 14d"
        />
        <MetricSummary
          label="Recommendation helpfulness"
          value={fb.helpful_rate !== null ? `${fb.helpful_rate}%` : "No ratings"}
          sublabel={`${fb.total_ratings} rated · ${fb.applied_to_replies} applied`}
          tone="accent"
        />
        <MetricSummary
          label="Open knowledge gaps"
          value={data.knowledge_gaps.filter((g) => g.status === "open").length}
          tone="warning"
        />
      </div>

      {/* Knowledge Gap Detection */}
      <div className="surface-card overflow-hidden mb-5">
        <div className="px-4 py-3 border-b border-[#E3E7E4]">
          <h2 className="text-[13.5px] font-semibold text-[#222C2A]">
            Detected Knowledge Gaps (Based on Actual Ticket Topics & KB Coverage)
          </h2>
          <p className="text-[12px] text-[#78817D]">
            Draft articles created here are saved as unpublished drafts for editorial review and are never automatically published.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-[12.5px]">
            <thead>
              <tr className="table-header">
                <th className="py-2 px-4">Topic & Suggested Title</th>
                <th className="py-2 px-3">Tickets (Open)</th>
                <th className="py-2 px-3">KB Coverage</th>
                <th className="py-2 px-3">Common Symptoms</th>
                <th className="py-2 px-3">Priority</th>
                <th className="py-2 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7E4]">
              {data.knowledge_gaps.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-[#78817D]">
                    No significant knowledge gaps detected across current tickets.
                  </td>
                </tr>
              ) : (
                data.knowledge_gaps.map((g) => (
                  <tr key={g.id} className="hover:bg-[#FAFBF9]">
                    <td className="py-2.5 px-4">
                      <div className="font-medium text-[#222C2A]">{g.topic}</div>
                      <div className="text-[11.5px] text-[#78817D]">{g.suggested_title}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <strong>{g.related_ticket_count}</strong> ({g.unresolved_count} open)
                    </td>
                    <td className="py-2.5 px-3 text-[#78817D]">
                      {g.topic_covered_by_kb ? `${g.existing_article_count} article(s)` : "No dedicated guide"}
                    </td>
                    <td className="py-2.5 px-3 text-[#78817D]">
                      {g.common_symptoms.slice(0, 3).join(", ") || "—"}
                    </td>
                    <td className="py-2.5 px-3 capitalize font-medium">{g.priority}</td>
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      {g.status === "draft_created" ? (
                        <span className="text-[11.5px] text-[#38685A] font-medium">Draft created</span>
                      ) : g.status === "dismissed" ? (
                        <span className="text-[11.5px] text-[#78817D]">Dismissed</span>
                      ) : isManagerOrAdmin ? (
                        <div className="inline-flex gap-1.5">
                          <button
                            className="btn-primary py-1 px-2 text-[11.5px]"
                            disabled={draftMutation.isPending}
                            onClick={() => draftMutation.mutate(g.id)}
                          >
                            Create draft article
                          </button>
                          <button
                            className="btn-secondary py-1 px-2 text-[11.5px]"
                            onClick={() => dismissMutation.mutate(g.id)}
                          >
                            Dismiss
                          </button>
                        </div>
                      ) : (
                        <span className="text-[11.5px] text-[#78817D]">Manager review</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Category & Department Effectiveness Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
        <div className="surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Resolution Effectiveness by Category
          </div>
          <table className="w-full text-left border-collapse text-[12.5px]">
            <thead>
              <tr className="table-header">
                <th className="py-2 px-3">Category</th>
                <th className="py-2 px-2">n</th>
                <th className="py-2 px-2">FCR</th>
                <th className="py-2 px-2">Reopen</th>
                <th className="py-2 px-3">Avg Res</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7E4]">
              {eff.by_category.map((row) => (
                <tr key={row.category}>
                  <td className="py-2 px-3 font-medium">
                    {row.category}
                    {row.small_sample_warning && (
                      <span className="text-[10.5px] text-[#C08A3E] ml-1">(small n)</span>
                    )}
                  </td>
                  <td className="py-2 px-2 text-[#78817D]">{row.sample_size}</td>
                  <td className="py-2 px-2 text-[#38685A] font-medium">{row.fcr_rate}%</td>
                  <td className="py-2 px-2">{row.reopen_rate}%</td>
                  <td className="py-2 px-3">{formatMinutes(row.avg_resolution_minutes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Recent Genuine Resolved Cases (Reference Library)
          </div>
          <div className="divide-y divide-[#E3E7E4] max-h-80 overflow-y-auto text-[12.5px]">
            {data.recent_verified_resolutions.length === 0 ? (
              <div className="p-5 text-center text-[#78817D]">No resolved tickets with public staff resolutions yet.</div>
            ) : (
              data.recent_verified_resolutions.map((r) => (
                <div key={r.ticket_id} className="p-3.5">
                  <div className="flex justify-between gap-2">
                    <Link to={`/tickets/${r.ticket_id}`} className="font-mono text-[#38685A] hover:underline">
                      {r.ticket_reference}
                    </Link>
                    <span className="text-[11.5px] text-[#78817D]">
                      {r.category_name} {r.satisfaction_rating ? `· ${r.satisfaction_rating}/5` : ""}
                    </span>
                  </div>
                  <div className="font-medium text-[#222C2A] mt-0.5">{r.subject}</div>
                  <p className="text-[#78817D] text-[12px] mt-1 line-clamp-2">{r.resolution_excerpt}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
