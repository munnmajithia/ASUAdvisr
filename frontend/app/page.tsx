"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AuthGate } from "@/components/auth-gate";
import { loadProfile } from "@/lib/profile";

/**
 * Routes a signed-in user to the right place. Rendered only inside <AuthGate>,
 * so by the time this mounts there is an authenticated Supabase session and
 * `loadProfile()` can read the user's row directly.
 *
 * Has a profile  → /chat        (ready to schedule)
 * No profile yet → /onboarding  (added by a later task; redirect is wired anyway)
 */
function ProfileRouter() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadProfile()
      .then((profile) => {
        if (!active) return;
        router.replace(profile ? "/chat" : "/onboarding");
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Couldn’t load your profile.");
      });
    return () => {
      active = false;
    };
  }, [router]);

  if (error) {
    return (
      <div className="mx-auto max-w-sm px-4 py-20 text-center font-sans">
        <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 font-sans">
      <p className="text-sm text-zinc-400">Setting things up…</p>
    </div>
  );
}

export default function Home() {
  return (
    <AuthGate>
      <ProfileRouter />
    </AuthGate>
  );
}
