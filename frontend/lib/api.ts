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
import { getBrowserSupabase } from "@/lib/supabase";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Opportunistic auth: include `Authorization: Bearer <token>` when a Supabase
 *  session exists, and nothing otherwise. SSR-safe (no session read on the
 *  server) and failure-tolerant — anonymous calls (e.g. `getCourses`) keep
 *  working since the backend does not verify JWTs. */
async function authHeader(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  try {
    const { data } = await getBrowserSupabase().auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

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
        // Only send a JSON content-type when there's a body to describe.
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        // Attach the bearer token when signed in; harmless when anonymous.
        ...(await authHeader()),
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
