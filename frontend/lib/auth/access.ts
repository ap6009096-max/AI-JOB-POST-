export const APP_ROLES = ["candidate", "recruiter", "company_admin", "platform_admin"] as const;

export type AppRole = (typeof APP_ROLES)[number];

export function isAppRole(value: unknown): value is AppRole {
  return typeof value === "string" && (APP_ROLES as readonly string[]).includes(value);
}

export function roleFromClaims(claims: Record<string, unknown> | null | undefined): AppRole | null {
  if (!claims) {
    return null;
  }
  const metadata = claims.app_metadata;
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  const role = (metadata as { role?: unknown }).role;
  return isAppRole(role) ? role : null;
}

export function loginPathForPathname(pathname: string): string {
  if (pathname === "/candidate" || pathname.startsWith("/candidate/")) {
    return "/login/candidate";
  }
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    return "/login/company";
  }
  return "/login/company";
}

export function defaultHome(role: AppRole): string {
  if (role === "candidate") {
    return "/candidate";
  }
  if (role === "platform_admin") {
    return "/admin";
  }
  return "/dashboard";
}

export function canAccessPath(role: AppRole | null, pathname: string): boolean {
  const isDashboard = pathname === "/dashboard" || pathname.startsWith("/dashboard/");
  const isCandidate = pathname === "/candidate" || pathname.startsWith("/candidate/");
  const isAdmin = pathname === "/admin" || pathname.startsWith("/admin/");

  if (!isDashboard && !isCandidate && !isAdmin) {
    return true;
  }
  if (!role) {
    return false;
  }
  if (isAdmin) {
    return role === "platform_admin";
  }
  if (isCandidate) {
    return role === "candidate" || role === "platform_admin";
  }
  return role === "recruiter" || role === "company_admin" || role === "platform_admin";
}

export function redirectForDenied(role: AppRole | null, pathname: string): string | null {
  if (canAccessPath(role, pathname)) {
    return null;
  }
  if (!role) {
    return loginPathForPathname(pathname);
  }
  if (role === "candidate") {
    return "/candidate";
  }
  if (role === "recruiter" || role === "company_admin") {
    return "/dashboard";
  }
  return "/";
}
