import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { ModelVersionRecord } from "../types";
import { PageHeader, MetricSummary, LoadingSkeleton, ErrorState, EmptyState } from "../components/UI";

interface ModelsListResponse {
  models: ModelVersionRecord[];
  pending_feedback_corrections: number;
  has_active_model: boolean;
}

export function ModelCentrePage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const canTrain = user?.role === "admin" || user?.role === "manager";

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [includeFeedback, setIncludeFeedback] = useState(true);
  const [activateImmediately, setActivateImmediately] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiRequest<ModelsListResponse>("/api/models"),
  });

  const trainMutation = useMutation({
    mutationFn: () =>
      apiRequest<ModelVersionRecord>("/api/models/train", {
        method: "POST",
        body: JSON.stringify({
          include_feedback_corrections: includeFeedback,
          activate_immediately: activateImmediately,
        }),
      }),
    onSuccess: (mv) => {
      notify(`Trained model ${mv.version} (Macro F1: ${((mv.evaluation_metrics.macro_f1 || 0) * 100).toFixed(1)}%).`, "success");
      setSelectedId(mv.id);
      qc.invalidateQueries({ queryKey: ["models"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Training failed.", "error"),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/models/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      notify("Active production model updated.", "success");
      qc.invalidateQueries({ queryKey: ["models"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Activation failed.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (error || !data) return <ErrorState message="Failed to load Model Centre." onRetry={() => refetch()} />;

  const activeModel = data.models.find((m) => m.is_active) || data.models[0] || null;
  const inspected = data.models.find((m) => m.id === selectedId) || activeModel;
  const metrics = inspected?.evaluation_metrics;

  return (
    <div>
      <PageHeader
        title="Model Centre"
        subtitle="Manage trained classifier versions, inspect held-out test metrics and confusion matrices, and run controlled retraining with human feedback."
      />

      {!data.has_active_model && (
        <div className="surface-card p-4 mb-5 border-[#E8D7BC] bg-[#FBF8F1] text-[13px]">
          <strong>No trained ML model is currently active.</strong> Ticket classification uses the transparent keyword rule-based fallback until a model is trained and activated below.
        </div>
      )}

      {/* Controlled Retraining Workflow */}
      {canTrain && (
        <div className="surface-card p-4 mb-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="text-[13.5px] font-semibold text-[#222C2A]">
              Controlled Model Retraining Workflow
            </div>
            <p className="text-[12.5px] text-[#78817D] mt-0.5">
              Deduplicates training text, performs group-stratified train/test evaluation with zero leakage, and saves a versioned joblib artifact.{" "}
              <strong>{data.pending_feedback_corrections}</strong> human correction record(s) available.
            </p>
            <div className="flex flex-wrap gap-4 mt-2.5 text-[12.5px]">
              <label className="inline-flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={includeFeedback}
                  onChange={(e) => setIncludeFeedback(e.target.checked)}
                />
                Include verified human corrections
              </label>
              <label className="inline-flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={activateImmediately}
                  onChange={(e) => setActivateImmediately(e.target.checked)}
                />
                Promote to active immediately after evaluation
              </label>
            </div>
          </div>
          <button
            className="btn-primary shrink-0"
            disabled={trainMutation.isPending}
            onClick={() => trainMutation.mutate()}
          >
            {trainMutation.isPending ? "Training & evaluating..." : "Train new model version"}
          </button>
        </div>
      )}

      {data.models.length === 0 ? (
        <EmptyState
          title="No trained model versions found"
          description="Use the Controlled Model Retraining workflow above or run scripts/train_classifier.py to train the initial TF-IDF + Logistic Regression classifier."
        />
      ) : (
        <div className="space-y-5">
          {/* Version History Table */}
          <div className="surface-card overflow-x-auto">
            <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
              Model Version History
            </div>
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2.5 px-4">Version</th>
                  <th className="py-2.5 px-3">Algorithm</th>
                  <th className="py-2.5 px-3">Dataset</th>
                  <th className="py-2.5 px-3">Test Accuracy</th>
                  <th className="py-2.5 px-3">Macro F1</th>
                  <th className="py-2.5 px-3">Weighted F1</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {data.models.map((mv) => (
                  <tr
                    key={mv.id}
                    className={inspected?.id === mv.id ? "bg-[#F0F4F2]/60" : "hover:bg-[#FAFBF9]"}
                  >
                    <td className="py-2.5 px-4 font-mono font-medium">{mv.version}</td>
                    <td className="py-2.5 px-3 text-[#78817D]">{mv.algorithm}</td>
                    <td className="py-2.5 px-3 text-[#78817D] max-w-xs truncate">{mv.dataset_reference}</td>
                    <td className="py-2.5 px-3 font-medium">
                      {mv.evaluation_metrics.accuracy !== undefined
                        ? `${(mv.evaluation_metrics.accuracy * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-[#38685A]">
                      {mv.evaluation_metrics.macro_f1 !== undefined
                        ? `${(mv.evaluation_metrics.macro_f1 * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      {mv.evaluation_metrics.weighted_f1 !== undefined
                        ? `${(mv.evaluation_metrics.weighted_f1 * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      {mv.is_active ? (
                        <span className="px-2 py-0.5 text-[11.5px] rounded bg-[#EFF5F2] text-[#38685A] border border-[#CDE0D7] font-medium">
                          Active
                        </span>
                      ) : (
                        <span className="text-[12px] text-[#78817D]">Archived / Candidate</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        className="btn-secondary py-1 px-2 text-[12px]"
                        onClick={() => setSelectedId(mv.id)}
                      >
                        Inspect
                      </button>
                      {canTrain && !mv.is_active && mv.artifact_exists && (
                        <button
                          className="btn-primary py-1 px-2 text-[12px]"
                          disabled={activateMutation.isPending}
                          onClick={() => activateMutation.mutate(mv.id)}
                        >
                          Activate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Inspected Model Details */}
          {inspected && metrics && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <MetricSummary
                  label="Held-out accuracy"
                  value={metrics.accuracy !== undefined ? `${(metrics.accuracy * 100).toFixed(1)}%` : "—"}
                  tone="accent"
                />
                <MetricSummary
                  label="Macro F1"
                  value={metrics.macro_f1 !== undefined ? `${(metrics.macro_f1 * 100).toFixed(1)}%` : "—"}
                />
                <MetricSummary
                  label="Weighted F1"
                  value={metrics.weighted_f1 !== undefined ? `${(metrics.weighted_f1 * 100).toFixed(1)}%` : "—"}
                />
                <MetricSummary
                  label="Subcategory test acc"
                  value={
                    metrics.subcategory_test_accuracy !== null && metrics.subcategory_test_accuracy !== undefined
                      ? `${(metrics.subcategory_test_accuracy * 100).toFixed(1)}%`
                      : "N/A"
                  }
                />
                <MetricSummary
                  label="Train / Test split"
                  value={`${metrics.train_samples ?? 0} / ${metrics.test_samples ?? 0}`}
                  sublabel={`${metrics.duplicates_removed_before_split ?? 0} duplicates removed`}
                />
              </div>

              {metrics.warnings && metrics.warnings.length > 0 && (
                <div className="surface-card p-3.5 border-[#E8D7BC] bg-[#FBF8F1] text-[12.5px] space-y-1">
                  <div className="font-semibold text-[#9A6D2E]">Data Sufficiency Warnings</div>
                  {metrics.warnings.map((w, i) => (
                    <div key={i}>{w}</div>
                  ))}
                </div>
              )}

              {/* Per-category table */}
              {metrics.per_category && (
                <div className="surface-card overflow-x-auto">
                  <div className="px-4 py-3 border-b border-[#E3E7E4] flex justify-between items-center">
                    <span className="text-[13.5px] font-semibold">
                      Per-Category Performance — {inspected.version}
                    </span>
                    <span className="text-[12px] text-[#78817D]">{metrics.split_strategy}</span>
                  </div>
                  <table className="w-full text-left border-collapse text-[13px]">
                    <thead>
                      <tr className="table-header">
                        <th className="py-2 px-4">Category</th>
                        <th className="py-2 px-3">Precision</th>
                        <th className="py-2 px-3">Recall</th>
                        <th className="py-2 px-3">F1</th>
                        <th className="py-2 px-3">Train samples</th>
                        <th className="py-2 px-3">Test samples</th>
                        <th className="py-2 px-3">Reliability</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E3E7E4]">
                      {metrics.per_category.map((row) => (
                        <tr key={row.category}>
                          <td className="py-2 px-4 font-medium">{row.category}</td>
                          <td className="py-2 px-3">{(row.precision * 100).toFixed(1)}%</td>
                          <td className="py-2 px-3">{(row.recall * 100).toFixed(1)}%</td>
                          <td className="py-2 px-3 font-medium text-[#38685A]">{(row.f1 * 100).toFixed(1)}%</td>
                          <td className="py-2 px-3">{row.train_support}</td>
                          <td className="py-2 px-3">{row.test_support}</td>
                          <td className="py-2 px-3">
                            {row.insufficient_data ? (
                              <span className="text-[#C08A3E] text-[12px] font-medium">Insufficient examples</span>
                            ) : (
                              <span className="text-[#38685A] text-[12px]">Adequate support</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Confusion Matrix */}
              {metrics.confusion_matrix && metrics.labels && (
                <div className="surface-card overflow-x-auto p-4">
                  <div className="text-[13.5px] font-semibold mb-3">
                    Held-Out Confusion Matrix (Rows = True Category, Columns = Predicted Category)
                  </div>
                  <table className="text-[11.5px] border-collapse">
                    <thead>
                      <tr>
                        <th className="p-2 border border-[#E3E7E4] bg-[#FAFBF9] text-left">True \ Pred</th>
                        {metrics.labels.map((lbl) => (
                          <th key={lbl} className="p-2 border border-[#E3E7E4] bg-[#FAFBF9] font-medium max-w-[90px] truncate" title={lbl}>
                            {lbl.split(" ")[0]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.confusion_matrix.map((row, rIdx) => (
                        <tr key={metrics.labels![rIdx]}>
                          <td className="p-2 border border-[#E3E7E4] font-medium bg-[#FAFBF9] whitespace-nowrap">
                            {metrics.labels![rIdx]}
                          </td>
                          {row.map((val, cIdx) => (
                            <td
                              key={cIdx}
                              className={`p-2 border border-[#E3E7E4] text-center ${
                                rIdx === cIdx && val > 0
                                  ? "bg-[#EFF5F2] text-[#38685A] font-semibold"
                                  : val > 0
                                  ? "bg-[#FCF3F3] text-[#B84C4C]"
                                  : "text-[#78817D]"
                              }`}
                            >
                              {val}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
