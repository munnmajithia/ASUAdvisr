"use client";

import { useRef, useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { RequirementReview } from "@/components/requirement-review";
import { ApiError, extractProfile } from "@/lib/api";
import type { RequirementProfile } from "@/lib/profile";

/**
 * DARS upload onboarding.
 *
 * The student uploads their degree-audit PDF; we extract a draft
 * `RequirementProfile` from the backend, then hand off to `RequirementReview`,
 * which owns all editing, confirmation, saving, and routing to /chat. This page
 * only covers: pick a file → validate it's a PDF → extract → show the review.
 *
 * LLM/extraction lives entirely in the backend; the frontend just uploads and
 * surfaces friendly errors keyed off `ApiError.status`.
 */
export default function OnboardingPage() {
  return (
    <AuthGate>
      <Onboarding />
    </AuthGate>
  );
}

/** Map an extraction failure to a friendly, actionable message. */
function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 422:
        return "We couldn’t read that PDF — make sure it’s your DARS/degree-audit export.";
      case 502:
        return "Extraction failed on our end — please try again.";
      case 0:
        return "Can’t reach the server — is the backend running?";
      default:
        return err.message;
    }
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

/** True when the picked file looks like a PDF (by MIME type or extension). */
function isPdf(file: File): boolean {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function Onboarding() {
  const [draft, setDraft] = useState<RequirementProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Once we have a draft, hand off entirely — RequirementReview owns the rest.
  if (draft) {
    return <RequirementReview draft={draft} />;
  }

  async function handleFile(file: File) {
    setError(null);

    // Reject non-PDFs locally — never send them to the extractor.
    if (!isPdf(file)) {
      setError("That doesn’t look like a PDF. Upload your ASU DARS / degree-audit export.");
      return;
    }

    setLoading(true);
    try {
      const profile = await extractProfile(file);
      setDraft(profile);
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset so picking the same file again still fires onChange (retry case).
    e.target.value = "";
    if (file) void handleFile(file);
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Upload your degree audit</h1>
      <p className="mb-8 text-sm text-zinc-500">
        Upload your ASU DARS / degree-audit PDF and we&rsquo;ll pull out what you still need to
        graduate. You&rsquo;ll get to review and correct everything before anything is saved.
      </p>

      <div className="space-y-6">
        <div>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onInputChange}
            disabled={loading}
            className="sr-only"
            aria-label="DARS or degree-audit PDF"
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={loading}
            className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {loading ? "Reading your audit…" : "Choose PDF"}
          </button>
          <p className="mt-2 text-xs text-zinc-400">PDF only. This can take several seconds.</p>
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
