import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { CategoryItem, CompanyItem, TicketDetail } from "../types";
import { PageHeader, StatusLabel, PriorityIndicator, VerificationBadge } from "../components/UI";

const ticketSchema = z.object({
  platform_type: z.string().optional(),
  company_id: z.string().optional(),
  external_reference: z.string().max(120).optional(),
  subject: z.string().min(4, "Subject must be at least 4 characters.").max(255),
  description: z.string().min(10, "Please provide at least 10 characters describing the issue.").max(8000),
  category_id: z.string().optional(),
  product_reference: z.string().max(120).optional(),
  contact_information: z.string().max(255).optional(),
});

type TicketFormValues = z.infer<typeof ticketSchema>;

export function SubmitTicketPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const [attachment, setAttachment] = useState<File | null>(null);
  const [submittedTicket, setSubmittedTicket] = useState<TicketDetail | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const { data: categories } = useQuery({
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

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TicketFormValues>({
    resolver: zodResolver(ticketSchema),
    defaultValues: {
      platform_type: "",
      company_id: "",
      contact_information: user?.contact_information || user?.email || "",
    },
  });

  const selectedPlatform = watch("platform_type");
  const allCompanies = companiesData?.companies || [];
  const filteredCompanies = selectedPlatform
    ? allCompanies.filter((c) => c.platform_type === selectedPlatform)
    : allCompanies;

  const onSubmit = async (values: TicketFormValues) => {
    setServerError(null);
    try {
      const created = await apiRequest<TicketDetail>("/api/tickets", {
        method: "POST",
        body: JSON.stringify({
          subject: values.subject,
          description: values.description,
          category_id: values.category_id ? Number(values.category_id) : null,
          product_reference: values.product_reference || null,
          contact_information: values.contact_information || null,
          company_id: values.company_id ? Number(values.company_id) : null,
          platform_type: values.platform_type || null,
          external_reference: values.external_reference || null,
        }),
      });

      if (attachment) {
        const fd = new FormData();
        fd.append("file", attachment);
        await apiRequest(`/api/tickets/${created.id}/attachments`, {
          method: "POST",
          body: fd,
        });
      }

      setSubmittedTicket(created);
      notify(`Ticket ${created.ticket_reference} submitted for verification and routing.`, "success");
      reset();
      setAttachment(null);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Failed to submit ticket.");
    }
  };

  if (submittedTicket) {
    return (
      <div className="max-w-2xl mx-auto">
        <PageHeader
          title="Request Received"
          subtitle="QRYVANTA has registered your ticket, classified it, and queued it for evidence verification and company handoff."
        />
        <div className="surface-card p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#E3E7E4]">
            <div>
              <div className="text-[12px] text-[#78817D]">Ticket reference</div>
              <div className="text-[19px] font-mono font-semibold text-[#38685A]">
                {submittedTicket.ticket_reference}
              </div>
            </div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <PriorityIndicator priority={submittedTicket.priority} />
              <StatusLabel status={submittedTicket.status} />
              <VerificationBadge status={submittedTicket.verification?.status || submittedTicket.verification_status} />
            </div>
          </div>

          <div>
            <div className="text-[12px] text-[#78817D]">Subject</div>
            <div className="text-[14px] font-medium text-[#222C2A] mt-0.5">{submittedTicket.subject}</div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[13px] pt-1">
            <div>
              <span className="text-[#78817D]">Platform / Portal: </span>
              <span className="font-medium">{submittedTicket.platform_type || "General"}</span>
            </div>
            <div>
              <span className="text-[#78817D]">Target Company: </span>
              <span className="font-medium">{submittedTicket.company?.name || submittedTicket.company_name || "General Support"}</span>
            </div>
            {submittedTicket.external_reference && (
              <div>
                <span className="text-[#78817D]">External Order / Ref ID: </span>
                <span className="font-mono font-medium">{submittedTicket.external_reference}</span>
              </div>
            )}
            <div>
              <span className="text-[#78817D]">Category: </span>
              <span className="font-medium">{submittedTicket.category_name || "Pending review"}</span>
            </div>
          </div>

          <div className="text-[12.5px] text-[#78817D] bg-[#FAFBF9] border border-[#E3E7E4] rounded p-3">
            <strong>Next step:</strong> QRYVANTA support specialists will verify your claim details and order/proof attachments, then prepare a verified handoff brief so the company can resolve your request directly without repeated investigation.
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Link to={`/tickets/${submittedTicket.id}`} className="btn-primary">
              Track ticket & verification progress
            </Link>
            <button className="btn-secondary" onClick={() => setSubmittedTicket(null)}>
              Submit another request
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader
        title="Submit a Support Ticket"
        subtitle="Select the platform and company your issue relates to. QRYVANTA will classify, verify your evidence, and prepare an action-ready report for the company."
      />

      <div className="surface-card p-6">
        {serverError && (
          <div role="alert" className="mb-4 px-3 py-2 rounded border border-[#E7C6C6] bg-[#FCF7F7] text-[#B84C4C] text-[13px]">
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-[#FAFBF9] p-3.5 rounded border border-[#E3E7E4]">
            <div>
              <div className="text-[11.5px] text-[#78817D]">Requester</div>
              <div className="text-[13.5px] font-medium text-[#222C2A]">
                {user?.name} ({user?.email})
              </div>
            </div>
            <div>
              <label className="block text-[11.5px] text-[#78817D] mb-1">
                Preferred contact details
              </label>
              <input
                {...register("contact_information")}
                className="field-input"
                placeholder="Phone or alternate contact"
              />
            </div>
          </div>

          {/* Target Platform / Portal & Company Selection */}
          <div className="border border-[#D3DFDA] bg-[#F6FAF8] rounded p-4 space-y-3">
            <div>
              <div className="text-[13px] font-semibold text-[#222C2A]">
                Target Platform / Portal & Company
              </div>
              <p className="text-[12px] text-[#78817D]">
                Choose where your issue occurred (e.g., an E-Commerce store that hasn't refunded a returned item, a SaaS app, or a courier) so QRYVANTA can verify and report it directly to that company.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="platform_type" className="block text-[12px] font-medium text-[#222C2A] mb-1">
                  Platform / Portal
                </label>
                <select
                  id="platform_type"
                  {...register("platform_type")}
                  onChange={(e) => {
                    setValue("platform_type", e.target.value);
                    setValue("company_id", "");
                  }}
                  className="field-input"
                >
                  <option value="">All platforms / General</option>
                  {(companiesData?.platform_types || [
                    "E-Commerce",
                    "SaaS / Software",
                    "Fintech / Payments",
                    "Logistics / Courier",
                    "Hardware & Devices",
                  ]).map((pt) => (
                    <option key={pt} value={pt}>
                      {pt}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="company_id" className="block text-[12px] font-medium text-[#222C2A] mb-1">
                  Company
                </label>
                <select
                  id="company_id"
                  {...register("company_id")}
                  onChange={(e) => {
                    const cid = e.target.value;
                    setValue("company_id", cid);
                    const found = allCompanies.find((c) => String(c.id) === cid);
                    if (found && !selectedPlatform) {
                      setValue("platform_type", found.platform_type);
                    }
                  }}
                  className="field-input"
                >
                  <option value="">Select target company...</option>
                  {filteredCompanies.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.name} ({c.platform_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="external_reference" className="block text-[12px] font-medium text-[#222C2A] mb-1">
                  Order / Return / Txn ID
                </label>
                <input
                  id="external_reference"
                  {...register("external_reference")}
                  className="field-input"
                  placeholder="e.g., ORD-99210, RMA-441"
                />
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="subject" className="block text-[12.5px] font-medium text-[#222C2A] mb-1">
              Subject *
            </label>
            <input
              id="subject"
              {...register("subject")}
              className="field-input"
              placeholder="e.g., Refund not issued 10 days after returning product to warehouse"
            />
            {errors.subject && (
              <p className="text-[12px] text-[#B84C4C] mt-1">{errors.subject.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="description" className="block text-[12.5px] font-medium text-[#222C2A] mb-1">
              Detailed description & verification details *
            </label>
            <textarea
              id="description"
              rows={5}
              {...register("description")}
              className="field-input"
              placeholder="Include order date, return tracking confirmation, payment amount, prior contact with the company, and desired resolution..."
            />
            {errors.description && (
              <p className="text-[12px] text-[#B84C4C] mt-1">{errors.description.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="category_id" className="block text-[12.5px] font-medium text-[#222C2A] mb-1">
                Category (optional — leave blank for automatic classification)
              </label>
              <select id="category_id" {...register("category_id")} className="field-input">
                <option value="">Auto-detect category</option>
                {categories?.filter((c) => c.is_active).map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="product_reference" className="block text-[12.5px] font-medium text-[#222C2A] mb-1">
                Product or service name (optional)
              </label>
              <input
                id="product_reference"
                {...register("product_reference")}
                className="field-input"
                placeholder="e.g., Wireless Headset Pro, Annual Plan"
              />
            </div>
          </div>

          <div>
            <label htmlFor="attachment" className="block text-[12.5px] font-medium text-[#222C2A] mb-1">
              Supporting proof / attachment (optional, max 5 MB — invoice, return receipt, screenshot)
            </label>
            <input
              id="attachment"
              type="file"
              onChange={(e) => setAttachment(e.target.files?.[0] || null)}
              className="field-input"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Link to="/tickets" className="btn-secondary">
              Cancel
            </Link>
            <button type="submit" disabled={isSubmitting} className="btn-primary">
              {isSubmitting ? "Submitting..." : "Submit ticket"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
