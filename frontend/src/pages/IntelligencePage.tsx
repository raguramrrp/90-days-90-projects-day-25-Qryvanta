import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { apiRequest, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { PageHeader, MetricSummary, LoadingSkeleton, ErrorState } from "../components/UI";

interface FeedbackIntelligence {
  total_predictions: number;
  corrected_predictions: number;
  unique_tickets_corrected: number;
  correction_rate: number;
  correction_rate_formula: string;
  department_agreement_rate: number | null;
  confidence_distribution: { band: string; count: number }[];
  routing_decisions: { decision: string; count: number }[];
  most_corrected_categories: { transition: string; count: number }[];
  department_mismatches: { transition: string; count: number }[];
  sentiment_distribution: { sentiment: string; count: number }[];
  demand_alerts: { category: string; last_7_days_volume: number; prior_weekly_avg: number; z_score: number; evidence: string }[];
  recent_corrections: {
    id: number;
    ticket_id: number;
    ticket_reference: string;
    ticket_subject: string;
    original_category: string | null;
    corrected_category: string | null;
    correction_reason: string;
    corrected_by: string | null;
    model_version: string;
    created_at: string;
  }[];
  low_confidence_predictions: {
    ticket_id: number;
    ticket_reference: string;
    subject: string;
    predicted_category: string | null;
    confidence: number;
    routing_decision: string | null;
    status: string | null;
  }[];
}

export function IntelligencePage() {
  const { notify } = useToast();
  const [testSubject, setTestSubject] = useState("");
  const [testDesc, setTestDesc] = useState("");
  const [sandboxResult, setSandboxResult] = useState<{
    predicted_category_name: string;
    predicted_subcategory_name: string | null;
    confidence: number;
    suggested_priority: string;
    priority_reason: string;
    routing_decision: string;
    routing_rule_applied: string;
    explanation: string;
    prediction_source: string;
    sentiment: { label: string; confidence: number; method: string };
  } | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["intelligence-feedback"],
    queryFn: () => apiRequest<FeedbackIntelligence>("/api/intelligence/feedback"),
  });

  const testClassifyMutation = useMutation({
    mutationFn: () =>
      apiRequest<typeof sandboxResult>("/api/intelligence/classify", {
        method: "POST",
        body: JSON.stringify({ subject: testSubject, description: testDesc }),
      }),
    onSuccess: (res) => setSandboxResult(res),
    onError: (err) => notify(err instanceof ApiError ? err.message : "Classification failed.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) return <ErrorState message="Failed to load intelligence telemetry." onRetry={() => refetch()} />;

  return (
    <div>
      <PageHeader
        title="Operational Intelligence & Human-in-the-Loop Feedback"
        subtitle="Inspect live classification confidence, department agreement, staff corrections, sentiment distribution, and demand anomalies."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/resolution-intelligence" className="btn-primary">
              Resolution Intelligence & Knowledge Gaps
            </Link>
            <Link to="/models" className="btn-secondary">
              Model Centre
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <MetricSummary label="Total predictions stored" value={data.total_predictions} />
        <MetricSummary label="Human corrections" value={data.corrected_predictions} tone="warning" />
        <MetricSummary
          label="Correction rate"
          value={`${data.correction_rate}%`}
          sublabel="Unique tickets corrected / total predictions"
        />
        <MetricSummary
          label="Department agreement"
          value={data.department_agreement_rate !== null ? `${data.department_agreement_rate}%` : "N/A"}
          tone="accent"
        />
      </div>

      {/* Live Classification Sandbox */}
      <div className="surface-card p-4 mb-5">
        <div className="text-[13.5px] font-semibold text-[#222C2A] mb-1">
          Live Classification & Urgency Test Bench
        </div>
        <p className="text-[12px] text-[#78817D] mb-3">
          Run the active backend ML model, rule-based urgency detector, routing policy, and sentiment analyzer on any sample ticket text without creating a ticket.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-6 space-y-2.5">
            <input
              value={testSubject}
              onChange={(e) => setTestSubject(e.target.value)}
              placeholder="Sample ticket subject (e.g., Double charged on October Visa invoice)"
              className="field-input"
            />
            <textarea
              rows={3}
              value={testDesc}
              onChange={(e) => setTestDesc(e.target.value)}
              placeholder="Sample ticket description..."
              className="field-input"
            />
            <button
              className="btn-primary"
              disabled={testSubject.trim().length < 3 || testDesc.trim().length < 5 || testClassifyMutation.isPending}
              onClick={() => testClassifyMutation.mutate()}
            >
              {testClassifyMutation.isPending ? "Running inference..." : "Run live classification"}
            </button>
          </div>
          <div className="lg:col-span-6">
            {sandboxResult ? (
              <div className="bg-[#FAFBF9] border border-[#E3E7E4] rounded p-3.5 text-[12.5px] space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Predicted category</span>
                  <span className="font-semibold text-[#38685A]">
                    {sandboxResult.predicted_category_name}
                    {sandboxResult.predicted_subcategory_name ? ` / ${sandboxResult.predicted_subcategory_name}` : ""}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Confidence / Source</span>
                  <span>
                    {(sandboxResult.confidence * 100).toFixed(1)}% ({sandboxResult.prediction_source})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Routing decision</span>
                  <span className="capitalize">{sandboxResult.routing_decision.replace("_", " ")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Independent urgency</span>
                  <span className="capitalize font-medium">{sandboxResult.suggested_priority}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#78817D]">Sentiment (context only)</span>
                  <span className="capitalize">
                    {sandboxResult.sentiment.label} ({sandboxResult.sentiment.method.replace(/_/g, " ")})
                  </span>
                </div>
                <p className="text-[12px] text-[#78817D] pt-1 border-t border-[#E3E7E4]">
                  {sandboxResult.explanation}
                </p>
                <p className="text-[12px] text-[#78817D]">{sandboxResult.priority_reason}</p>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center border border-dashed border-[#E3E7E4] rounded p-4 text-[12.5px] text-[#78817D]">
                Enter sample text on the left to inspect genuine model inference output.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-5">
        <div className="lg:col-span-6 surface-card p-4">
          <div className="text-[13.5px] font-semibold text-[#222C2A] mb-3">
            Prediction confidence distribution
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.confidence_distribution}>
                <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="band" tick={{ fontSize: 11, fill: "#222C2A" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                <Tooltip />
                <Bar dataKey="count" name="Predictions" fill="#38685A" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-6 surface-card p-4">
          <div className="text-[13.5px] font-semibold text-[#222C2A] mb-3">
            Customer sentiment distribution (rule-based lexicon)
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.sentiment_distribution}>
                <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="sentiment" tick={{ fontSize: 11.5, fill: "#222C2A" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                <Tooltip />
                <Bar dataKey="count" name="Tickets" fill="#8AA397" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Demand Spike Alerts */}
      {data.demand_alerts.length > 0 && (
        <div className="surface-card p-4 mb-5 border-[#E8D7BC] bg-[#FBF8F1]">
          <div className="text-[13.5px] font-semibold text-[#222C2A] mb-2">
            Detected Category Demand Increases (Statistical Z-Score &ge; 1.5)
          </div>
          <div className="space-y-1.5 text-[12.5px]">
            {data.demand_alerts.map((al) => (
              <div key={al.category} className="flex flex-wrap justify-between gap-2">
                <span className="font-medium text-[#222C2A]">{al.category}</span>
                <span className="text-[#78817D]">{al.evidence}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Low-Confidence Queue & Recent Human Corrections */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-6 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Recent Human-in-the-Loop Corrections
          </div>
          <div className="divide-y divide-[#E3E7E4] text-[12.5px]">
            {data.recent_corrections.length === 0 ? (
              <div className="p-5 text-center text-[#78817D]">No human corrections recorded yet.</div>
            ) : (
              data.recent_corrections.map((fb) => (
                <div key={fb.id} className="p-3.5">
                  <div className="flex justify-between gap-2">
                    <Link to={`/tickets/${fb.ticket_id}`} className="font-mono text-[#38685A] hover:underline">
                      {fb.ticket_reference}
                    </Link>
                    <span className="text-[#78817D] text-[11.5px]">{fb.corrected_by}</span>
                  </div>
                  <div className="text-[#222C2A] font-medium mt-0.5">
                    {fb.original_category || "Unmapped"} &rarr; {fb.corrected_category}
                  </div>
                  <div className="text-[#78817D] text-[12px] mt-0.5">Reason: {fb.correction_reason}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="lg:col-span-6 surface-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
            Low-Confidence Predictions Awaiting Review
          </div>
          <div className="divide-y divide-[#E3E7E4] text-[12.5px]">
            {data.low_confidence_predictions.length === 0 ? (
              <div className="p-5 text-center text-[#78817D]">No low-confidence predictions found.</div>
            ) : (
              data.low_confidence_predictions.map((p) => (
                <Link
                  key={`${p.ticket_id}-${p.confidence}`}
                  to={`/tickets/${p.ticket_id}`}
                  className="block p-3.5 hover:bg-[#FAFBF9]"
                >
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-[#38685A]">{p.ticket_reference}</span>
                    <span className="text-[#C08A3E] font-medium">{(p.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="text-[#222C2A] truncate mt-0.5">{p.subject}</div>
                  <div className="text-[11.5px] text-[#78817D] mt-0.5">
                    Predicted: {p.predicted_category || "None"} · Status: {p.status}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
