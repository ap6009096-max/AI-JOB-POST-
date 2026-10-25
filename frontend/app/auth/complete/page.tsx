"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { bootstrapAuth } from "@/lib/api";
import { defaultHome, isAppRole, type AppRole } from "@/lib/auth/access";
import {
  loginPathForIntent,
  OAUTH_COMPANY_KEY,
  OAUTH_INTENT_KEY,
  parseAuthIntent,
  roleForIntent,
  roleMatchesIntent,
} from "@/lib/auth/intents";
import { createClient } from "@/lib/supabase/client";

export default function AuthCompletePage() {
  return (
    <Suspense
      fallback={
        <main className="flex flex-1 items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
          <p className="text-sm text-zinc-600">Finishing Google sign-in…</p>
        </main>
      }
    >
      <CompleteSession />
    </Suspense>
  );
}

function CompleteSession() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function finish() {
      const storedIntent = window.sessionStorage.getItem(OAUTH_INTENT_KEY);
      const intent = parseAuthIntent(searchParams.get("intent") ?? storedIntent);
      const companyName = window.sessionStorage.getItem(OAUTH_COMPANY_KEY) ?? "";
      setError(null);

      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace(`${loginPathForIntent(intent)}?error=oauth`);
          return;
        }

        const metadata = user.user_metadata ?? {};
        const fullName =
          (typeof metadata.full_name === "string" && metadata.full_name) ||
          (typeof metadata.name === "string" && metadata.name) ||
          "";

        const me = await bootstrapAuth({
          intent,
          full_name: fullName,
          company_name: companyName || undefined,
        });
        await supabase.auth.refreshSession();
        window.sessionStorage.removeItem(OAUTH_INTENT_KEY);
        window.sessionStorage.removeItem(OAUTH_COMPANY_KEY);
        if (cancelled) {
          return;
        }
        const role = (isAppRole(me.role) ? me.role : roleForIntent(intent)) as AppRole;
        if (!roleMatchesIntent(role, intent)) {
          router.replace(
            `${loginPathForIntent(intent)}?error=role&existing=${encodeURIComponent(role)}`,
          );
          return;
        }
        router.replace(defaultHome(role));
        router.refresh();
      } catch (caught) {
        if (cancelled) {
          return;
        }
        setError(caught instanceof Error ? caught.message : "Google sign-in failed");
      }
    }

    void finish();
    return () => {
      cancelled = true;
    };
  }, [router, searchParams, retryKey]);

  return (
    <main className="flex flex-1 items-center justify-center bg-zinc-50 px-6 py-16 dark:bg-black">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
        {error ? (
          <>
            <h1 className="text-xl font-semibold tracking-tight">Could not finish sign-in</h1>
            <p className="mt-2 text-sm text-red-600">{error}</p>
            <p className="mt-4 text-sm text-zinc-600">
              Google already signed you in. The app still needs the API on port 8000 to create
              your profile.
            </p>
            <div className="mt-6 flex justify-center gap-4 text-sm">
              <button className="underline" type="button" onClick={() => setRetryKey((value) => value + 1)}>
                Try again
              </button>
              <button
                className="underline"
                type="button"
                onClick={() => {
                  const storedIntent = window.sessionStorage.getItem(OAUTH_INTENT_KEY);
                  router.replace(
                    loginPathForIntent(parseAuthIntent(searchParams.get("intent") ?? storedIntent)),
                  );
                }}
              >
                Back to sign in
              </button>
            </div>
          </>
        ) : (
          <>
            <h1 className="text-xl font-semibold tracking-tight">Finishing Google sign-in</h1>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Please wait…</p>
          </>
        )}
      </div>
    </main>
  );
}
