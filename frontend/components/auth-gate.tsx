"use client";

import { useEffect, useState } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { getBrowserSupabase } from "@/lib/supabase";

type AuthState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "link_sent"; email: string }
  | { status: "signed_in"; session: Session };

export function AuthGate({ children }: { children: React.ReactNode }) {
  // Created lazily on the client so the page can statically prerender (server returns null).
  const [supabase] = useState<SupabaseClient | null>(() =>
    typeof window === "undefined" ? null : getBrowserSupabase(),
  );
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data: { session } }) => {
      setAuth(session ? { status: "signed_in", session } : { status: "signed_out" });
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      // Keep "check your email" on screen instead of flashing back to the form.
      setAuth((prev) =>
        session
          ? { status: "signed_in", session }
          : prev.status === "link_sent"
            ? prev
            : { status: "signed_out" },
      );
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  async function handleSendLink(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase || !email.trim()) return;
    setSending(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.href },
    });
    setSending(false);
    if (err) {
      setError(err.message);
    } else {
      setAuth({ status: "link_sent", email: email.trim() });
    }
  }

  if (auth.status === "loading") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
        <p className="text-sm text-zinc-400">Loading…</p>
      </div>
    );
  }

  if (auth.status === "link_sent") {
    return (
      <div className="mx-auto max-w-sm px-4 py-20 text-center font-sans">
        <h1 className="mb-2 text-xl font-semibold tracking-tight">Check your email</h1>
        <p className="text-sm text-zinc-500">
          We sent a sign-in link to <span className="font-medium">{auth.email}</span>. Open it on
          this device to continue.
        </p>
        <button
          type="button"
          onClick={() => setAuth({ status: "signed_out" })}
          className="mt-6 text-xs text-zinc-400 underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
        >
          Use a different email
        </button>
      </div>
    );
  }

  if (auth.status === "signed_out") {
    return (
      <div className="mx-auto max-w-sm px-4 py-20 font-sans">
        <h1 className="mb-1 text-xl font-semibold tracking-tight">Sign in</h1>
        <p className="mb-6 text-sm text-zinc-500">
          Enter your email and we&rsquo;ll send you a magic link — no password needed.
        </p>
        <form onSubmit={handleSendLink} className="space-y-4">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@asu.edu"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          />
          <button
            type="submit"
            disabled={sending || !email.trim()}
            className="w-full rounded-full bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {sending ? "Sending…" : "Send magic link"}
          </button>
          {error && (
            <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </p>
          )}
        </form>
      </div>
    );
  }

  return (
    <>
      <div className="mx-auto flex max-w-2xl items-center justify-end gap-3 px-4 pt-4 font-sans text-xs text-zinc-400">
        <span>{auth.session.user.email}</span>
        <button
          type="button"
          onClick={() => supabase?.auth.signOut()}
          className="underline underline-offset-2 hover:text-zinc-600 dark:hover:text-zinc-200"
        >
          Sign out
        </button>
      </div>
      {children}
    </>
  );
}
