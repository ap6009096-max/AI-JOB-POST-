import { NextResponse } from "next/server";

import { defaultHome, isAppRole, roleFromClaims, type AppRole } from "@/lib/auth/access";
import {
  loginPathForIntent,
  parseAuthIntent,
  roleForIntent,
  roleMatchesIntent,
} from "@/lib/auth/intents";
import { appConfig } from "@/lib/config";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const intent = parseAuthIntent(searchParams.get("intent"));

  if (searchParams.get("error")) {
    return NextResponse.redirect(`${origin}${loginPathForIntent(intent)}?error=oauth`);
  }

  if (code) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error && data.session) {
      const metadata = data.session.user.user_metadata ?? {};
      const fullName =
        (typeof metadata.full_name === "string" && metadata.full_name) ||
        (typeof metadata.name === "string" && metadata.name) ||
        "";
      let dest = `/auth/complete?intent=${intent}`;
      try {
        const boot = await fetch(`${appConfig.apiUrl}/v1/auth/bootstrap`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${data.session.access_token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ intent, full_name: fullName }),
        });
        const body = (await boot.json().catch(() => ({}))) as { role?: unknown };
        if (boot.ok) {
          await supabase.auth.refreshSession();
          const { data: claimsData } = await supabase.auth.getClaims();
          const jwtRole = roleFromClaims(claimsData?.claims as Record<string, unknown> | undefined);
          const bodyRole = typeof body.role === "string" && isAppRole(body.role) ? body.role : null;
          const role = (jwtRole ?? bodyRole ?? roleForIntent(intent)) as AppRole;
          dest = roleMatchesIntent(role, intent)
            ? defaultHome(role)
            : `${loginPathForIntent(intent)}?error=role&existing=${encodeURIComponent(role)}`;
        }
      } catch {
        // Fall through to /auth/complete so the client can retry.
      }

      const forwardedHost = request.headers.get("x-forwarded-host");
      const isLocalEnv = process.env.NODE_ENV === "development";
      if (isLocalEnv) {
        return NextResponse.redirect(`${origin}${dest}`);
      }
      if (forwardedHost) {
        return NextResponse.redirect(`https://${forwardedHost}${dest}`);
      }
      return NextResponse.redirect(`${origin}${dest}`);
    }
  }

  return NextResponse.redirect(`${origin}${loginPathForIntent(intent)}?error=oauth`);
}
