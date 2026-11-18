import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, ArrowLeft, ChevronRight, BookOpen } from "lucide-react";
import { apiRequest } from "../../services/api";
import {
  HELP_CATEGORIES,
  articleMatchesHelpCategory,
  formatShortDate,
  type KnowledgeArticleItem,
} from "../../utils/customerStatus";

export function CustomerHelpCentrePage() {
  const [search, setSearch] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("all");
  const [activeArticle, setActiveArticle] =
    useState<KnowledgeArticleItem | null>(null);

  const queryParams = new URLSearchParams();
  if (search.trim()) {
    queryParams.set("search", search.trim());
  }

  const { data: articles = [], isLoading, isError } = useQuery({
    queryKey: ["customer-help-articles", search],
    queryFn: () =>
      apiRequest<KnowledgeArticleItem[]>(
        `/api/knowledge${queryParams.toString() ? `?${queryParams.toString()}` : ""}`
      ),
  });

  const publishedArticles = articles.filter((a) => a.is_published !== false);
  const filteredArticles = publishedArticles.filter((a) =>
    articleMatchesHelpCategory(a, selectedTopic)
  );

  if (activeArticle) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <button
          type="button"
          onClick={() => setActiveArticle(null)}
          className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-[#5A6964] hover:text-[#1D2825] transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Help Centre
        </button>

        <article className="surface-card p-7 sm:p-9 space-y-4">
          {activeArticle.category_name && (
            <span className="inline-block px-2.5 py-0.5 text-[12px] font-medium rounded-full bg-[#ECF4F1] text-[#244F43] border border-[#CCE0D8]">
              {activeArticle.category_name}
            </span>
          )}
          <h1 className="text-[25px] font-bold text-[#1D2825] leading-snug tracking-tight">
            {activeArticle.title}
          </h1>
          {activeArticle.updated_at && (
            <p className="text-[12.5px] text-[#76847F]">
              Updated {formatShortDate(activeArticle.updated_at)}
            </p>
          )}
          <div className="pt-5 border-t border-[#E6EBE8] text-[15px] text-[#2C3935] whitespace-pre-wrap leading-relaxed">
            {activeArticle.content}
          </div>
        </article>

        <div className="customer-hero-surface p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-semibold text-[#1D2825]">
              Didn&apos;t find what you need?
            </h2>
            <p className="mt-1 text-[13.5px] text-[#556560]">
              Submit a complaint and our support team will help you directly.
            </p>
          </div>
          <Link
            to="/submit-complaint"
            className="btn-primary px-5 py-2.5 text-[14px] text-center shrink-0"
          >
            Contact Support
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      {/* Search Hero */}
      <section className="customer-hero-surface p-7 sm:p-8">
        <div className="max-w-2xl">
          <h1 className="text-[28px] font-bold text-[#1D2825] tracking-tight">
            Help Centre
          </h1>
          <p className="mt-1.5 text-[15px] text-[#556560]">
            Search answers to common questions about payments, orders, refunds, delivery, and your account.
          </p>

          <div className="mt-5 relative">
            <Search className="w-4.5 h-4.5 text-[#76847F] absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search help articles (e.g. refund, password, delayed delivery)"
              aria-label="Search help articles"
              className="field-input pl-11 py-3 text-[14.5px] bg-white shadow-[0_1px_3px_rgba(17,29,25,0.04)]"
            />
          </div>
        </div>

        {/* Common Topic Filters */}
        <div aria-label="Help topics" className="mt-5 flex flex-wrap gap-2">
          {HELP_CATEGORIES.map((topic) => {
            const active = selectedTopic === topic.id;
            return (
              <button
                key={topic.id}
                type="button"
                onClick={() => setSelectedTopic(topic.id)}
                className={`px-3.5 py-1.5 rounded-full text-[13px] font-medium border transition-colors cursor-pointer ${
                  active
                    ? "bg-[#2F6354] border-[#2F6354] text-white shadow-xs"
                    : "bg-white border-[#DCE4E0] text-[#3B4A45] hover:border-[#B6C8C0] hover:bg-[#FAFBF9]"
                }`}
              >
                {topic.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* Articles List */}
      <section className="surface-card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 bg-[#F2F5F3] rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : isError ? (
          <div className="p-6 text-[14px] text-[#556560]">
            We could not load Help Centre articles right now. Please try again shortly.
          </div>
        ) : filteredArticles.length === 0 ? (
          <div className="px-6 py-12 text-center space-y-2">
            <p className="text-[15.5px] font-semibold text-[#1D2825]">
              No matching articles found.
            </p>
            <p className="text-[13.5px] text-[#6E7C77]">
              Try a different keyword, browse all topics, or contact our support team directly.
            </p>
            {(search || selectedTopic !== "all") && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setSearch("");
                    setSelectedTopic("all");
                  }}
                  className="btn-secondary px-4 py-2 text-[13.5px]"
                >
                  Show all articles
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="divide-y divide-[#E6EBE8]">
            {filteredArticles.map((article) => (
              <button
                key={article.id}
                type="button"
                onClick={() => setActiveArticle(article)}
                className="group w-full text-left px-6 py-5 hover:bg-[#F7FAF8] transition-colors flex items-start justify-between gap-4 cursor-pointer"
              >
                <div className="min-w-0 flex items-start gap-3.5">
                  <span className="w-9 h-9 rounded-[8px] bg-[#ECF4F1] text-[#2F6354] border border-[#D4E4DD] flex items-center justify-center shrink-0 mt-0.5">
                    <BookOpen className="w-4 h-4" />
                  </span>
                  <div className="min-w-0 space-y-1">
                    <h2 className="text-[15.5px] font-semibold text-[#1D2825] group-hover:text-[#2F6354] transition-colors">
                      {article.title}
                    </h2>
                    <p className="text-[13.5px] text-[#5A6964] line-clamp-2 leading-relaxed">
                      {article.content}
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-[#76847F] group-hover:text-[#2F6354] transition-all group-hover:translate-x-0.5 shrink-0 mt-2" />
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Bottom Contact Support Callout */}
      <section className="customer-hero-surface p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-[16.5px] font-semibold text-[#1D2825]">
            Didn&apos;t find what you need?
          </h2>
          <p className="mt-1 text-[14px] text-[#556560]">
            Tell us what happened and our support team will look into it for you.
          </p>
        </div>
        <Link
          to="/submit-complaint"
          className="btn-primary px-5 py-2.5 text-[14px] text-center shrink-0"
        >
          Contact Support
        </Link>
      </section>
    </div>
  );
}
