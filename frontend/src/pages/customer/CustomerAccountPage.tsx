import React, { useState, useEffect } from "react";
import { apiRequest, ApiError } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { formatShortDate } from "../../utils/customerStatus";
import { UserAvatar } from "../../components/BrandMark";

export function CustomerAccountPage() {
  const { user, refreshUser } = useAuth();
  const { notify } = useToast();

  const [name, setName] = useState(user?.name || "");
  const [contactInformation, setContactInformation] = useState(
    user?.contact_information || ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    if (user) {
      setName(user.name || "");
      setContactInformation(user.contact_information || "");
    }
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSavedNotice(false);

    if (name.trim().length < 2) {
      setError("Please enter your full name (at least 2 characters).");
      return;
    }

    setSaving(true);
    try {
      await apiRequest("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          contact_information: contactInformation.trim(),
        }),
      });
      await refreshUser();
      setSavedNotice(true);
      notify("Your account details have been updated.", "success");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "We could not save your changes right now. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-[#1D2825] tracking-tight">
          Account
        </h1>
        <p className="mt-1 text-[14.5px] text-[#556560]">
          Keep your name and contact details up to date so our support team can reach you easily.
        </p>
      </div>

      {/* Profile Header Strip */}
      <div className="customer-hero-surface p-5 flex items-center gap-4">
        <UserAvatar name={user?.name} tone="sage" size="md" />
        <div className="min-w-0">
          <div className="text-[16px] font-semibold text-[#1D2825] truncate">
            {user?.name}
          </div>
          <div className="text-[13px] text-[#62706B] truncate">
            {user?.email}
            {user?.created_at
              ? ` · Member since ${formatShortDate(user.created_at)}`
              : ""}
          </div>
        </div>
      </div>

      <form
        onSubmit={handleSave}
        className="surface-card p-6 sm:p-7 space-y-5"
      >
        {error && (
          <div
            role="alert"
            className="px-4 py-3 rounded-[8px] border border-[#ECC5C5] bg-[#FEF5F5] text-[#B03E3E] text-[13.5px]"
          >
            {error}
          </div>
        )}

        {savedNotice && (
          <div
            role="status"
            className="px-4 py-3 rounded-[8px] border border-[#C3DFD2] bg-[#EDF6F1] text-[#245A47] text-[13.5px]"
          >
            Your changes have been saved.
          </div>
        )}

        <div>
          <label
            htmlFor="account-name"
            className="block text-[13.5px] font-semibold text-[#1D2825] mb-1.5"
          >
            Full name
          </label>
          <input
            id="account-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
            className="field-input py-2.5 text-[14px]"
          />
        </div>

        <div>
          <label
            htmlFor="account-email"
            className="block text-[13.5px] font-semibold text-[#1D2825] mb-1.5"
          >
            Email address
          </label>
          <input
            id="account-email"
            type="email"
            value={user?.email || ""}
            disabled
            className="field-input py-2.5 text-[14px] bg-[#F4F6F4] text-[#62706B] cursor-not-allowed"
          />
          <p className="mt-1.5 text-[12.5px] text-[#76847F]">
            Your email address is used to sign in and receive complaint updates.
          </p>
        </div>

        <div>
          <label
            htmlFor="account-contact"
            className="block text-[13.5px] font-semibold text-[#1D2825] mb-1.5"
          >
            Phone number or preferred contact details{" "}
            <span className="font-normal text-[#7D8B86]">(optional)</span>
          </label>
          <input
            id="account-contact"
            type="text"
            value={contactInformation}
            onChange={(e) => setContactInformation(e.target.value)}
            placeholder="e.g. +1 555-0148 or preferred phone / email"
            className="field-input py-2.5 text-[14px]"
          />
          <p className="mt-1.5 text-[12.5px] text-[#76847F]">
            We use this to prefill your contact preference when you submit a complaint.
          </p>
        </div>

        <div className="pt-2 border-t border-[#E6EBE8]">
          <button
            type="submit"
            disabled={saving}
            className="btn-primary px-5 py-2.5 text-[14px]"
          >
            {saving ? "Saving changes..." : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
