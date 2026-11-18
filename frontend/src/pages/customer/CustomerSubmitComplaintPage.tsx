import React, { useState, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  Paperclip,
  X,
  CreditCard,
  ShoppingBag,
  RotateCcw,
  Truck,
  KeyRound,
  Package,
  MessageSquare,
  Check,
} from "lucide-react";
import { apiRequest, ApiError } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import type { CategoryItem, CompanyItem, TicketDetail } from "../../types";
import {
  CUSTOMER_ISSUE_OPTIONS,
  formatDateTime,
  getCustomerStatusInfo,
  matchBackendCategoryId,
} from "../../utils/customerStatus";

const MAX_ATTACHMENT_MB = 5;
const ACCEPTED_EXTENSIONS = ".png,.jpg,.jpeg,.pdf,.txt,.csv,.docx,.log";

const ISSUE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  payment: CreditCard,
  orders: ShoppingBag,
  refund: RotateCcw,
  delivery: Truck,
  account: KeyRound,
  product: Package,
  other: MessageSquare,
};

const complaintSchema = z.object({
  issue_type: z.string().min(1, "Please select what your issue is about."),
  subject: z
    .string()
    .trim()
    .min(4, "Please enter a short subject (at least 4 characters).")
    .max(255, "Subject is too long (maximum 255 characters)."),
  description: z
    .string()
    .trim()
    .min(10, "Please describe what happened (at least 10 characters).")
    .max(8000, "Description is too long."),
  order_reference: z.string().trim().max(120).optional(),
  company_id: z.string().optional(),
  contact_method: z.enum(["email", "phone", "portal"]),
  contact_phone: z.string().trim().max(120).optional(),
});

type ComplaintFormValues = z.infer<typeof complaintSchema>;

export function CustomerSubmitComplaintPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submittedComplaint, setSubmittedComplaint] =
    useState<TicketDetail | null>(null);

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiRequest<CategoryItem[]>("/api/categories"),
  });

  const { data: companiesData } = useQuery({
    queryKey: ["companies-active"],
    queryFn: () =>
      apiRequest<{ platform_types: string[]; companies: CompanyItem[] }>(
        "/api/companies?active_only=true"
      ),
  });

  const companies = companiesData?.companies || [];

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ComplaintFormValues>({
    resolver: zodResolver(complaintSchema),
    defaultValues: {
      issue_type: "",
      subject: "",
      description: "",
      order_reference: "",
      company_id: "",
      contact_method: "email",
      contact_phone: user?.contact_information || "",
    },
  });

  const selectedIssueId = watch("issue_type");
  const selectedContactMethod = watch("contact_method");
  const selectedIssueOption = CUSTOMER_ISSUE_OPTIONS.find(
    (opt) => opt.id === selectedIssueId
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAttachmentError(null);
    const file = e.target.files?.[0] || null;
    if (!file) {
      setAttachment(null);
      return;
    }
    if (file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      setAttachment(null);
      setAttachmentError(
        `This file is larger than ${MAX_ATTACHMENT_MB} MB. Please choose a smaller file.`
      );
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setAttachment(file);
  };

  const removeAttachment = () => {
    setAttachment(null);
    setAttachmentError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const onSubmit = async (values: ComplaintFormValues) => {
    setServerError(null);

    if (
      values.contact_method === "phone" &&
      !(values.contact_phone || "").trim()
    ) {
      setServerError(
        "Please enter a phone number so our support team can reach you."
      );
      return;
    }

    const mappedCategoryId = matchBackendCategoryId(
      values.issue_type,
      categories
    );
    const chosenCompany = values.company_id
      ? companies.find((c) => String(c.id) === values.company_id)
      : undefined;

    let contactPreference = `Preferred contact: Email (${user?.email || "account email"})`;
    if (values.contact_method === "phone") {
      contactPreference = `Preferred contact: Phone (${(values.contact_phone || "").trim()})`;
    } else if (values.contact_method === "portal") {
      contactPreference = "Preferred contact: In-portal messages";
    }

    try {
      const created = await apiRequest<TicketDetail>("/api/tickets", {
        method: "POST",
        body: JSON.stringify({
          subject: values.subject.trim(),
          description: values.description.trim(),
          category_id: mappedCategoryId,
          external_reference: values.order_reference?.trim() || null,
          company_id: chosenCompany ? chosenCompany.id : null,
          platform_type: chosenCompany ? chosenCompany.platform_type : null,
          contact_information: contactPreference,
        }),
      });

      if (attachment) {
        try {
          const fd = new FormData();
          fd.append("file", attachment);
          await apiRequest(`/api/tickets/${created.id}/attachments`, {
            method: "POST",
            body: fd,
          });
        } catch {
          notify(
            "Your complaint was submitted, but the attachment could not be uploaded. You can add it from the complaint page.",
            "info"
          );
        }
      }

      setSubmittedComplaint(created);
      queryClient.invalidateQueries({ queryKey: ["customer-recent-complaints"] });
      queryClient.invalidateQueries({ queryKey: ["customer-complaints"] });
      reset();
      setAttachment(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setServerError(
        err instanceof ApiError
          ? err.message
          : "We could not submit your complaint right now. Your details are still saved below — please try again."
      );
    }
  };

  if (submittedComplaint) {
    const statusInfo = getCustomerStatusInfo(
      submittedComplaint.status,
      submittedComplaint.has_assigned_support
    );

    return (
      <div className="max-w-2xl mx-auto">
        <div className="surface-card p-7 sm:p-9 space-y-6">
          <div className="flex items-start gap-4">
            <div className="w-11 h-11 rounded-full bg-[#EDF6F1] text-[#2F6354] border border-[#C6E0D4] flex items-center justify-center shrink-0 mt-0.5">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-[22px] font-bold text-[#1D2825] tracking-tight">
                Your complaint has been submitted successfully.
              </h1>
              <p className="mt-1.5 text-[14.5px] text-[#556560] leading-relaxed">
                Our support team has received your message and will review it as soon as possible.
                You can follow updates or add more details anytime from your complaints page.
              </p>
            </div>
          </div>

          <dl className="bg-[#F8FAF9] border border-[#E4EAE6] rounded-[10px] p-5 grid grid-cols-1 sm:grid-cols-2 gap-4 text-[14px]">
            <div>
              <dt className="text-[12px] font-medium text-[#6E7C77]">Complaint ID</dt>
              <dd className="mt-1 font-mono font-semibold text-[#2F6354] text-[15.5px]">
                {submittedComplaint.ticket_reference}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] font-medium text-[#6E7C77]">Current status</dt>
              <dd className="mt-1">
                <span
                  className={`inline-block px-2.5 py-0.5 text-[12.5px] font-medium rounded-full border ${statusInfo.badgeClass}`}
                >
                  {statusInfo.label}
                </span>
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-[12px] font-medium text-[#6E7C77]">Subject</dt>
              <dd className="mt-1 font-semibold text-[#1D2825]">
                {submittedComplaint.subject}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] font-medium text-[#6E7C77]">Submission date</dt>
              <dd className="mt-1 text-[#1D2825]">
                {formatDateTime(submittedComplaint.created_at)}
              </dd>
            </div>
          </dl>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Link
              to={`/my-complaints/${submittedComplaint.id}`}
              className="btn-primary px-5 py-2.5 text-[14px]"
            >
              View Complaint
            </Link>
            <button
              type="button"
              onClick={() => setSubmittedComplaint(null)}
              className="btn-secondary px-4 py-2.5 text-[14px]"
            >
              Submit another complaint
            </button>
            <Link
              to="/"
              className="text-[13.5px] font-medium text-[#5A6964] hover:text-[#1D2825] ml-auto"
            >
              Return to Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-[#1D2825] tracking-tight">
          Submit a Complaint
        </h1>
        <p className="mt-1.5 text-[14.5px] text-[#556560] leading-relaxed">
          Share a few details about what went wrong. We&apos;ll use your account details
          automatically and keep you updated every step of the way.
        </p>
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        className="surface-card p-6 sm:p-8 space-y-6"
      >
        {serverError && (
          <div
            role="alert"
            className="px-4 py-3 rounded-[8px] border border-[#ECC5C5] bg-[#FEF5F5] text-[#B03E3E] text-[13.5px]"
          >
            {serverError}
          </div>
        )}

        {/* 1. What is your issue about? */}
        <fieldset>
          <legend className="text-[14.5px] font-semibold text-[#1D2825]">
            1. What is your issue about? <span className="text-[#B03E3E]">*</span>
          </legend>
          <p className="text-[13px] text-[#6E7C77] mt-0.5">
            Choose the option that best matches your problem.
          </p>

          <input type="hidden" {...register("issue_type")} />

          <div className="mt-3.5 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {CUSTOMER_ISSUE_OPTIONS.map((option) => {
              const selected = selectedIssueId === option.id;
              const Icon = ISSUE_ICONS[option.id] || MessageSquare;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() =>
                    setValue("issue_type", option.id, { shouldValidate: true })
                  }
                  aria-pressed={selected}
                  className={`relative text-left px-4 py-3.5 rounded-[9px] border transition-all cursor-pointer flex items-start gap-3 ${
                    selected
                      ? "border-[#2F6354] bg-[#ECF4F1] shadow-[0_0_0_1px_#2F6354]"
                      : "border-[#E1E6E3] bg-white hover:border-[#B6C8C0] hover:bg-[#FAFBF9]"
                  }`}
                >
                  <span
                    className={`w-8 h-8 rounded-[7px] flex items-center justify-center shrink-0 mt-0.5 ${
                      selected
                        ? "bg-[#2F6354] text-white"
                        : "bg-[#F3F6F4] text-[#556560]"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </span>
                  <div className="min-w-0 flex-1 pr-4">
                    <div
                      className={`text-[14px] font-semibold ${
                        selected ? "text-[#1E473B]" : "text-[#1D2825]"
                      }`}
                    >
                      {option.label}
                    </div>
                    <div className="text-[12.5px] text-[#62706B] mt-0.5 leading-snug">
                      {option.hint}
                    </div>
                  </div>
                  {selected && (
                    <span className="absolute top-3 right-3 w-4.5 h-4.5 rounded-full bg-[#2F6354] text-white flex items-center justify-center">
                      <Check className="w-3 h-3" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {errors.issue_type && (
            <p role="alert" className="mt-2 text-[13px] text-[#B03E3E]">
              {errors.issue_type.message}
            </p>
          )}
        </fieldset>

        {/* 2. Subject */}
        <div>
          <label
            htmlFor="complaint-subject"
            className="block text-[14.5px] font-semibold text-[#1D2825] mb-1.5"
          >
            2. Subject <span className="text-[#B03E3E]">*</span>
          </label>
          <input
            id="complaint-subject"
            type="text"
            {...register("subject")}
            placeholder="e.g. Refund not received for returned order"
            className="field-input py-2.5 text-[14px]"
          />
          {errors.subject && (
            <p role="alert" className="mt-1.5 text-[13px] text-[#B03E3E]">
              {errors.subject.message}
            </p>
          )}
        </div>

        {/* 3. Describe your problem */}
        <div>
          <label
            htmlFor="complaint-description"
            className="block text-[14.5px] font-semibold text-[#1D2825] mb-1.5"
          >
            3. Describe your problem <span className="text-[#B03E3E]">*</span>
          </label>
          <textarea
            id="complaint-description"
            rows={5}
            {...register("description")}
            placeholder="Tell us what happened, when it occurred, and what outcome you are hoping for."
            className="field-input py-2.5 text-[14px] leading-relaxed"
          />
          {errors.description && (
            <p role="alert" className="mt-1.5 text-[13px] text-[#B03E3E]">
              {errors.description.message}
            </p>
          )}
        </div>

        {/* 4. Order ID / Transaction Reference */}
        {(!selectedIssueOption || selectedIssueOption.showOrderField) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="complaint-order-ref"
                className="block text-[13.5px] font-semibold text-[#1D2825] mb-1.5"
              >
                Order ID or transaction reference{" "}
                <span className="font-normal text-[#7D8B86]">(optional)</span>
              </label>
              <input
                id="complaint-order-ref"
                type="text"
                {...register("order_reference")}
                placeholder="e.g. ORD-90214 or TXN-4481"
                className="field-input py-2.5 text-[14px]"
              />
            </div>

            {companies.length > 0 && (
              <div>
                <label
                  htmlFor="complaint-company"
                  className="block text-[13.5px] font-semibold text-[#1D2825] mb-1.5"
                >
                  Company or store{" "}
                  <span className="font-normal text-[#7D8B86]">(optional)</span>
                </label>
                <select
                  id="complaint-company"
                  {...register("company_id")}
                  className="field-input py-2.5 text-[14px]"
                >
                  <option value="">Select if applicable</option>
                  {companies.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/* 5. Attachment */}
        <div className="rounded-[9px] border border-dashed border-[#CFD9D4] bg-[#F9FBFA] p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <label
                htmlFor="complaint-attachment"
                className="block text-[13.5px] font-semibold text-[#1D2825]"
              >
                Attachment{" "}
                <span className="font-normal text-[#7D8B86]">(optional)</span>
              </label>
              <p className="text-[12.5px] text-[#6E7C77] mt-0.5">
                Receipt, screenshot, or invoice (PDF, PNG, JPG, TXT, CSV, DOCX — up to {MAX_ATTACHMENT_MB} MB).
              </p>
            </div>

            <label
              htmlFor="complaint-attachment"
              className="btn-secondary inline-flex items-center gap-2 px-3.5 py-2 text-[13px] cursor-pointer shrink-0 self-start sm:self-center"
            >
              <Paperclip className="w-3.5 h-3.5 text-[#556560]" />
              {attachment ? "Change file" : "Choose a file"}
            </label>
            <input
              ref={fileInputRef}
              id="complaint-attachment"
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              onChange={handleFileChange}
              className="sr-only"
            />
          </div>

          {attachment && (
            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-[7px] bg-white border border-[#DCE4E0] text-[13px] text-[#1D2825]">
              <span className="truncate max-w-[260px] font-medium">{attachment.name}</span>
              <span className="text-[#7D8B86]">
                ({(attachment.size / 1024).toFixed(0)} KB)
              </span>
              <button
                type="button"
                onClick={removeAttachment}
                aria-label="Remove attachment"
                className="text-[#7D8B86] hover:text-[#1D2825] cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {attachmentError && (
            <p role="alert" className="mt-2 text-[13px] text-[#B03E3E]">
              {attachmentError}
            </p>
          )}
        </div>

        {/* 6. Preferred contact method */}
        <fieldset className="pt-2 border-t border-[#E6EBE8]">
          <legend className="text-[14px] font-semibold text-[#1D2825]">
            Preferred contact method
          </legend>
          <p className="text-[12.5px] text-[#6E7C77] mt-0.5">
            Signed in as <span className="text-[#1D2825] font-medium">{user?.name}</span> ({user?.email}).
          </p>

          <div className="mt-3 flex flex-wrap gap-2.5">
            {[
              { value: "email", label: "Email" },
              { value: "phone", label: "Phone" },
              { value: "portal", label: "In-portal messages" },
            ].map((item) => {
              const active = selectedContactMethod === item.value;
              return (
                <label
                  key={item.value}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-[8px] border text-[13.5px] cursor-pointer transition-colors ${
                    active
                      ? "border-[#2F6354] bg-[#ECF4F1] text-[#1E473B] font-semibold"
                      : "border-[#E1E6E3] bg-white text-[#1D2825] hover:bg-[#F8FAF9]"
                  }`}
                >
                  <input
                    type="radio"
                    value={item.value}
                    {...register("contact_method")}
                    className="accent-[#2F6354]"
                  />
                  {item.label}
                </label>
              );
            })}
          </div>

          {selectedContactMethod === "phone" && (
            <div className="mt-3 max-w-sm">
              <label
                htmlFor="complaint-phone"
                className="block text-[13px] font-medium text-[#1D2825] mb-1"
              >
                Phone number
              </label>
              <input
                id="complaint-phone"
                type="text"
                {...register("contact_phone")}
                placeholder="e.g. +1 555-0148"
                className="field-input py-2 text-[14px]"
              />
            </div>
          )}
        </fieldset>

        {/* Actions */}
        <div className="pt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#E6EBE8]">
          <Link
            to="/"
            className="text-[13.5px] font-medium text-[#5A6964] hover:text-[#1D2825]"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary px-6 py-2.5 text-[14px]"
          >
            {isSubmitting ? "Submitting complaint..." : "Submit Complaint"}
          </button>
        </div>
      </form>
    </div>
  );
}
