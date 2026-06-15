"use client";

import { useState } from "react";

import type { ScheduleOut, SectionDetail } from "@/lib/api-types";

const MODE_LABELS: Record<string, string> = {
  P: "In Person",
  OL: "Online",
  HY: "Hybrid",
  ICOURSE: "iCourse",
};

/** Open / Waitlisted / Closed pill driven by a section's enrollment status. */
function SeatBadge({ section }: { section: SectionDetail }) {
  if (section.is_open) {
    return (
      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700 dark:bg-green-950 dark:text-green-300">
        Open
      </span>
    );
  }
  if (section.enrl_stat === "W") {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
        Waitlist
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-zinc-200 px-2 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
      Closed
    </span>
  );
}

export function ScheduleCard({ schedule, index }: { schedule: ScheduleOut; index: number }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard
      .writeText(schedule.sections.map((s) => s.id).join(", "))
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
          Schedule {index + 1}
          <span className="ml-2 text-zinc-400">·</span>
          <span className="ml-2 text-zinc-500">{schedule.total_credits} cr</span>
        </span>
        <button
          type="button"
          onClick={copy}
          className="rounded px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
        >
          {copied ? "Copied!" : "Copy class #s"}
        </button>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-zinc-400">
            <th className="pr-4 pb-1 font-medium">Class #</th>
            <th className="pr-4 pb-1 font-medium">Course</th>
            <th className="pr-4 pb-1 font-medium">Type</th>
            <th className="pr-4 pb-1 font-medium">Mode</th>
            <th className="pr-4 pb-1 font-medium">Seats</th>
            <th className="pr-4 pb-1 font-medium">Instructor</th>
            <th className="pr-4 pb-1 font-medium">Days</th>
            <th className="pb-1 font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {schedule.sections.map((sec) => (
            <tr key={sec.id} className="border-t border-zinc-100 dark:border-zinc-800">
              <td className="py-1 pr-4 font-mono text-zinc-500">{sec.id}</td>
              <td className="py-1 pr-4 font-medium text-zinc-800 dark:text-zinc-100">
                {sec.course_key}
              </td>
              <td className="py-1 pr-4 text-zinc-500">{sec.component}</td>
              <td className="py-1 pr-4 text-zinc-500">
                {MODE_LABELS[sec.instruction_mode] ?? sec.instruction_mode}
              </td>
              <td className="py-1 pr-4">
                <SeatBadge section={sec} />
              </td>
              <td className="py-1 pr-4 text-zinc-500">
                {sec.instructors.length > 0 ? sec.instructors.join(", ") : "TBA"}
              </td>
              <td className="py-1 pr-4 text-zinc-500">{sec.days || "—"}</td>
              <td className="py-1 text-zinc-500">{sec.time_range}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
