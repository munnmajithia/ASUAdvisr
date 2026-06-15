// Typed client for the ASUAdvisr FastAPI backend.
//
// Every frontend → backend call goes through here so the base URL, request
// shape, and error handling live in one place. Types are defined in
// ./api-types and mirror the backend Pydantic models.

import type {
  CoursesResponse,
  HealthResponse,
  ParsedConstraints,
  ScheduleRequest,
  ScheduleResponse,
} from "@/lib/api-types";
import type { RequirementProfile } from "@/lib/profile";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown for any non-OK response or network failure. `status` is 0 when the
 *  request never reached the server (e.g. backend down, CORS, offline). */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        // Only send a JSON content-type when there's a body to describe; for
        // FormData let the browser set multipart/form-data with its boundary.
        ...(init?.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("Could not reach the API. Is the backend running?", 0);
  }

  if (!res.ok) {
    // FastAPI surfaces errors as `{ detail: string }`; fall back to the status.
    let message = `API error ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Non-JSON error body — keep the default message.
    }
    throw new ApiError(message, res.status);
  }

  return (await res.json()) as T;
}

/** `GET /health` — liveness probe. Not yet called by the app; kept so the
 *  client mirrors the full backend surface (e.g. a future connectivity check). */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

/** `GET /courses` — sorted course keys available in the loaded data source. */
export async function getCourses(): Promise<string[]> {
  const data = await request<CoursesResponse>("/courses");
  return data.courses;
}

/** `POST /parse-constraints` — natural-language preferences → structured constraints. */
export async function parseConstraints(text: string): Promise<ParsedConstraints> {
  return request<ParsedConstraints>("/parse-constraints", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

/** `POST /schedule` — requirements + constraints → ranked conflict-free schedules. */
export async function getSchedule(req: ScheduleRequest): Promise<ScheduleResponse> {
  return request<ScheduleResponse>("/schedule", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/** `POST /extract-requirements` — DARS PDF (multipart `file`) → requirement profile. */
export async function extractProfile(file: File): Promise<RequirementProfile> {
  const form = new FormData();
  form.append("file", file);
  return request<RequirementProfile>("/extract-requirements", { method: "POST", body: form });
}
