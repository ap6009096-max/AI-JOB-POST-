import { redirect } from "next/navigation";

import { canAccessPath, loginPathForPathname, redirectForDenied, roleFromClaims } from "@/lib/auth/access";
import { isSupabaseConfigured } from "@/lib/config";
import { createClient } from "@/lib/supabase/server";

async function guard(pathname: string) {
  if (!isSupabaseConfigured()) {
    return;
  }
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect(loginPathForPathname(pathname));
  }
  const { data } = await supabase.auth.getClaims();
  const role = roleFromClaims(data?.claims as Record<string, unknown> | undefined);
  if (!canAccessPath(role, pathname)) {
    redirect(redirectForDenied(role, pathname) ?? "/");
  }
}

export async function requireDashboardAccess() {
  await guard("/dashboard");
}

export async function requireCandidateAccess() {
  await guard("/candidate");
}

export async function requireAdminAccess() {
  await guard("/admin");
}
