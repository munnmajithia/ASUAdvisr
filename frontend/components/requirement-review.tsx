"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  saveProfile,
  unresolvedRequirements,
  type CompletedCourse,
  type RemainingRequirement,
  type RequirementProfile,
} from "@/lib/profile";

/**
 * Mandatory editable review of a freshly-extracted `RequirementProfile`.
 *
 * The student edits a local copy of the draft, then confirms. Confirming
 * persists the profile and routes to the chat scheduler.
 *
 * Correctness gate (ties to backend B3): any remaining requirement with an
 * empty `options` array (wildcards / open electives / hour-based needs) cannot
 * be scheduled — `profileToRequirements` drops it and the scheduler then
 * silently returns zero schedules. So every such row is visibly warned and the
 * Confirm button is disabled while ANY remaining requirement has empty options.
 * `unresolvedRequirements` is the single source of truth for that check.
 */
export function RequirementReview({ draft }: { draft: RequirementProfile }) {
  const router = useRouter();
  const [profile, setProfile] = useState<RequirementProfile>(draft);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unresolved = unresolvedRequirements(profile);
  const blocked = unresolved.length > 0;

  // ── Top-level field updates ──────────────────────────────────────────────
  function setField<K extends "catalog_year" | "major">(key: K, value: string) {
    setProfile((p) => ({ ...p, [key]: value === "" ? null : value }));
  }

  // ── Completed courses ────────────────────────────────────────────────────
  function updateCompleted(index: number, patch: Partial<CompletedCourse>) {
    setProfile((p) => ({
      ...p,
      completed_courses: p.completed_courses.map((c, i) =>
        i === index ? { ...c, ...patch } : c,
      ),
    }));
  }

  function removeCompleted(index: number) {
    setProfile((p) => ({
      ...p,
      completed_courses: p.completed_courses.filter((_, i) => i !== index),
    }));
  }

  function addCompleted() {
    setProfile((p) => ({
      ...p,
      completed_courses: [
        ...p.completed_courses,
        { course: "", title: null, grade: null, term: null, credits: null, in_progress: false },
      ],
    }));
  }

  // ── Remaining requirements ───────────────────────────────────────────────
  function updateRequirement(index: number, patch: Partial<RemainingRequirement>) {
    setProfile((p) => ({
      ...p,
      remaining_requirements: p.remaining_requirements.map((r, i) =>
        i === index ? { ...r, ...patch } : r,
      ),
    }));
  }

  function removeRequirement(index: number) {
    setProfile((p) => ({
      ...p,
      remaining_requirements: p.remaining_requirements.filter((_, i) => i !== index),
    }));
  }

  function addRequirement() {
    setProfile((p) => ({
      ...p,
      remaining_requirements: [
        ...p.remaining_requirements,
        { label: "", options: [], pick: 1, credits_needed: null, note: null },
      ],
    }));
  }

  function addOption(reqIndex: number) {
    setProfile((p) => ({
      ...p,
      remaining_requirements: p.remaining_requirements.map((r, i) =>
        i === reqIndex ? { ...r, options: [...r.options, ""] } : r,
      ),
    }));
  }

  function updateOption(reqIndex: number, optIndex: number, value: string) {
    setProfile((p) => ({
      ...p,
      remaining_requirements: p.remaining_requirements.map((r, i) =>
        i === reqIndex
          ? { ...r, options: r.options.map((o, j) => (j === optIndex ? value : o)) }
          : r,
      ),
    }));
  }

  function removeOption(reqIndex: number, optIndex: number) {
    setProfile((p) => ({
      ...p,
      remaining_requirements: p.remaining_requirements.map((r, i) =>
        i === reqIndex ? { ...r, options: r.options.filter((_, j) => j !== optIndex) } : r,
      ),
    }));
  }

  // ── Confirm ──────────────────────────────────────────────────────────────
  async function handleConfirm() {
    if (blocked || saving) return;
    setSaving(true);
    setError(null);
    try {
      await saveProfile(profile);
      router.push("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Review your requirements</h1>
      <p className="mb-8 text-sm text-zinc-500">
        We extracted this from your audit. Correct anything that looks off, then confirm.
      </p>

      <div className="space-y-8">
        {/* ── Catalog year & major ──────────────────────────────────────────── */}
        <section className="flex flex-wrap gap-4">
          <div>
            <label className="mb-1 block text-xs text-zinc-500">Catalog year</label>
            <input
              type="text"
              value={profile.catalog_year ?? ""}
              onChange={(e) => setField("catalog_year", e.target.value)}
              placeholder="e.g. 2024-2025"
              className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>
          <div className="grow">
            <label className="mb-1 block text-xs text-zinc-500">Major</label>
            <input
              type="text"
              value={profile.major ?? ""}
              onChange={(e) => setField("major", e.target.value)}
              placeholder="e.g. Computer Science (BS)"
              className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>
        </section>

        {/* ── Completed courses ─────────────────────────────────────────────── */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Completed courses
            </h2>
            <button
              type="button"
              onClick={addCompleted}
              className="rounded px-2 py-1 text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
            >
              + Add course
            </button>
          </div>
          {profile.completed_courses.length === 0 ? (
            <p className="text-sm text-zinc-400">No completed courses.</p>
          ) : (
            <div className="space-y-2">
              {profile.completed_courses.map((course, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700"
                >
                  <input
                    type="text"
                    value={course.course}
                    onChange={(e) => updateCompleted(i, { course: e.target.value })}
                    placeholder="CSE 110"
                    className="w-28 rounded border border-zinc-300 px-2 py-1 font-mono text-xs dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                  />
                  <input
                    type="text"
                    value={course.grade ?? ""}
                    onChange={(e) =>
                      updateCompleted(i, { grade: e.target.value === "" ? null : e.target.value })
                    }
                    placeholder="Grade"
                    className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                  />
                  <label className="flex items-center gap-1.5 text-xs text-zinc-500">
                    <input
                      type="checkbox"
                      checked={course.in_progress}
                      onChange={(e) => updateCompleted(i, { in_progress: e.target.checked })}
                      className="rounded border-zinc-300 dark:border-zinc-600"
                    />
                    In progress
                  </label>
                  <button
                    type="button"
                    onClick={() => removeCompleted(i)}
                    className="ml-auto rounded px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── Remaining requirements ────────────────────────────────────────── */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Remaining requirements
            </h2>
            <button
              type="button"
              onClick={addRequirement}
              className="rounded px-2 py-1 text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
            >
              + Add requirement
            </button>
          </div>
          {profile.remaining_requirements.length === 0 ? (
            <p className="text-sm text-zinc-400">No remaining requirements.</p>
          ) : (
            <div className="space-y-3">
              {profile.remaining_requirements.map((req, i) => {
                const empty = req.options.length === 0;
                return (
                  <div
                    key={i}
                    className={`rounded-lg border p-3 ${
                      empty
                        ? "border-amber-300 bg-amber-50 dark:border-amber-700/60 dark:bg-amber-950/30"
                        : "border-zinc-200 dark:border-zinc-700"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="text"
                        value={req.label}
                        onChange={(e) => updateRequirement(i, { label: e.target.value })}
                        placeholder="Requirement label"
                        className="grow rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                      />
                      <label className="flex items-center gap-1.5 text-xs text-zinc-500">
                        Pick
                        <input
                          type="number"
                          min={1}
                          value={req.pick}
                          onChange={(e) =>
                            updateRequirement(i, {
                              pick: Number(e.target.value) || 1,
                            })
                          }
                          className="w-16 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                        />
                      </label>
                      <button
                        type="button"
                        onClick={() => removeRequirement(i)}
                        className="rounded px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                      >
                        Remove
                      </button>
                    </div>

                    {/* Option course keys */}
                    <div className="mt-3">
                      <div className="mb-1.5 flex items-center justify-between">
                        <p className="text-xs text-zinc-500">Course options</p>
                        <button
                          type="button"
                          onClick={() => addOption(i)}
                          className="rounded px-1.5 py-0.5 text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
                        >
                          + Add option
                        </button>
                      </div>
                      {req.options.length === 0 ? (
                        <p className="rounded-md bg-amber-100 px-3 py-2 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          Add at least one course or remove this requirement — it can&rsquo;t be
                          scheduled.
                        </p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {req.options.map((opt, j) => (
                            <span key={j} className="flex items-center gap-1">
                              <input
                                type="text"
                                value={opt}
                                onChange={(e) => updateOption(i, j, e.target.value)}
                                placeholder="CSE 355"
                                className="w-28 rounded border border-zinc-300 px-2 py-1 font-mono text-xs dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                              />
                              <button
                                type="button"
                                onClick={() => removeOption(i, j)}
                                aria-label="Remove option"
                                className="rounded px-1.5 py-1 text-xs text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                              >
                                ✕
                              </button>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ── Confirm ───────────────────────────────────────────────────────── */}
        <section className="space-y-3 border-t border-zinc-200 pt-6 dark:border-zinc-800">
          {blocked && (
            <p className="rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              {unresolved.length} requirement{unresolved.length === 1 ? "" : "s"} still{" "}
              {unresolved.length === 1 ? "has" : "have"} no course options. Add a course to each, or
              remove it, before confirming.
            </p>
          )}
          {error && (
            <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={handleConfirm}
            disabled={blocked || saving}
            className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {saving ? "Saving…" : "Confirm & continue"}
          </button>
        </section>
      </div>
    </div>
  );
}
