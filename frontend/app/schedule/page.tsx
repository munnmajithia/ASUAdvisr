"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
type Day = (typeof DAYS)[number];
const DAY_LABELS: Record<Day, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

interface SectionDetail {
  id: number;
  course_key: string;
  component: string;
  instruction_mode: string;
  days: string;
  time_range: string;
}

interface ScheduleOut {
  sections: SectionDetail[];
  total_credits: number;
}

interface ScheduleResponse {
  schedules: ScheduleOut[];
  count: number;
}

const MODE_LABELS: Record<string, string> = {
  P: "In Person",
  OL: "Online",
  HY: "Hybrid",
  ICOURSE: "iCourse",
};

export default function SchedulePage() {
  const [allCourses, setAllCourses] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [avoidDays, setAvoidDays] = useState<Set<Day>>(new Set());
  const [earliestStart, setEarliestStart] = useState("");
  const [latestEnd, setLatestEnd] = useState("");
  const [results, setResults] = useState<ScheduleOut[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/courses`)
      .then((r) => r.json())
      .then((data: { courses: string[] }) => setAllCourses(data.courses))
      .catch(() => setError("Could not reach the API. Is the backend running?"));
  }, []);

  function toggleCourse(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  function toggleDay(day: Day) {
    setAvoidDays((prev) => {
      const next = new Set(prev);
      next.has(day) ? next.delete(day) : next.add(day);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const body = {
        requirements: [...selected].map((key) => ({ course_keys: [key], pick: 1 })),
        constraints: {
          avoid_days: [...avoidDays],
          earliest_start: earliestStart || null,
          latest_end: latestEnd || null,
        },
        max_results: 50,
      };
      const res = await fetch(`${API_BASE}/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data: ScheduleResponse = await res.json();
      setResults(data.schedules);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function copyClassNumbers(schedule: ScheduleOut) {
    const nums = schedule.sections.map((s) => s.id).join(", ");
    navigator.clipboard.writeText(nums);
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 font-sans">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Schedule Builder</h1>
      <p className="mb-8 text-sm text-zinc-500">Fall 2026 · CSE courses · M2 prototype</p>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Course picker */}
        <section>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-widest text-zinc-400">
            Courses
          </h2>
          {allCourses.length === 0 && !error && (
            <p className="text-sm text-zinc-400">Loading courses…</p>
          )}
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
            {allCourses.map((key) => {
              const on = selected.has(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleCourse(key)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                    on
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                  }`}
                >
                  {key}
                </button>
              );
            })}
          </div>
        </section>

        {/* Constraints */}
        <section>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-widest text-zinc-400">
            Constraints
          </h2>
          <div className="flex flex-wrap gap-6">
            {/* Avoid days */}
            <div>
              <p className="mb-1.5 text-xs text-zinc-500">Avoid days</p>
              <div className="flex gap-2">
                {DAYS.map((d) => {
                  const on = avoidDays.has(d);
                  return (
                    <button
                      key={d}
                      type="button"
                      onClick={() => toggleDay(d)}
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

            {/* Time window */}
            <div className="flex gap-4">
              <div>
                <label className="mb-1 block text-xs text-zinc-500" htmlFor="earliest">
                  Earliest start
                </label>
                <input
                  id="earliest"
                  type="time"
                  value={earliestStart}
                  onChange={(e) => setEarliestStart(e.target.value)}
                  className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-zinc-500" htmlFor="latest">
                  Latest end
                </label>
                <input
                  id="latest"
                  type="time"
                  value={latestEnd}
                  onChange={(e) => setLatestEnd(e.target.value)}
                  className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                />
              </div>
            </div>
          </div>
        </section>

        <button
          type="submit"
          disabled={loading || selected.size === 0}
          className="rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
        >
          {loading ? "Finding schedules…" : "Find schedules"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {/* Results */}
      {results !== null && (
        <div className="mt-10">
          <h2 className="mb-4 text-lg font-semibold">
            {results.length === 0
              ? "No valid schedules found."
              : `${results.length} schedule${results.length === 1 ? "" : "s"} found`}
          </h2>
          <div className="space-y-4">
            {results.map((sched, i) => (
              <div
                key={i}
                className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                    Schedule {i + 1}
                    <span className="ml-2 text-zinc-400">·</span>
                    <span className="ml-2 text-zinc-500">{sched.total_credits} cr</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => copyClassNumbers(sched)}
                    className="rounded px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
                  >
                    Copy class #s
                  </button>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-zinc-400">
                      <th className="pb-1 pr-4 font-medium">Class #</th>
                      <th className="pb-1 pr-4 font-medium">Course</th>
                      <th className="pb-1 pr-4 font-medium">Type</th>
                      <th className="pb-1 pr-4 font-medium">Mode</th>
                      <th className="pb-1 pr-4 font-medium">Days</th>
                      <th className="pb-1 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sched.sections.map((sec) => (
                      <tr
                        key={sec.id}
                        className="border-t border-zinc-100 dark:border-zinc-800"
                      >
                        <td className="py-1 pr-4 font-mono text-zinc-500">{sec.id}</td>
                        <td className="py-1 pr-4 font-medium text-zinc-800 dark:text-zinc-100">
                          {sec.course_key}
                        </td>
                        <td className="py-1 pr-4 text-zinc-500">{sec.component}</td>
                        <td className="py-1 pr-4 text-zinc-500">
                          {MODE_LABELS[sec.instruction_mode] ?? sec.instruction_mode}
                        </td>
                        <td className="py-1 pr-4 text-zinc-500">{sec.days || "—"}</td>
                        <td className="py-1 text-zinc-500">{sec.time_range}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
