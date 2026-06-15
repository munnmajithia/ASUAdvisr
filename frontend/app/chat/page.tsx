"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { ScheduleCard } from "@/components/schedule-card";
import { getSchedule, parseConstraints } from "@/lib/api";
import {
  DAYS,
  type ApiConstraints,
  type Day,
  type Requirement,
  type ScheduleOut,
} from "@/lib/api-types";
import { loadProfile, profileToRequirements, type RequirementProfile } from "@/lib/profile";

const DAY_LABELS: Record<Day, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

const MODE_LABELS: Record<string, string> = {
  P: "In Person",
  OL: "Online",
  HY: "Hybrid",
  ICOURSE: "iCourse",
};

/** Empty string means "Any" for the time-of-day select. */
type TimeOfDay = "" | "morning" | "afternoon" | "evening";

interface Constraints {
  avoid_days: Day[];
  earliest_start: string; // "HH:MM" or ""
  latest_end: string;
  min_credits: string; // stored as string for number inputs
  max_credits: string;
  preferred_modality: string; // "" | "P" | "OL" | "HY"
  only_open: boolean; // open-sections-only filter
  compact_schedule: boolean; // soft pref: minimize gaps
  prefer_time_of_day: TimeOfDay; // soft pref: "" (Any) | morning | afternoon | evening
}

function emptyConstraints(): Constraints {
  return {
    avoid_days: [],
    earliest_start: "",
    latest_end: "",
    min_credits: "",
    max_credits: "",
    preferred_modality: "",
    only_open: false,
    compact_schedule: false,
    prefer_time_of_day: "",
  };
}

function toApiConstraints(c: Constraints): ApiConstraints {
  return {
    avoid_days: c.avoid_days,
    earliest_start: c.earliest_start || null,
    latest_end: c.latest_end || null,
    min_credits: c.min_credits !== "" ? Number(c.min_credits) : null,
    max_credits: c.max_credits !== "" ? Number(c.max_credits) : null,
    preferred_modality: c.preferred_modality || null,
    only_open: c.only_open,
    compact_schedule: c.compact_schedule,
    prefer_time_of_day: c.prefer_time_of_day || null,
  };
}

const TIME_OF_DAY_LABELS: Record<Exclude<TimeOfDay, "">, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

function summaryChips(c: Constraints): string[] {
  const chips: string[] = [];
  if (c.avoid_days.length > 0)
    chips.push(`No ${c.avoid_days.map((d) => DAY_LABELS[d]).join(", ")}`);
  if (c.earliest_start) chips.push(`After ${c.earliest_start}`);
  if (c.latest_end) chips.push(`Before ${c.latest_end}`);
  if (c.min_credits && c.max_credits) chips.push(`${c.min_credits}–${c.max_credits} credits`);
  else if (c.min_credits) chips.push(`Min ${c.min_credits} credits`);
  else if (c.max_credits) chips.push(`Max ${c.max_credits} credits`);
  if (c.preferred_modality) chips.push(MODE_LABELS[c.preferred_modality] ?? c.preferred_modality);
  if (c.only_open) chips.push("Open sections only");
  if (c.compact_schedule) chips.push("Compact schedule");
  if (c.prefer_time_of_day) chips.push(`${TIME_OF_DAY_LABELS[c.prefer_time_of_day]} classes`);
  return chips;
}

type Step = "input" | "confirming" | "results";

export default function ChatPage() {
  return (
    <AuthGate>
      <ChatFlow />
    </AuthGate>
  );
}

function ChatFlow() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("input");
  const [chatText, setChatText] = useState("");
  const [constraints, setConstraints] = useState<Constraints>(emptyConstraints());
  const [showEdit, setShowEdit] = useState(false);
  const [profile, setProfile] = useState<RequirementProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [schedules, setSchedules] = useState<ScheduleOut[]>([]);
  const [parsing, setParsing] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the confirmed requirement profile once we're inside the authed flow.
  // No profile means the student hasn't onboarded yet → send them there.
  useEffect(() => {
    let active = true;
    loadProfile()
      .then((loaded) => {
        if (!active) return;
        if (loaded === null) {
          router.replace("/onboarding");
          return;
        }
        setProfile(loaded);
        setProfileLoaded(true);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load your plan");
        setProfileLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [router]);

  // Scheduler input derived from the confirmed profile (no manual picking).
  const requirements: Requirement[] = profile ? profileToRequirements(profile) : [];
  const courseKeys: string[] = [...new Set(requirements.flatMap((req) => req.course_keys))];

  async function handleParse(e: React.FormEvent) {
    e.preventDefault();
    if (!chatText.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const parsed = await parseConstraints(chatText);
      setConstraints({
        avoid_days: parsed.avoid_days,
        earliest_start: parsed.earliest_start ?? "",
        latest_end: parsed.latest_end ?? "",
        min_credits: parsed.min_credits != null ? String(parsed.min_credits) : "",
        max_credits: parsed.max_credits != null ? String(parsed.max_credits) : "",
        preferred_modality: parsed.preferred_modality ?? "",
        only_open: parsed.only_open ?? false,
        compact_schedule: parsed.compact_schedule ?? false,
        prefer_time_of_day: (parsed.prefer_time_of_day ?? "") as TimeOfDay,
      });
      setStep("confirming");
      setShowEdit(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setParsing(false);
    }
  }

  async function handleSchedule(e: React.FormEvent) {
    e.preventDefault();
    if (requirements.length === 0) return;
    setScheduling(true);
    setError(null);
    try {
      const data = await getSchedule({
        requirements,
        constraints: toApiConstraints(constraints),
        max_results: 50,
      });
      setSchedules(data.schedules);
      setStep("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Schedule failed");
    } finally {
      setScheduling(false);
    }
  }

  function toggleAvoidDay(day: Day) {
    setConstraints((c) => ({
      ...c,
      avoid_days: c.avoid_days.includes(day)
        ? c.avoid_days.filter((d) => d !== day)
        : [...c.avoid_days, day],
    }));
  }

  function reset() {
    setStep("input");
    setChatText("");
    setConstraints(emptyConstraints());
    setSchedules([]);
    setError(null);
    setShowEdit(false);
  }

  const chips = summaryChips(constraints);

  // Profile still loading (and no error yet) → hold the flow with a placeholder.
  if (!profileLoaded && error === null) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Chat Scheduler</h1>
        <p className="text-sm text-zinc-500">Loading your plan…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Chat Scheduler</h1>
      <p className="mb-8 text-sm text-zinc-500">Fall 2026 · CSE courses · M3 prototype</p>

      {/* Signed-in profile with nothing to schedule → dead-end guard. */}
      {step === "input" && profileLoaded && courseKeys.length === 0 && (
        <div className="space-y-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-300">
            Your plan doesn&rsquo;t have any schedulable courses yet. Open your profile to resolve
            your remaining requirements into concrete courses, then come back to build a schedule.
          </p>
          <button
            type="button"
            onClick={() => router.push("/onboarding")}
            className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Edit profile
          </button>
          {error && <ErrorBanner message={error} />}
        </div>
      )}

      {/* ── Step 1: Chat input ───────────────────────────────────────────────── */}
      {step === "input" && courseKeys.length > 0 && (
        <form onSubmit={handleParse} className="space-y-4">
          <label
            htmlFor="chat-input"
            className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
          >
            Describe your scheduling preferences
          </label>
          <textarea
            id="chat-input"
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            rows={3}
            placeholder="e.g. no Friday classes, nothing before 10am, 12–15 credits"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          />
          <button
            type="submit"
            disabled={parsing || !chatText.trim()}
            className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {parsing ? "Parsing…" : "Parse preferences"}
          </button>
          {error && <ErrorBanner message={error} />}
        </form>
      )}

      {/* ── Step 2: Confirm constraints + confirmed courses ──────────────────── */}
      {step === "confirming" && (
        <div className="space-y-8">
          {/* User utterance echo */}
          <blockquote className="border-l-2 border-zinc-300 pl-4 text-sm text-zinc-500 italic dark:border-zinc-600">
            &ldquo;{chatText}&rdquo;
          </blockquote>

          {/* Parsed constraints summary */}
          <section>
            <h2 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Understood
            </h2>
            {chips.length === 0 ? (
              <p className="text-sm text-zinc-400">No constraints detected.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {chips.map((chip) => (
                  <span
                    key={chip}
                    className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={() => setShowEdit((v) => !v)}
              className="mt-3 text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
            >
              {showEdit ? "Hide editor" : "Edit / correct constraints"}
            </button>
          </section>

          {/* Editable constraint form */}
          {showEdit && (
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <div className="space-y-4">
                <div>
                  <p className="mb-1.5 text-xs text-zinc-500">Avoid days</p>
                  <div className="flex flex-wrap gap-2">
                    {DAYS.map((d) => {
                      const on = constraints.avoid_days.includes(d);
                      return (
                        <button
                          key={d}
                          type="button"
                          onClick={() => toggleAvoidDay(d)}
                          className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                            on
                              ? "bg-red-500 text-white"
                              : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
                          }`}
                        >
                          {DAY_LABELS[d]}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex flex-wrap gap-4">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Earliest start</label>
                    <input
                      type="time"
                      value={constraints.earliest_start}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, earliest_start: e.target.value }))
                      }
                      className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Latest end</label>
                    <input
                      type="time"
                      value={constraints.latest_end}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, latest_end: e.target.value }))
                      }
                      className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap gap-4">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Min credits</label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={constraints.min_credits}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, min_credits: e.target.value }))
                      }
                      className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Max credits</label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={constraints.max_credits}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, max_credits: e.target.value }))
                      }
                      className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap gap-4">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Modality</label>
                    <select
                      value={constraints.preferred_modality}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, preferred_modality: e.target.value }))
                      }
                      className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    >
                      <option value="">Any</option>
                      <option value="P">In Person</option>
                      <option value="OL">Online</option>
                      <option value="HY">Hybrid</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Preferred time of day</label>
                    <select
                      value={constraints.prefer_time_of_day}
                      onChange={(e) =>
                        setConstraints((c) => ({
                          ...c,
                          prefer_time_of_day: e.target.value as TimeOfDay,
                        }))
                      }
                      className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                    >
                      <option value="">Any</option>
                      <option value="morning">Morning</option>
                      <option value="afternoon">Afternoon</option>
                      <option value="evening">Evening</option>
                    </select>
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300">
                    <input
                      type="checkbox"
                      checked={constraints.only_open}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, only_open: e.target.checked }))
                      }
                      className="h-3.5 w-3.5 rounded border-zinc-300 dark:border-zinc-600"
                    />
                    Only open sections
                  </label>
                  <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300">
                    <input
                      type="checkbox"
                      checked={constraints.compact_schedule}
                      onChange={(e) =>
                        setConstraints((c) => ({ ...c, compact_schedule: e.target.checked }))
                      }
                      className="h-3.5 w-3.5 rounded border-zinc-300 dark:border-zinc-600"
                    />
                    Compact schedule (minimize gaps)
                  </label>
                </div>
              </div>
            </section>
          )}

          {/* Confirmed courses (read-only) + submit */}
          <form onSubmit={handleSchedule} className="space-y-6">
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Scheduling for
                </h2>
                <button
                  type="button"
                  onClick={() => router.push("/onboarding")}
                  className="text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
                >
                  Edit profile
                </button>
              </div>
              {courseKeys.length === 0 ? (
                <p className="text-sm text-zinc-500">
                  Your plan has no schedulable courses yet. Resolve your remaining requirements into
                  concrete courses, then come back.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {courseKeys.map((key) => (
                    <span
                      key={key}
                      className="rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                    >
                      {key}
                    </span>
                  ))}
                </div>
              )}
            </section>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={scheduling || courseKeys.length === 0}
                className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
              >
                {scheduling ? "Finding schedules…" : "Build schedule"}
              </button>
              <button
                type="button"
                onClick={reset}
                className="rounded-full border border-zinc-300 px-6 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Start over
              </button>
            </div>

            {error && <ErrorBanner message={error} />}
          </form>
        </div>
      )}

      {/* ── Step 3: Results ──────────────────────────────────────────────────── */}
      {step === "results" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              {schedules.length === 0
                ? "No valid schedules found."
                : `${schedules.length} schedule${schedules.length === 1 ? "" : "s"} found`}
            </h2>
            <button
              type="button"
              onClick={reset}
              className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Start over
            </button>
          </div>

          <div className="space-y-4">
            {schedules.map((sched, i) => (
              <ScheduleCard key={i} schedule={sched} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
      {message}
    </p>
  );
}
