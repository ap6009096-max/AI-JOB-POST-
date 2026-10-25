"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { bootstrapAuth } from "@/lib/api";
import { defaultHome, isAppRole, type AppRole } from "@/lib/auth/access";
import {
  loginPathForRole,
  OAUTH_COMPANY_KEY,
  OAUTH_INTENT_KEY,
  roleForIntent,
  roleMatchesIntent,
  roleMismatchMessage,
  type AuthIntent,
} from "@/lib/auth/intents";
import { appConfig } from "@/lib/config";
import { createClient } from "@/lib/supabase/client";

const COPY: Record<
  AuthIntent,
  { title: string; signup: string; login: string; homeHint: string }
> = {
  candidate: {
    title: "Candidate",
    signup: "Create a candidate account",
    login: "Sign in as a candidate",
    homeHint: "Your profile stays private to you.",
  },
  recruiter: {
    title: "Recruiter",
    signup: "Create a recruiter account",
    login: "Sign in as a recruiter",
    homeHint: "A company admin must add you before dashboard access.",
  },
  company: {
    title: "Company",
    signup: "Create a company admin account",
    login: "Sign in as a company admin",
    homeHint: "Manage jobs, recruiters, and ranking.",
  },
};

export function AuthForm({
  intent,
  mode,
}: {
  intent: AuthIntent;
  mode: "login" | "signup";
}) {
  const router = useRouter();
  const copy = COPY[intent];
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [existingRole, setExistingRole] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("error");
    if (code === "oauth") {
      setExistingRole(null);
      setError("Google sign-in was cancelled or failed. Try again.");
      return;
    }
    if (code === "role") {
      const existing = params.get("existing");
      setExistingRole(existing);
      setError(roleMismatchMessage(intent, existing));
    }
  }, [intent]);

  async function startGoogle(options?: { switchAccount?: boolean }) {
    setError(null);
    setMessage(null);
    if (mode === "signup" && intent === "company" && !companyName.trim()) {
      setError("Enter a company name before continuing with Google.");
      return;
    }
    setPending(true);
    try {
      window.sessionStorage.setItem(OAUTH_INTENT_KEY, intent);
      if (companyName.trim()) {
        window.sessionStorage.setItem(OAUTH_COMPANY_KEY, companyName.trim());
      } else {
        window.sessionStorage.removeItem(OAUTH_COMPANY_KEY);
      }
      const supabase = createClient();
      if (options?.switchAccount) {
        await supabase.auth.signOut();
      }
      const redirectTo = `${appConfig.siteUrl || window.location.origin}/auth/callback?intent=${intent}`;
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo,
          queryParams: options?.switchAccount ? { prompt: "select_account" } : undefined,
        },
      });
      if (oauthError) {
        throw oauthError;
      }
    } catch (caught) {
      setPending(false);
      setError(caught instanceof Error ? caught.message : "Google sign-in failed");
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (mode === "signup" && intent === "company" && !companyName.trim()) {
      setError("Enter a company name.");
      return;
    }
    setPending(true);
    try {
      const supabase = createClient();
      if (mode === "signup") {
        const { data, error: signError } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } },
        });
        if (signError) {
          throw signError;
        }
        if (!data.session) {
          setMessage("Check your email to confirm your account, then sign in.");
          return;
        }
      } else {
        const { error: signError } = await supabase.auth.signInWithPassword({ email, password });
        if (signError) {
          throw signError;
        }
      }

      const me = await bootstrapAuth({
        intent,
        full_name: fullName,
        company_name: companyName || undefined,
      });
      await supabase.auth.refreshSession();
      const role = (isAppRole(me.role) ? me.role : roleForIntent(intent)) as AppRole;
      if (!roleMatchesIntent(role, intent)) {
        setExistingRole(role);
        setError(roleMismatchMessage(intent, role));
        return;
      }
      router.push(defaultHome(role));
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed");
    } finally {
      setPending(false);
    }
  }

  const otherMode = mode === "login" ? "signup" : "login";
  const otherHref = `/${otherMode}/${intent === "company" ? "company" : intent}`;

  return (
    <div className="mx-auto w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-sm font-medium tracking-wide text-zinc-500 uppercase">{copy.title}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        {mode === "signup" ? copy.signup : copy.login}
      </h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{copy.homeHint}</p>
      {mode === "signup" && intent === "company" ? (
        <div className="mt-6 flex flex-col gap-2">
          <Label htmlFor="company_name">Company name</Label>
          <Input
            id="company_name"
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            required
          />
        </div>
      ) : null}
      <div className={mode === "signup" && intent === "company" ? "mt-4 flex flex-col gap-4" : "mt-6 flex flex-col gap-4"}>
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          onClick={() => void startGoogle({ switchAccount: Boolean(existingRole) })}
        >
          <GoogleMark />
          Continue with Google
        </Button>
        <div className="flex items-center gap-3 text-xs tracking-wide text-zinc-500 uppercase">
          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
          or
          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
        </div>
      </div>
      <form className="mt-4 flex flex-col gap-4" onSubmit={onSubmit}>
        {mode === "signup" ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="full_name">Full name</Label>
            <Input
              id="full_name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              autoComplete="name"
            />
          </div>
        ) : null}
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
            suppressHydrationWarning
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        {existingRole ? (
          <div className="flex flex-col gap-2 text-sm">
            <button
              className="underline"
              type="button"
              disabled={pending}
              onClick={() => void startGoogle({ switchAccount: true })}
            >
              Use a different account
            </button>
            <Link className="underline" href={loginPathForRole(existingRole)}>
              Go to {existingRole === "candidate" ? "candidate" : existingRole === "recruiter" ? "recruiter" : "company"} sign-in
            </Link>
          </div>
        ) : null}
        {message ? <p className="text-sm text-zinc-600">{message}</p> : null}
        <Button type="submit" disabled={pending}>
          {pending ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">
        {mode === "login" ? "Need an account?" : "Already registered?"}{" "}
        <Link className="underline" href={otherHref}>
          {mode === "login" ? "Sign up" : "Sign in"}
        </Link>
      </p>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.2-2.27H12v4.3h6.46c-.28 1.5-1.12 2.77-2.39 3.63v3.02h3.87c2.26-2.08 3.55-5.14 3.55-8.68"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.9l-3.87-3.02c-1.08.72-2.45 1.15-4.08 1.15-3.14 0-5.8-2.12-6.75-4.97H1.26v3.12C3.24 21.3 7.31 24 12 24"
      />
      <path
        fill="#FBBC05"
        d="M5.25 14.26c-.24-.72-.38-1.49-.38-2.26s.14-1.54.38-2.26V6.62H1.26C.46 8.21 0 10.05 0 12s.46 3.79 1.26 5.38z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.76 0 3.35.6 4.6 1.79l3.45-3.45C17.95 1.14 15.24 0 12 0 7.31 0 3.24 2.7 1.26 6.62l3.99 3.12C6.2 6.87 8.86 4.75 12 4.75"
      />
    </svg>
  );
}
