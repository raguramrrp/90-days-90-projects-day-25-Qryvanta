import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Lock, ArrowLeft, BookOpen, CheckCircle2, FileDown } from "lucide-react";
import { apiDownloadBlob, apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { AgentMetrics, CategoryItem, DepartmentMetrics, TicketDetail } from "../types";
import {
  StatusLabel,
  PriorityIndicator,
  SLAIndicator,
  RiskBadge,
  IncidentStatusBadge,
  VerificationBadge,
  CollapsiblePanel,
  LoadingSkeleton,
  ErrorState,
  formatMinutes,
  formatShortDate,
} from "../components/UI";

interface SimilarResponse {
  similar_tickets: {
    ticket_id: number;
    ticket_reference: string;
    subject: string;
    category?: string | null;
    status: string;
    priority: string;
    similarity_score: number;
  }[];
}

export function TicketDetailPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const isStaff = user?.role !== "customer";

  const [replyText, setReplyText] = useState("");
  const [replyVisibility, setReplyVisibility] = useState<"public" | "internal">("public");
  const [replyStatus, setReplyStatus] = useState("");

  // Reclassify / Human-in-the-loop correction form
  const [showCorrect, setShowCorrect] = useState(false);
  const [corrCatId, setCorrCatId] = useState("");
  const [corrSubId, setCorrSubId] = useState("");
  const [corrDeptId, setCorrDeptId] = useState("");
  const [corrPriority, setCorrPriority] = useState("");
  const [corrReason, setCorrReason] = useState("");

  // Reopen & rating
  const [reopenReason, setReopenReason] = useState("");
  const [showReopen, setShowReopen] = useState(false);
  const [ratingVal, setRatingVal] = useState(5);
  const [ratingComment, setRatingComment] = useState("");

  // QRYVANTA Verification & Company Handoff state
  const [showVerifyForm, setShowVerifyForm] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState("verified_ready");
  const [verifyNotes, setVerifyNotes] = useState("");
  const [verifyAction, setVerifyAction] = useState("");
  const [verifyCompanyRef, setVerifyCompanyRef] = useState("");
  const [handoffPreview, setHandoffPreview] = useState<string | null>(null);

  const { data: ticket, isLoading, error, refetch } = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => apiRequest<TicketDetail>(`/api/tickets/${ticketId}`),
    enabled: Boolean(ticketId),
  });

  const { data: similarData } = useQuery({
    queryKey: ["similar", ticketId],
    queryFn: () => apiRequest<SimilarResponse>(`/api/intelligence/similar/${ticketId}`),
    enabled: Boolean(ticketId) && isStaff,
  });

  const { data: resolvedSimilarData } = useQuery({
    queryKey: ["similar-resolved", ticketId],
    queryFn: () =>
      apiRequest<{
        similar_resolved: {
          source_ticket_id: number;
          ticket_reference: string;
          subject: string;
          problem_description: string;
          actual_resolution: string;
          similarity_score: number;
          satisfaction_rating?: number | null;
          helpful_votes: number;
        }[];
      }>(`/api/resolution/similar/${ticketId}`),
    enabled: Boolean(ticketId) && isStaff,
  });

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiRequest<CategoryItem[]>("/api/categories"),
    enabled: isStaff,
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
    enabled: isStaff,
  });

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiRequest<AgentMetrics[]>("/api/agents"),
    enabled: isStaff,
  });

  const refreshTicket = () => {
    qc.invalidateQueries({ queryKey: ["ticket", ticketId] });
    qc.invalidateQueries({ queryKey: ["tickets"] });
  };

  const replyMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/reply`, {
        method: "POST",
        body: JSON.stringify({
          message: replyText,
          visibility: isStaff ? replyVisibility : "public",
          new_status: isStaff && replyStatus ? replyStatus : null,
        }),
      }),
    onSuccess: () => {
      setReplyText("");
      setReplyStatus("");
      notify(replyVisibility === "internal" ? "Internal note saved." : "Reply sent.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to send reply.", "error"),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiRequest(`/api/tickets/${ticketId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      notify("Ticket updated.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Update failed.", "error"),
  });

  const assignMutation = useMutation({
    mutationFn: (payload: { agent_id?: number; department_id?: number; reason?: string }) =>
      apiRequest(`/api/tickets/${ticketId}/assign`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      notify("Ticket assignment updated.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Assignment failed.", "error"),
  });

  const reclassifyMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/reclassify`, {
        method: "POST",
        body: JSON.stringify({
          corrected_category_id: Number(corrCatId),
          corrected_subcategory_id: corrSubId ? Number(corrSubId) : null,
          corrected_department_id: corrDeptId ? Number(corrDeptId) : null,
          corrected_priority: corrPriority || null,
          correction_reason: corrReason,
        }),
      }),
    onSuccess: () => {
      setShowCorrect(false);
      setCorrReason("");
      notify("Classification correction stored for feedback analytics and future retraining.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Correction failed.", "error"),
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/close`, {
        method: "POST",
        body: JSON.stringify({ status: "resolved" }),
      }),
    onSuccess: () => {
      notify("Ticket marked as resolved.", "success");
      refreshTicket();
    },
  });

  const reopenMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/reopen`, {
        method: "POST",
        body: JSON.stringify({ reason: reopenReason }),
      }),
    onSuccess: () => {
      setShowReopen(false);
      setReopenReason("");
      notify("Ticket reopened.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Unable to reopen.", "error"),
  });

  const rateMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/rate`, {
        method: "POST",
        body: JSON.stringify({ rating: ratingVal, comment: ratingComment || null }),
      }),
    onSuccess: () => {
      notify("Thank you for your feedback.", "success");
      refreshTicket();
    },
  });

  const linkRelationMutation = useMutation({
    mutationFn: (payload: { related_ticket_id: number; relation_type: "duplicate" | "related"; similarity_score: number }) =>
      apiRequest(`/api/tickets/${ticketId}/relations`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      notify("Ticket relationship recorded.", "success");
      refreshTicket();
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/tickets/${ticketId}/verify`, {
        method: "POST",
        body: JSON.stringify({
          verification_status: verifyStatus,
          verification_notes: verifyNotes,
          recommended_company_action: verifyAction || null,
          company_case_reference: verifyCompanyRef || null,
        }),
      }),
    onSuccess: () => {
      setShowVerifyForm(false);
      notify("Verification & company handoff status saved.", "success");
      refreshTicket();
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to save verification.", "error"),
  });

  const handlePreviewCompanyReport = async () => {
    try {
      const rep = await apiRequest<{ report_markdown: string }>(`/api/tickets/${ticketId}/company-report`);
      setHandoffPreview(rep.report_markdown);
    } catch {
      notify("Unable to generate company handoff brief.", "error");
    }
  };

  const handleDownloadCompanyReport = async () => {
    try {
      await apiDownloadBlob(
        `/api/tickets/${ticketId}/company-report?download=true`,
        `${ticket?.ticket_reference || "ticket"}_company_handoff_brief.md`
      );
      notify("Downloaded verified company handoff brief.", "success");
    } catch {
      notify("Failed to download company handoff brief.", "error");
    }
  };

  const resolutionFeedbackMutation = useMutation({
    mutationFn: (payload: {
      source_ticket_id: number;
      rating: "helpful" | "partially_helpful" | "not_helpful";
      applied_to_reply: boolean;
    }) =>
      apiRequest("/api/resolution/feedback", {
        method: "POST",
        body: JSON.stringify({
          ticket_id: ticketId,
          recommendation_type: "similar_ticket",
          ...payload,
        }),
      }),
    onSuccess: () => {
      notify("Resolution feedback recorded.", "success");
      qc.invalidateQueries({ queryKey: ["similar-resolved", ticketId] });
    },
  });

  const handleUploadAttachment = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await apiRequest(`/api/tickets/${ticketId}/attachments`, { method: "POST", body: fd });
      notify("Attachment uploaded.", "success");
      refreshTicket();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : "Attachment upload failed.", "error");
    }
  };

  const handleKbInsert = async (articleTitle: string, articleContent: string, recId?: number | null) => {
    setReplyVisibility("public");
    setReplyText((prev) => `${prev ? prev + "\n\n" : ""}Reference Guide — ${articleTitle}:\n${articleContent}`);
    if (recId) {
      try {
        await apiRequest(`/api/knowledge/recommendations/${recId}/feedback`, {
          method: "POST",
          body: JSON.stringify({ accepted: true }),
        });
      } catch {
        // non-blocking
      }
    }
    notify("Knowledge article inserted into reply editor.", "info");
  };

  if (isLoading) return <LoadingSkeleton rows={8} />;
  if (error || !ticket) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Ticket not found or inaccessible."}
        onRetry={() => refetch()}
      />
    );
  }

  const selectedCatObj = categories?.find((c) => String(c.id) === corrCatId);

  return (
    <div>
      {/* Breadcrumb & Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#E3E7E4]">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/tickets" className="btn-secondary inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[13px] font-semibold text-[#38685A]">
                {ticket.ticket_reference}
              </span>
              <StatusLabel status={ticket.status} />
              <PriorityIndicator priority={ticket.priority} />
              <VerificationBadge status={ticket.verification?.status || ticket.verification_status} />
              {ticket.is_demo_data && (
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-[#F5F6F4] border border-[#E3E7E4] text-[#78817D]">
                  Demo data
                </span>
              )}
            </div>
            <h1 className="text-[18px] font-semibold text-[#222C2A] mt-0.5 truncate">
              {ticket.subject}
            </h1>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {isStaff && ticket.status !== "resolved" && ticket.status !== "closed" && (
            <button className="btn-primary" onClick={() => closeMutation.mutate()}>
              Mark resolved
            </button>
          )}
          {(ticket.status === "resolved" || ticket.status === "closed") && (
            <button className="btn-secondary" onClick={() => setShowReopen((v) => !v)}>
              Reopen ticket
            </button>
          )}
        </div>
      </div>

      {showReopen && (
        <div className="surface-card p-4 mb-4 bg-[#FCF7F7] border-[#E7C6C6]">
          <div className="text-[13px] font-medium text-[#222C2A] mb-2">
            Provide a reason for reopening this ticket
          </div>
          <div className="flex gap-2">
            <input
              value={reopenReason}
              onChange={(e) => setReopenReason(e.target.value)}
              placeholder="Explain why the issue requires further attention..."
              className="field-input"
            />
            <button
              className="btn-primary shrink-0"
              disabled={reopenReason.trim().length < 3 || reopenMutation.isPending}
              onClick={() => reopenMutation.mutate()}
            >
              Confirm reopen
            </button>
          </div>
        </div>
      )}

      {/* Three-Column Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT COLUMN — Ticket Information */}
        <div className="lg:col-span-3 space-y-4">
          <div className="surface-card p-4 space-y-3">
            <div className="text-[13px] font-semibold text-[#222C2A] border-b border-[#E3E7E4] pb-2">
              Ticket Details
            </div>

            <div className="space-y-2.5 text-[12.5px]">
              <div>
                <div className="text-[#78817D]">Customer</div>
                <div className="font-medium text-[#222C2A]">{ticket.customer?.name}</div>
                <div className="text-[#78817D] text-[12px]">{ticket.customer?.email}</div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <div className="text-[#78817D]">Created</div>
                  <div>{formatShortDate(ticket.created_at)}</div>
                </div>
                <div>
                  <div className="text-[#78817D]">Source</div>
                  <div className="capitalize">{ticket.source.replace("_", " ")}</div>
                </div>
              </div>

              {ticket.product_reference && (
                <div>
                  <div className="text-[#78817D]">Product / Reference</div>
                  <div className="font-medium">{ticket.product_reference}</div>
                </div>
              )}

              {/* Target Platform / Company & Verification Status (visible to Customer & Staff) */}
              <div className="pt-2 border-t border-[#E3E7E4] space-y-2">
                <div>
                  <div className="text-[#78817D]">Target Company / Portal</div>
                  <div className="font-medium text-[#222C2A]">
                    {ticket.company?.name || ticket.company_name || "General Support"}
                  </div>
                  {(ticket.platform_type || ticket.company?.platform_type) && (
                    <div className="text-[11.5px] text-[#78817D]">
                      {ticket.platform_type || ticket.company?.platform_type}
                    </div>
                  )}
                </div>
                {ticket.external_reference && (
                  <div>
                    <div className="text-[#78817D]">External Order / Ref ID</div>
                    <div className="font-mono text-[12px] font-medium text-[#222C2A]">
                      {ticket.external_reference}
                    </div>
                  </div>
                )}
                <div>
                  <div className="text-[#78817D] mb-1">QRYVANTA Verification</div>
                  <VerificationBadge status={ticket.verification?.status || ticket.verification_status} />
                  {ticket.verification?.company_case_reference && (
                    <div className="text-[11.5px] text-[#78817D] mt-1">
                      Company Case: <span className="font-mono text-[#222C2A]">{ticket.verification.company_case_reference}</span>
                    </div>
                  )}
                  {ticket.verification?.recommended_company_action && (
                    <div className="text-[11.5px] text-[#38685A] bg-[#F0F4F2] border border-[#D3DFDA] rounded p-2 mt-1.5">
                      <strong>Verified Action:</strong> {ticket.verification.recommended_company_action}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <div className="text-[#78817D]">Category</div>
                <div className="font-medium">
                  {ticket.category_name || "Uncategorized"}
                  {ticket.subcategory_name ? ` / ${ticket.subcategory_name}` : ""}
                </div>
              </div>

              <div>
                <div className="text-[#78817D]">Department</div>
                {isStaff ? (
                  <select
                    value={ticket.department_id ? String(ticket.department_id) : ""}
                    onChange={(e) =>
                      updateMutation.mutate({
                        department_id: Number(e.target.value),
                        override_reason: "Department updated from ticket detail workspace.",
                      })
                    }
                    className="field-input mt-1"
                  >
                    <option value="">Manual triage</option>
                    {departments?.map((d) => (
                      <option key={d.department_id} value={String(d.department_id)}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="font-medium">{ticket.department_name || "Support triage"}</div>
                )}
              </div>

              {isStaff && (
                <>
                  <div>
                    <div className="text-[#78817D]">Status</div>
                    <select
                      value={ticket.status}
                      onChange={(e) => updateMutation.mutate({ status: e.target.value })}
                      className="field-input mt-1"
                    >
                      <option value="new">New</option>
                      <option value="open">Open</option>
                      <option value="in_progress">In progress</option>
                      <option value="awaiting_customer">Awaiting customer</option>
                      <option value="reopened">Reopened</option>
                      <option value="resolved">Resolved</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>

                  <div>
                    <div className="text-[#78817D]">Priority</div>
                    <select
                      value={ticket.priority}
                      onChange={(e) =>
                        updateMutation.mutate({
                          priority: e.target.value,
                          priority_override_reason: "Staff priority adjustment in ticket workspace.",
                        })
                      }
                      className="field-input mt-1"
                    >
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                  </div>

                  <div>
                    <div className="text-[#78817D]">Assigned agent</div>
                    <select
                      value={ticket.assigned_agent?.id ? String(ticket.assigned_agent.id) : ""}
                      onChange={(e) => {
                        if (e.target.value) {
                          assignMutation.mutate({
                            agent_id: Number(e.target.value),
                            reason: "Manual assignment in ticket workspace.",
                          });
                        }
                      }}
                      className="field-input mt-1"
                    >
                      <option value="">Unassigned</option>
                      {agents?.map((a) => (
                        <option key={a.agent_id} value={String(a.agent_id)}>
                          {a.name} ({a.open_tickets}/{a.max_open_tickets})
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Attachments */}
          <div className="surface-card p-4 space-y-2.5">
            <div className="flex items-center justify-between border-b border-[#E3E7E4] pb-2">
              <span className="text-[13px] font-semibold text-[#222C2A]">Attachments</span>
              <label className="text-[12px] text-[#38685A] cursor-pointer hover:underline inline-flex items-center gap-1">
                <Paperclip className="w-3.5 h-3.5" />
                Add file
                <input type="file" className="hidden" onChange={handleUploadAttachment} />
              </label>
            </div>
            {ticket.attachments.length === 0 ? (
              <div className="text-[12px] text-[#78817D]">No attachments uploaded.</div>
            ) : (
              <ul className="space-y-1.5 text-[12.5px]">
                {ticket.attachments.map((att) => (
                  <li key={att.id} className="flex items-center justify-between gap-2">
                    <button
                      onClick={() =>
                        apiDownloadBlob(
                          `/api/tickets/${ticket.id}/attachments/${att.id}`,
                          att.original_filename
                        )
                      }
                      className="text-[#38685A] hover:underline truncate text-left"
                    >
                      {att.original_filename}
                    </button>
                    <span className="text-[11px] text-[#78817D] shrink-0">
                      {(att.file_size / 1024).toFixed(1)} KB
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Customer Satisfaction Feedback */}
          {(ticket.status === "resolved" || ticket.status === "closed") && !isStaff && (
            <div className="surface-card p-4 space-y-2.5">
              <div className="text-[13px] font-semibold text-[#222C2A]">Rate resolution</div>
              {ticket.satisfaction_rating ? (
                <div className="text-[12.5px] text-[#38685A]">
                  Rated {ticket.satisfaction_rating}/5
                  {ticket.satisfaction_comment && (
                    <p className="text-[#78817D] mt-1">{ticket.satisfaction_comment}</p>
                  )}
                </div>
              ) : (
                <>
                  <select
                    value={ratingVal}
                    onChange={(e) => setRatingVal(Number(e.target.value))}
                    className="field-input"
                  >
                    <option value={5}>5 — Very satisfied</option>
                    <option value={4}>4 — Satisfied</option>
                    <option value={3}>3 — Neutral</option>
                    <option value={2}>2 — Unsatisfied</option>
                    <option value={1}>1 — Very unsatisfied</option>
                  </select>
                  <textarea
                    rows={2}
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    placeholder="Optional feedback..."
                    className="field-input"
                  />
                  <button className="btn-primary w-full" onClick={() => rateMutation.mutate()}>
                    Submit rating
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* CENTRE COLUMN — Conversation & Timeline */}
        <div className={`${isStaff ? "lg:col-span-5" : "lg:col-span-9"} space-y-4`}>
          <div className="surface-card p-4">
            <div className="text-[12px] font-medium text-[#78817D] mb-1">Original request</div>
            <p className="text-[13.5px] text-[#222C2A] whitespace-pre-wrap leading-relaxed">
              {ticket.description}
            </p>
          </div>

          <div className="surface-card p-4 space-y-3">
            <div className="text-[13px] font-semibold text-[#222C2A] border-b border-[#E3E7E4] pb-2">
              Conversation ({ticket.messages.length})
            </div>

            {ticket.messages.length === 0 ? (
              <div className="text-[12.5px] text-[#78817D] py-4 text-center">
                No replies yet.
              </div>
            ) : (
              <div className="space-y-3">
                {ticket.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`p-3.5 rounded border text-[13px] ${
                      msg.visibility === "internal"
                        ? "bg-[#FBF8F1] border-[#E8D7BC]"
                        : msg.sender_role === "customer"
                        ? "bg-[#FAFBF9] border-[#E3E7E4]"
                        : "bg-white border-[#D3DFDA]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[#222C2A]">{msg.sender_name}</span>
                        <span className="text-[11px] text-[#78817D] capitalize">{msg.sender_role}</span>
                        {msg.visibility === "internal" && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#9A6D2E] bg-[#F5EBDA] px-1.5 py-0.5 rounded">
                            <Lock className="w-3 h-3" />
                            Internal note (private)
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-[#78817D]">
                        {new Date(msg.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap text-[#222C2A]">{msg.message}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Reply Editor */}
            {ticket.status !== "closed" && (
              <div className="pt-3 border-t border-[#E3E7E4] space-y-2.5">
                {isStaff && (
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => setReplyVisibility("public")}
                        className={`px-2.5 py-1 text-[12px] rounded border ${
                          replyVisibility === "public"
                            ? "bg-[#38685A] text-white border-[#38685A]"
                            : "bg-white text-[#222C2A] border-[#E3E7E4]"
                        }`}
                      >
                        Public reply
                      </button>
                      <button
                        type="button"
                        onClick={() => setReplyVisibility("internal")}
                        className={`px-2.5 py-1 text-[12px] rounded border inline-flex items-center gap-1 ${
                          replyVisibility === "internal"
                            ? "bg-[#C08A3E] text-white border-[#C08A3E]"
                            : "bg-white text-[#222C2A] border-[#E3E7E4]"
                        }`}
                      >
                        <Lock className="w-3 h-3" />
                        Internal note
                      </button>
                    </div>

                    {replyVisibility === "public" && (
                      <select
                        value={replyStatus}
                        onChange={(e) => setReplyStatus(e.target.value)}
                        className="field-input w-44"
                      >
                        <option value="">Keep current status</option>
                        <option value="in_progress">Set In progress</option>
                        <option value="awaiting_customer">Set Awaiting customer</option>
                        <option value="resolved">Set Resolved</option>
                      </select>
                    )}
                  </div>
                )}

                <textarea
                  rows={4}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder={
                    replyVisibility === "internal"
                      ? "Write a private internal note (never visible to customers)..."
                      : "Write your response..."
                  }
                  className="field-input"
                />

                <div className="flex justify-end">
                  <button
                    className="btn-primary"
                    disabled={!replyText.trim() || replyMutation.isPending}
                    onClick={() => replyMutation.mutate()}
                  >
                    {replyVisibility === "internal" ? "Save internal note" : "Send reply"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Activity History */}
          <div className="surface-card p-4">
            <div className="text-[13px] font-semibold text-[#222C2A] border-b border-[#E3E7E4] pb-2 mb-2.5">
              Status & Event History
            </div>
            <ul className="space-y-2 text-[12px]">
              {ticket.events.map((ev) => (
                <li key={ev.id} className="flex justify-between gap-2 text-[#78817D]">
                  <span className="text-[#222C2A]">{ev.event_description}</span>
                  <span className="shrink-0">{new Date(ev.created_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* RIGHT COLUMN — Intelligence, Verification Handoff, SLA, Similar Tickets, KB, Agent Recommendations (Staff only) */}
        {isStaff && (
          <div className="lg:col-span-4 space-y-4">
            {/* QRYVANTA Verification & Company Handoff Brief */}
            <div className="surface-card p-4 space-y-2.5 border-[#C9DBD3]">
              <div className="flex items-center justify-between border-b border-[#E3E7E4] pb-2">
                <span className="text-[13px] font-semibold text-[#222C2A] inline-flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#38685A]" />
                  Verification & Company Handoff
                </span>
                <button
                  className="text-[12px] text-[#38685A] hover:underline font-medium"
                  onClick={() => {
                    setVerifyStatus(ticket.verification?.status || "verified_ready");
                    setVerifyNotes(ticket.verification?.notes || "");
                    setVerifyAction(ticket.verification?.recommended_company_action || "");
                    setVerifyCompanyRef(ticket.verification?.company_case_reference || "");
                    setShowVerifyForm((v) => !v);
                  }}
                >
                  {showVerifyForm ? "Cancel" : "Verify / Report"}
                </button>
              </div>

              <div className="text-[12px] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[#78817D]">Handoff stage</span>
                  <VerificationBadge status={ticket.verification?.status || ticket.verification_status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Target company</span>
                  <span className="font-medium">{ticket.company?.name || "General"}</span>
                </div>
                {ticket.external_reference && (
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">External Ref ID</span>
                    <span className="font-mono">{ticket.external_reference}</span>
                  </div>
                )}
                {ticket.verification?.notes && (
                  <div className="bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2 text-[#222C2A]">
                    <div className="text-[11px] text-[#78817D] mb-0.5">Verified findings</div>
                    {ticket.verification.notes}
                  </div>
                )}
                {ticket.verification?.recommended_company_action && (
                  <div className="bg-[#F0F4F2] border border-[#D3DFDA] rounded p-2 text-[#222C2A]">
                    <div className="text-[11px] text-[#38685A] font-medium mb-0.5">Direct action for company</div>
                    {ticket.verification.recommended_company_action}
                  </div>
                )}
              </div>

              {showVerifyForm && (
                <div className="pt-2.5 border-t border-[#E3E7E4] space-y-2 bg-[#FAFBF9] p-3 rounded">
                  <select
                    value={verifyStatus}
                    onChange={(e) => setVerifyStatus(e.target.value)}
                    className="field-input"
                  >
                    <option value="under_verification">Under verification</option>
                    <option value="verified_ready">Verified — ready for company</option>
                    <option value="reported_to_company">Reported to company</option>
                    <option value="company_acknowledged">Company acknowledged</option>
                    <option value="company_resolved">Company resolved</option>
                    <option value="insufficient_proof">Insufficient proof (ask customer)</option>
                  </select>
                  <textarea
                    rows={2}
                    value={verifyNotes}
                    onChange={(e) => setVerifyNotes(e.target.value)}
                    placeholder="Verification findings (e.g., confirmed return tracking delivered & duplicate charge on invoice) *"
                    className="field-input"
                  />
                  <textarea
                    rows={2}
                    value={verifyAction}
                    onChange={(e) => setVerifyAction(e.target.value)}
                    placeholder="Recommended direct action so company can proceed immediately (e.g., Approve $149 refund for ORD-99210)..."
                    className="field-input"
                  />
                  <input
                    value={verifyCompanyRef}
                    onChange={(e) => setVerifyCompanyRef(e.target.value)}
                    placeholder="Company case reference ID (optional)"
                    className="field-input"
                  />
                  <button
                    className="btn-primary w-full"
                    disabled={verifyNotes.trim().length < 5 || verifyMutation.isPending}
                    onClick={() => verifyMutation.mutate()}
                  >
                    Save verification & handoff status
                  </button>
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <button className="btn-secondary flex-1 text-[12px]" onClick={handlePreviewCompanyReport}>
                  Preview brief
                </button>
                <button
                  className="btn-secondary flex-1 text-[12px] inline-flex items-center justify-center gap-1"
                  onClick={handleDownloadCompanyReport}
                >
                  <FileDown className="w-3.5 h-3.5" />
                  Export brief
                </button>
              </div>

              {handoffPreview && (
                <div className="mt-2 bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2.5">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[11px] font-semibold text-[#38685A]">Company Handoff Dossier</span>
                    <button className="text-[11px] text-[#78817D] hover:underline" onClick={() => setHandoffPreview(null)}>
                      Hide
                    </button>
                  </div>
                  <pre className="text-[11px] whitespace-pre-wrap font-mono text-[#222C2A] max-h-56 overflow-y-auto">
                    {handoffPreview}
                  </pre>
                </div>
              )}
            </div>

            {/* SLA & Breach Risk Card */}
            {ticket.sla && (
              <div className="surface-card p-4 space-y-2.5">
                <div className="flex items-center justify-between border-b border-[#E3E7E4] pb-2">
                  <span className="text-[13px] font-semibold text-[#222C2A]">SLA & Breach Risk</span>
                  <div className="flex items-center gap-1.5">
                    <SLAIndicator state={ticket.sla.current_state} />
                    {ticket.sla_risk && <RiskBadge level={ticket.sla_risk.risk_level} />}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[12px]">
                  <div>
                    <div className="text-[#78817D]">Policy</div>
                    <div className="font-medium">{ticket.sla.policy_name || "Default"}</div>
                  </div>
                  <div>
                    <div className="text-[#78817D]">Remaining</div>
                    <div className="font-medium">{formatMinutes(ticket.sla.time_remaining_minutes)}</div>
                  </div>
                  <div>
                    <div className="text-[#78817D]">First response time</div>
                    <div>{formatMinutes(ticket.sla.first_response_time_minutes)}</div>
                  </div>
                  <div>
                    <div className="text-[#78817D]">Resolution deadline</div>
                    <div>{ticket.sla.resolution_deadline ? new Date(ticket.sla.resolution_deadline).toLocaleString() : "—"}</div>
                  </div>
                </div>
                {ticket.sla_risk && (
                  <div className="bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2.5 text-[12px] space-y-1">
                    <div className="flex justify-between text-[11px] text-[#78817D]">
                      <span>Risk score: {ticket.sla_risk.risk_score}/100</span>
                      <span>Rule-based estimate</span>
                    </div>
                    <ul className="list-disc pl-4 text-[#222C2A] space-y-0.5">
                      {ticket.sla_risk.factors.slice(0, 3).map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                    <div className="text-[#38685A] font-medium pt-0.5">
                      Action: {ticket.sla_risk.recommended_action}
                    </div>
                  </div>
                )}
                {ticket.sla.escalated && (
                  <div className="text-[12px] text-[#B84C4C] bg-[#FCF7F7] border border-[#E7C6C6] rounded px-2.5 py-1.5">
                    Escalated: {ticket.sla.escalation_notes}
                  </div>
                )}
              </div>
            )}

            {/* Customer Impact & Linked Incidents Panel */}
            {ticket.customer_impact && (
              <CollapsiblePanel
                title="Customer Impact"
                badge={
                  <span className="text-[11px] text-[#78817D]">
                    {ticket.customer_impact.unique_affected_customers} customer(s)
                  </span>
                }
                defaultOpen={true}
              >
                <div className="space-y-2.5 text-[12px]">
                  <div className="grid grid-cols-3 gap-2 text-center bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2">
                    <div>
                      <div className="text-[15px] font-semibold text-[#222C2A]">
                        {ticket.customer_impact.unique_affected_customers}
                      </div>
                      <div className="text-[10.5px] text-[#78817D]">Unique affected</div>
                    </div>
                    <div>
                      <div className="text-[15px] font-semibold text-[#C08A3E]">
                        {ticket.customer_impact.customer_unresolved_tickets}
                      </div>
                      <div className="text-[10.5px] text-[#78817D]">Cust. open</div>
                    </div>
                    <div>
                      <div className="text-[15px] font-semibold text-[#38685A]">
                        {ticket.customer_impact.customer_total_tickets}
                      </div>
                      <div className="text-[10.5px] text-[#78817D]">Cust. total</div>
                    </div>
                  </div>
                  <p className="text-[#78817D]">{ticket.customer_impact.summary_note}</p>

                  {ticket.customer_impact.linked_incidents.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <div className="text-[11px] font-medium text-[#78817D]">Linked Incidents</div>
                      {ticket.customer_impact.linked_incidents.map((inc) => (
                        <Link
                          key={inc.id}
                          to="/incidents"
                          className="block border border-[#E7C6C6] bg-[#FCF7F7] rounded p-2 hover:bg-[#FAF0F0]"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-mono text-[11.5px] font-semibold text-[#B84C4C]">
                              {inc.incident_reference}
                            </span>
                            <IncidentStatusBadge status={inc.status} />
                          </div>
                          <div className="text-[#222C2A] font-medium truncate mt-0.5">{inc.title}</div>
                          <div className="text-[11px] text-[#78817D]">
                            {inc.affected_customer_count} unique customers · {inc.ticket_count} tickets
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}

                  {ticket.customer_impact.customer_prior_history.length > 0 && (
                    <div className="space-y-1 pt-1">
                      <div className="text-[11px] font-medium text-[#78817D]">Customer's Recent History</div>
                      {ticket.customer_impact.customer_prior_history.slice(0, 3).map((h) => (
                        <div key={h.id} className="flex justify-between gap-2 text-[11.5px]">
                          <Link to={`/tickets/${h.id}`} className="text-[#38685A] hover:underline truncate">
                            {h.ticket_reference}: {h.subject}
                          </Link>
                          <span className="text-[#78817D] shrink-0 capitalize">{h.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CollapsiblePanel>
            )}

            {/* Resolution Intelligence — Similar Resolved Tickets */}
            <CollapsiblePanel
              title="Resolution Intelligence"
              badge={
                <span className="text-[11px] text-[#78817D]">
                  {resolvedSimilarData?.similar_resolved.length ?? 0} match(es)
                </span>
              }
              defaultOpen={true}
            >
              {!resolvedSimilarData || resolvedSimilarData.similar_resolved.length === 0 ? (
                <div className="text-[12px] text-[#78817D]">
                  No similar previously resolved tickets with verified staff resolutions matched this issue yet.
                </div>
              ) : (
                <div className="space-y-2.5 text-[12px]">
                  {resolvedSimilarData.similar_resolved.slice(0, 3).map((res) => (
                    <div key={res.source_ticket_id} className="border border-[#E3E7E4] rounded p-2.5 space-y-1.5">
                      <div className="flex justify-between gap-2">
                        <Link to={`/tickets/${res.source_ticket_id}`} className="font-mono text-[#38685A] font-medium hover:underline">
                          {res.ticket_reference}
                        </Link>
                        <span className="text-[#78817D]">
                          {(res.similarity_score * 100).toFixed(0)}% similar
                        </span>
                      </div>
                      <div className="font-medium text-[#222C2A] line-clamp-1">{res.subject}</div>
                      <div className="bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2 text-[#222C2A] line-clamp-3">
                        <div className="text-[10.5px] text-[#78817D] mb-0.5">Actual historical resolution:</div>
                        {res.actual_resolution}
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1">
                        <button
                          className="btn-secondary py-0.5 px-2 text-[11px]"
                          onClick={() => {
                            setReplyVisibility("public");
                            setReplyText((prev) =>
                              `${prev ? prev + "\n\n" : ""}${res.actual_resolution}`
                            );
                            resolutionFeedbackMutation.mutate({
                              source_ticket_id: res.source_ticket_id,
                              rating: "helpful",
                              applied_to_reply: true,
                            });
                          }}
                        >
                          Use in reply
                        </button>
                        <div className="flex gap-1">
                          {(
                            [
                              ["helpful", "Helpful"],
                              ["partially_helpful", "Partial"],
                              ["not_helpful", "Not helpful"],
                            ] as const
                          ).map(([val, lbl]) => (
                            <button
                              key={val}
                              className="text-[11px] px-1.5 py-0.5 border border-[#E3E7E4] rounded hover:bg-[#F5F6F4] text-[#78817D]"
                              onClick={() =>
                                resolutionFeedbackMutation.mutate({
                                  source_ticket_id: res.source_ticket_id,
                                  rating: val,
                                  applied_to_reply: false,
                                })
                              }
                            >
                              {lbl}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CollapsiblePanel>

            {/* Classification & Priority Intelligence */}
            <div className="surface-card p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-[#E3E7E4] pb-2">
                <span className="text-[13px] font-semibold text-[#222C2A]">
                  Classification & Routing
                </span>
                <button
                  className="text-[12px] text-[#38685A] hover:underline font-medium"
                  onClick={() => {
                    setCorrCatId(ticket.category_id ? String(ticket.category_id) : "");
                    setCorrDeptId(ticket.department_id ? String(ticket.department_id) : "");
                    setCorrPriority(ticket.priority);
                    setShowCorrect((v) => !v);
                  }}
                >
                  {showCorrect ? "Cancel correction" : "Correct prediction"}
                </button>
              </div>

              {ticket.prediction ? (
                <div className="space-y-2 text-[12.5px]">
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Predicted category</span>
                    <span className="font-medium">{ticket.prediction.predicted_category_name || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Subcategory</span>
                    <span className="font-medium">{ticket.prediction.predicted_subcategory_name || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Confidence</span>
                    <span className="font-semibold text-[#38685A]">
                      {(ticket.prediction.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Suggested department</span>
                    <span>{ticket.prediction.suggested_department_name || "Manual triage"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Routing decision</span>
                    <span className="capitalize">{ticket.prediction.routing_decision?.replace("_", " ")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#78817D]">Model version</span>
                    <span className="font-mono text-[11.5px]">{ticket.prediction.model_version}</span>
                  </div>

                  {ticket.prediction.explanation && (
                    <div className="text-[12px] text-[#78817D] bg-[#FAFBF9] border border-[#E3E7E4] rounded p-2.5">
                      {ticket.prediction.explanation}
                    </div>
                  )}

                  {ticket.prediction.alternative_predictions.length > 0 && (
                    <div>
                      <div className="text-[11.5px] text-[#78817D] mb-1">Alternative categories</div>
                      <div className="space-y-1">
                        {ticket.prediction.alternative_predictions.map((alt) => (
                          <div key={alt.category} className="flex justify-between text-[12px]">
                            <span>{alt.category}</span>
                            <span className="text-[#78817D]">{(alt.confidence * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-[12.5px] text-[#78817D]">No stored prediction record.</div>
              )}

              {/* Priority Rationale & Supporting Sentiment */}
              <div className="pt-2 border-t border-[#E3E7E4] space-y-1.5 text-[12px]">
                <div className="text-[#78817D] font-medium">Urgency rationale (independent of category)</div>
                <p className="text-[#222C2A]">{ticket.priority_reason || "Standard priority."}</p>
                {ticket.sentiment?.label && (
                  <div className="text-[#78817D] pt-1">
                    Supporting sentiment: <strong className="capitalize text-[#222C2A]">{ticket.sentiment.label}</strong>{" "}
                    ({ticket.sentiment.method?.replace(/_/g, " ")}; trend: {ticket.sentiment_trend?.trend || "stable"})
                  </div>
                )}
              </div>

              {/* Human-in-the-Loop Correction Form */}
              {showCorrect && (
                <div className="pt-3 border-t border-[#E3E7E4] space-y-2.5 bg-[#FAFBF9] p-3 rounded">
                  <div className="text-[12.5px] font-semibold text-[#222C2A]">
                    Submit Human-in-the-Loop Correction
                  </div>
                  <select
                    value={corrCatId}
                    onChange={(e) => { setCorrCatId(e.target.value); setCorrSubId(""); }}
                    className="field-input"
                  >
                    <option value="">Select correct category *</option>
                    {categories?.map((c) => (
                      <option key={c.id} value={String(c.id)}>{c.name}</option>
                    ))}
                  </select>
                  {selectedCatObj && selectedCatObj.subcategories.length > 0 && (
                    <select
                      value={corrSubId}
                      onChange={(e) => setCorrSubId(e.target.value)}
                      className="field-input"
                    >
                      <option value="">Select subcategory (optional)</option>
                      {selectedCatObj.subcategories.map((s) => (
                        <option key={s.id} value={String(s.id)}>{s.name}</option>
                      ))}
                    </select>
                  )}
                  <select
                    value={corrDeptId}
                    onChange={(e) => setCorrDeptId(e.target.value)}
                    className="field-input"
                  >
                    <option value="">Keep / select department</option>
                    {departments?.map((d) => (
                      <option key={d.department_id} value={String(d.department_id)}>{d.name}</option>
                    ))}
                  </select>
                  <select
                    value={corrPriority}
                    onChange={(e) => setCorrPriority(e.target.value)}
                    className="field-input"
                  >
                    <option value="">Keep priority</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                  <textarea
                    rows={2}
                    value={corrReason}
                    onChange={(e) => setCorrReason(e.target.value)}
                    placeholder="Reason for correction (required for model feedback audit)..."
                    className="field-input"
                  />
                  <button
                    className="btn-primary w-full"
                    disabled={!corrCatId || corrReason.trim().length < 3 || reclassifyMutation.isPending}
                    onClick={() => reclassifyMutation.mutate()}
                  >
                    Save correction
                  </button>
                </div>
              )}

              {ticket.feedback_history && ticket.feedback_history.length > 0 && (
                <div className="pt-2 border-t border-[#E3E7E4] text-[12px] space-y-1">
                  <div className="font-medium text-[#222C2A]">Recorded corrections</div>
                  {ticket.feedback_history.map((fb) => (
                    <div key={fb.id} className="text-[#78817D]">
                      {fb.corrected_by_name}: {fb.corrected_category_name} — "{fb.correction_reason}"
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Agent Recommendations (Collapsible) */}
            <CollapsiblePanel title="Recommended Agents (Workload Rules)" defaultOpen={false}>
              {!ticket.recommended_agents || ticket.recommended_agents.length === 0 ? (
                <div className="text-[12px] text-[#78817D]">No eligible available agents in department.</div>
              ) : (
                <div className="space-y-2.5">
                  {ticket.recommended_agents.map((rec) => (
                    <div key={rec.agent_id} className="border border-[#E3E7E4] rounded p-2.5 text-[12px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-[#222C2A]">{rec.name}</span>
                        <button
                          className="btn-secondary py-0.5 px-2 text-[11.5px]"
                          onClick={() =>
                            assignMutation.mutate({ agent_id: rec.agent_id, reason: rec.reason })
                          }
                        >
                          Assign
                        </button>
                      </div>
                      <div className="text-[#78817D] mt-1">{rec.reason}</div>
                    </div>
                  ))}
                </div>
              )}
            </CollapsiblePanel>

            {/* Similar & Duplicate Tickets (Collapsible) */}
            <CollapsiblePanel
              title="Similar & Related Tickets"
              badge={<span className="text-[11px] text-[#78817D]">{similarData?.similar_tickets.length ?? 0}</span>}
              defaultOpen={false}
            >
              {ticket.confirmed_relations && ticket.confirmed_relations.length > 0 && (
                <div className="space-y-1.5 pb-2 mb-2 border-b border-[#E3E7E4]">
                  <div className="text-[11.5px] font-medium text-[#78817D]">Confirmed links</div>
                  {ticket.confirmed_relations.map((rel) => (
                    <div key={rel.id} className="text-[12px] flex items-center justify-between gap-2">
                      <Link to={`/tickets/${rel.other_ticket_id}`} className="text-[#38685A] hover:underline truncate">
                        {rel.other_ticket_reference}: {rel.other_ticket_subject}
                      </Link>
                      <span className="text-[11px] uppercase text-[#C08A3E] font-medium shrink-0">
                        {rel.relation_type}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {!similarData || similarData.similar_tickets.length === 0 ? (
                <div className="text-[12px] text-[#78817D]">
                  No tickets exceeded the TF-IDF cosine similarity threshold.
                </div>
              ) : (
                <div className="space-y-2">
                  {similarData.similar_tickets.map((sim) => (
                    <div key={sim.ticket_id} className="border border-[#E3E7E4] rounded p-2.5 text-[12px]">
                      <div className="flex justify-between gap-2">
                        <Link to={`/tickets/${sim.ticket_id}`} className="font-mono text-[#38685A] hover:underline">
                          {sim.ticket_reference}
                        </Link>
                        <span className="text-[#78817D]">{(sim.similarity_score * 100).toFixed(0)}% match</span>
                      </div>
                      <div className="text-[#222C2A] mt-0.5 line-clamp-1">{sim.subject}</div>
                      <div className="flex gap-2 mt-2">
                        <button
                          className="btn-secondary py-0.5 px-2 text-[11px]"
                          onClick={() =>
                            linkRelationMutation.mutate({
                              related_ticket_id: sim.ticket_id,
                              relation_type: "related",
                              similarity_score: sim.similarity_score,
                            })
                          }
                        >
                          Mark related
                        </button>
                        <button
                          className="btn-secondary py-0.5 px-2 text-[11px]"
                          onClick={() =>
                            linkRelationMutation.mutate({
                              related_ticket_id: sim.ticket_id,
                              relation_type: "duplicate",
                              similarity_score: sim.similarity_score,
                            })
                          }
                        >
                          Mark duplicate
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CollapsiblePanel>

            {/* Knowledge Base Recommendations (Collapsible) */}
            <CollapsiblePanel
              title={
                <>
                  <BookOpen className="w-3.5 h-3.5 text-[#38685A]" />
                  Knowledge Articles
                </>
              }
              badge={<span className="text-[11px] text-[#78817D]">{ticket.knowledge_recommendations?.length ?? 0}</span>}
              defaultOpen={false}
            >
              {!ticket.knowledge_recommendations || ticket.knowledge_recommendations.length === 0 ? (
                <div className="text-[12px] text-[#78817D]">No matching knowledge articles found.</div>
              ) : (
                <div className="space-y-2">
                  {ticket.knowledge_recommendations.map((kb) => (
                    <div key={kb.article_id} className="border border-[#E3E7E4] rounded p-2.5 text-[12px]">
                      <div className="font-medium text-[#222C2A]">{kb.title}</div>
                      <p className="text-[#78817D] line-clamp-2 mt-0.5">{kb.content}</p>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[11px] text-[#78817D]">
                          Relevance {(kb.relevance_score * 100).toFixed(0)}%
                        </span>
                        <button
                          className="text-[11.5px] text-[#38685A] font-medium hover:underline"
                          onClick={() => handleKbInsert(kb.title, kb.content, kb.recommendation_id)}
                        >
                          Insert into reply
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CollapsiblePanel>
          </div>
        )}
      </div>
    </div>
  );
}
