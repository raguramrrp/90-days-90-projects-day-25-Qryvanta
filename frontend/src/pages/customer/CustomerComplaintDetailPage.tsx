import React, { useState, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  Paperclip,
  Download,
  Send,
  Star,
  AlertCircle,
  Headphones,
  User,
} from "lucide-react";
import { apiDownloadBlob, apiRequest, ApiError } from "../../services/api";
import { useToast } from "../../hooks/useToast";
import type { TicketDetail } from "../../types";
import {
  PROGRESS_STEPS,
  formatDateTime,
  formatShortDate,
  getCustomerStatusInfo,
} from "../../utils/customerStatus";

const MAX_ATTACHMENT_MB = 5;
const ACCEPTED_EXTENSIONS = ".png,.jpg,.jpeg,.pdf,.txt,.csv,.docx,.log";

export function CustomerComplaintDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const replyTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const attachInputRef = useRef<HTMLInputElement | null>(null);

  const [replyText, setReplyText] = useState("");
  const [replyFile, setReplyFile] = useState<File | null>(null);
  const [sendingReply, setSendingReply] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  const [ratingValue, setRatingValue] = useState<number>(0);
  const [ratingComment, setRatingComment] = useState("");
  const [submittingRating, setSubmittingRating] = useState(false);

  const [showReopenForm, setShowReopenForm] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [reopening, setReopening] = useState(false);

  const {
    data: complaint,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["customer-complaint", id],
    queryFn: () => apiRequest<TicketDetail>(`/api/tickets/${id}`),
    enabled: Boolean(id),
  });

  const refreshComplaint = () => {
    queryClient.invalidateQueries({ queryKey: ["customer-complaint", id] });
    queryClient.invalidateQueries({ queryKey: ["customer-complaints"] });
    queryClient.invalidateQueries({ queryKey: ["customer-recent-complaints"] });
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!complaint) return;
    setReplyError(null);

    if (!replyText.trim() && !replyFile) {
      setReplyError("Please enter a message or attach a file before sending.");
      return;
    }

    setSendingReply(true);
    try {
      if (replyText.trim()) {
        await apiRequest(`/api/tickets/${complaint.id}/reply`, {
          method: "POST",
          body: JSON.stringify({
            message: replyText.trim(),
            visibility: "public",
          }),
        });
      }

      if (replyFile) {
        const fd = new FormData();
        fd.append("file", replyFile);
        await apiRequest(`/api/tickets/${complaint.id}/attachments`, {
          method: "POST",
          body: fd,
        });
      }

      setReplyText("");
      setReplyFile(null);
      if (attachInputRef.current) attachInputRef.current.value = "";
      refreshComplaint();
      notify("Your message has been sent to our support team.", "success");
    } catch (err) {
      setReplyError(
        err instanceof ApiError
          ? err.message
          : "We could not send your reply right now. Please try again."
      );
    } finally {
      setSendingReply(false);
    }
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    setReplyError(null);
    const file = e.target.files?.[0] || null;
    if (!file) {
      setReplyFile(null);
      return;
    }
    if (file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      setReplyError(
        `This file exceeds the ${MAX_ATTACHMENT_MB} MB limit. Please choose a smaller file.`
      );
      if (attachInputRef.current) attachInputRef.current.value = "";
      return;
    }
    setReplyFile(file);
  };

  const handleSubmitRating = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!complaint || ratingValue < 1) return;
    setSubmittingRating(true);
    try {
      await apiRequest(`/api/tickets/${complaint.id}/rate`, {
        method: "POST",
        body: JSON.stringify({
          rating: ratingValue,
          comment: ratingComment.trim() || undefined,
        }),
      });
      refreshComplaint();
      notify("Thank you for sharing your feedback.", "success");
    } catch (err) {
      notify(
        err instanceof ApiError ? err.message : "Could not save your rating.",
        "error"
      );
    } finally {
      setSubmittingRating(false);
    }
  };

  const handleReopen = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!complaint || reopenReason.trim().length < 5) return;
    setReopening(true);
    try {
      await apiRequest(`/api/tickets/${complaint.id}/reopen`, {
        method: "POST",
        body: JSON.stringify({ reason: reopenReason.trim() }),
      });
      setReopenReason("");
      setShowReopenForm(false);
      refreshComplaint();
      notify("Your complaint has been reopened for our support team.", "success");
    } catch (err) {
      notify(
        err instanceof ApiError
          ? err.message
          : "Could not reopen this complaint.",
        "error"
      );
    } finally {
      setReopening(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="h-6 w-40 bg-[#E6EBE8] rounded-md animate-pulse" />
        <div className="h-44 surface-card animate-pulse" />
        <div className="h-56 surface-card animate-pulse" />
      </div>
    );
  }

  if (isError || !complaint) {
    return (
      <div className="max-w-3xl mx-auto surface-card p-8 text-center space-y-3">
        <h1 className="text-[19px] font-bold text-[#1D2825]">
          Complaint not found
        </h1>
        <p className="text-[14px] text-[#556560]">
          We couldn&apos;t find this complaint or you don&apos;t have permission to view it.
        </p>
        <div className="pt-2">
          <Link to="/my-complaints" className="btn-primary inline-block px-4 py-2">
            Back to My Complaints
          </Link>
        </div>
      </div>
    );
  }

  const statusInfo = getCustomerStatusInfo(
    complaint.status,
    complaint.has_assigned_support
  );
  const publicMessages = (complaint.messages || []).filter(
    (m) => m.visibility !== "internal"
  );
  const isResolvedOrClosed =
    complaint.status === "resolved" || complaint.status === "closed";

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Link
        to="/my-complaints"
        className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-[#5A6964] hover:text-[#1D2825] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to My Complaints
      </Link>

      {/* Summary & 4-Step Progress Tracker */}
      <section className="surface-card p-6 sm:p-7 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="space-y-1.5">
            <div className="font-mono text-[13px] font-semibold text-[#2F6354]">
              {complaint.ticket_reference}
            </div>
            <h1 className="text-[23px] font-bold text-[#1D2825] leading-snug tracking-tight">
              {complaint.subject}
            </h1>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[#6E7C77] pt-0.5">
              <span>Submitted {formatShortDate(complaint.created_at)}</span>
              <span>
                Last updated{" "}
                {formatShortDate(complaint.updated_at || complaint.created_at)}
              </span>
            </div>
          </div>

          <span
            className={`self-start inline-block px-3 py-1 text-[12.5px] font-medium rounded-full border shrink-0 ${statusInfo.badgeClass}`}
          >
            {statusInfo.label}
          </span>
        </div>

        {/* Clean 4-Step Progress Timeline */}
        <div className="pt-5 border-t border-[#E6EBE8]">
          <ol
            aria-label="Complaint progress"
            className="grid grid-cols-1 sm:grid-cols-4 gap-3.5 sm:gap-2"
          >
            {PROGRESS_STEPS.map((step, index) => {
              const completed = index < statusInfo.stepIndex;
              const current = index === statusInfo.stepIndex;
              const isDoneStep =
                completed || (current && statusInfo.stepIndex === 3);
              return (
                <li
                  key={step.key}
                  className="flex sm:flex-col items-center sm:items-start gap-3 sm:gap-2.5"
                >
                  <div className="flex items-center w-auto sm:w-full gap-2">
                    <span
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0 border transition-all ${
                        isDoneStep
                          ? "bg-[#2F6354] border-[#2F6354] text-white shadow-[0_1px_3px_rgba(47,99,84,0.28)]"
                          : current
                          ? "bg-[#ECF4F1] border-[#2F6354] text-[#2F6354] ring-4 ring-[#2F6354]/10"
                          : "bg-white border-[#D4DDD8] text-[#8A9893]"
                      }`}
                    >
                      {isDoneStep ? <Check className="w-3.5 h-3.5" /> : index + 1}
                    </span>
                    {index < PROGRESS_STEPS.length - 1 && (
                      <div
                        className={`hidden sm:block h-[2.5px] flex-1 rounded-full ${
                          index < statusInfo.stepIndex
                            ? "bg-[#2F6354]"
                            : "bg-[#E4EAE6]"
                        }`}
                      />
                    )}
                  </div>
                  <span
                    className={`text-[13px] ${
                      completed || current
                        ? "font-semibold text-[#1D2825]"
                        : "text-[#7A8883]"
                    }`}
                  >
                    {step.label}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Plain-Language Status Explanation */}
        <div
          className={`rounded-[9px] px-4 py-3.5 border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            statusInfo.needsCustomerAction
              ? "bg-[#FEF7EC] border-[#ECD5B1]"
              : "bg-[#F8FAF9] border-[#E4EAE6]"
          }`}
        >
          <div className="flex items-start gap-2.5">
            {statusInfo.needsCustomerAction && (
              <AlertCircle className="w-4 h-4 text-[#9A651D] shrink-0 mt-0.5" />
            )}
            <p className="text-[13.5px] text-[#32403B] leading-relaxed">
              {statusInfo.shortDescription}
            </p>
          </div>
          {statusInfo.needsCustomerAction && (
            <button
              type="button"
              onClick={() => replyTextareaRef.current?.focus()}
              className="btn-primary px-4 py-2 text-[13px] shrink-0"
            >
              Reply now
            </button>
          )}
        </div>
      </section>

      {/* Complaint Details & Attachments */}
      <section className="surface-card p-6 sm:p-7 space-y-4">
        <h2 className="text-[16px] font-semibold text-[#1D2825]">
          Complaint Details
        </h2>

        <p className="text-[14.5px] text-[#2C3935] whitespace-pre-wrap leading-relaxed">
          {complaint.description}
        </p>

        {(complaint.external_reference || complaint.company?.name) && (
          <div className="pt-4 border-t border-[#E6EBE8] flex flex-wrap gap-x-8 gap-y-2 text-[13.5px]">
            {complaint.external_reference && (
              <div>
                <span className="text-[#6E7C77]">Order / Reference: </span>
                <span className="font-semibold text-[#1D2825] font-mono text-[13px]">
                  {complaint.external_reference}
                </span>
              </div>
            )}
            {complaint.company?.name && (
              <div>
                <span className="text-[#6E7C77]">Company: </span>
                <span className="font-semibold text-[#1D2825]">
                  {complaint.company.name}
                </span>
              </div>
            )}
          </div>
        )}

        {complaint.attachments && complaint.attachments.length > 0 && (
          <div className="pt-4 border-t border-[#E6EBE8] space-y-2.5">
            <div className="text-[13px] font-semibold text-[#556560]">
              Attachments
            </div>
            <div className="flex flex-wrap gap-2">
              {complaint.attachments.map((att) => (
                <button
                  key={att.id}
                  type="button"
                  onClick={() =>
                    apiDownloadBlob(
                      `/api/tickets/${complaint.id}/attachments/${att.id}`,
                      att.original_filename
                    )
                  }
                  className="inline-flex items-center gap-2 px-3.5 py-2 rounded-[8px] border border-[#DFE5E2] bg-[#F8FAF9] hover:bg-[#ECF4F1] hover:border-[#C5DDD3] text-[13px] font-medium text-[#1D2825] transition-colors cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5 text-[#2F6354]" />
                  <span>{att.original_filename}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Support Conversation */}
      <section className="surface-card p-6 sm:p-7 space-y-5">
        <h2 className="text-[16px] font-semibold text-[#1D2825]">
          Support Conversation
        </h2>

        {publicMessages.length === 0 ? (
          <p className="text-[14px] text-[#6E7C77] py-2">
            No replies yet. When our support team responds, their messages will appear here.
          </p>
        ) : (
          <div className="space-y-3.5">
            {publicMessages.map((msg) => {
              const isCustomer = msg.sender_role === "customer";
              return (
                <div
                  key={msg.id}
                  className={`rounded-[10px] p-4.5 border ${
                    isCustomer
                      ? "bg-[#F8FAF9] border-[#E4EAE6]"
                      : "bg-white border-[#CBE0D7] border-l-[3.5px] border-l-[#2F6354] shadow-[0_1px_4px_rgba(47,99,84,0.06)]"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[12.5px]">
                    <div className="inline-flex items-center gap-2">
                      <span
                        className={`w-6 h-6 rounded-full inline-flex items-center justify-center ${
                          isCustomer
                            ? "bg-[#E6ECE9] text-[#4C5C57]"
                            : "bg-[#ECF4F1] text-[#2F6354]"
                        }`}
                      >
                        {isCustomer ? (
                          <User className="w-3.5 h-3.5" />
                        ) : (
                          <Headphones className="w-3.5 h-3.5" />
                        )}
                      </span>
                      <span className="font-semibold text-[#1D2825]">
                        {isCustomer ? "You" : "Support Team"}
                      </span>
                    </div>
                    <span className="text-[#76847F]">
                      {formatDateTime(msg.created_at)}
                    </span>
                  </div>
                  <p className="mt-2.5 text-[14px] text-[#2C3935] whitespace-pre-wrap leading-relaxed pl-8">
                    {msg.message}
                  </p>
                </div>
              );
            })}
          </div>
        )}

        {/* Reply Input */}
        {complaint.status !== "closed" && (
          <form
            onSubmit={handleSendReply}
            className="pt-5 border-t border-[#E6EBE8] space-y-3"
          >
            <label
              htmlFor="customer-reply-input"
              className="block text-[14px] font-semibold text-[#1D2825]"
            >
              Send a reply
            </label>

            {replyError && (
              <div
                role="alert"
                className="px-3.5 py-2.5 rounded-[7px] border border-[#ECC5C5] bg-[#FEF5F5] text-[#B03E3E] text-[13px]"
              >
                {replyError}
              </div>
            )}

            <textarea
              ref={replyTextareaRef}
              id="customer-reply-input"
              rows={3}
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Write your reply or share any additional information..."
              className="field-input py-2.5 text-[14px] leading-relaxed"
            />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <label
                  htmlFor="reply-attachment"
                  className="btn-secondary inline-flex items-center gap-1.5 px-3.5 py-1.5 text-[13px] cursor-pointer"
                >
                  <Paperclip className="w-3.5 h-3.5 text-[#556560]" />
                  Attach file
                </label>
                <input
                  ref={attachInputRef}
                  id="reply-attachment"
                  type="file"
                  accept={ACCEPTED_EXTENSIONS}
                  onChange={handleFilePick}
                  className="sr-only"
                />
                {replyFile && (
                  <span className="text-[12.5px] text-[#556560] truncate max-w-[220px]">
                    {replyFile.name}
                  </span>
                )}
              </div>

              <button
                type="submit"
                disabled={sendingReply}
                className="btn-primary inline-flex items-center gap-2 px-4.5 py-2 text-[13.5px]"
              >
                <Send className="w-3.5 h-3.5" />
                {sendingReply ? "Sending..." : "Send reply"}
              </button>
            </div>
          </form>
        )}
      </section>

      {/* Resolution Feedback & Reopen */}
      {isResolvedOrClosed && (
        <section className="surface-card p-6 sm:p-7 space-y-5">
          {complaint.satisfaction_rating ? (
            <div>
              <h2 className="text-[16px] font-semibold text-[#1D2825]">
                Thank you for your feedback
              </h2>
              <p className="mt-1 text-[13.5px] text-[#556560]">
                You rated this resolution {complaint.satisfaction_rating} out of 5.
                {complaint.satisfaction_comment
                  ? ` "${complaint.satisfaction_comment}"`
                  : ""}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmitRating} className="space-y-3">
              <h2 className="text-[16px] font-semibold text-[#1D2825]">
                How was our support?
              </h2>
              <p className="text-[13.5px] text-[#556560]">
                Let us know how satisfied you are with how your complaint was handled.
              </p>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRatingValue(star)}
                    aria-label={`Rate ${star} out of 5`}
                    className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-[8px] border text-[13.5px] transition-colors cursor-pointer ${
                      ratingValue >= star
                        ? "border-[#2F6354] bg-[#ECF4F1] text-[#1E473B] font-semibold"
                        : "border-[#E1E6E3] bg-white text-[#556560] hover:bg-[#F8FAF9]"
                    }`}
                  >
                    <Star
                      className={`w-3.5 h-3.5 ${
                        ratingValue >= star ? "fill-[#2F6354] text-[#2F6354]" : ""
                      }`}
                    />
                    {star}
                  </button>
                ))}
              </div>
              {ratingValue > 0 && (
                <div className="space-y-2.5 pt-1">
                  <input
                    type="text"
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    placeholder="Add an optional comment about your experience"
                    className="field-input py-2 text-[13.5px]"
                  />
                  <button
                    type="submit"
                    disabled={submittingRating}
                    className="btn-primary px-4 py-2 text-[13.5px]"
                  >
                    {submittingRating ? "Submitting..." : "Submit feedback"}
                  </button>
                </div>
              )}
            </form>
          )}

          <div className="pt-4 border-t border-[#E6EBE8]">
            {!showReopenForm ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-[13.5px] text-[#556560]">
                  Is your issue still not fully resolved?
                </span>
                <button
                  type="button"
                  onClick={() => setShowReopenForm(true)}
                  className="btn-secondary px-4 py-2 text-[13.5px]"
                >
                  Reopen complaint
                </button>
              </div>
            ) : (
              <form onSubmit={handleReopen} className="space-y-3">
                <label
                  htmlFor="reopen-reason"
                  className="block text-[13.5px] font-semibold text-[#1D2825]"
                >
                  Tell us what still needs attention
                </label>
                <textarea
                  id="reopen-reason"
                  rows={2}
                  required
                  minLength={5}
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                  placeholder="Briefly explain why you need us to reopen this complaint..."
                  className="field-input py-2 text-[13.5px]"
                />
                <div className="flex items-center gap-2.5">
                  <button
                    type="submit"
                    disabled={reopening || reopenReason.trim().length < 5}
                    className="btn-primary px-4 py-2 text-[13.5px]"
                  >
                    {reopening ? "Reopening..." : "Confirm reopen"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowReopenForm(false)}
                    className="btn-secondary px-4 py-2 text-[13.5px]"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
