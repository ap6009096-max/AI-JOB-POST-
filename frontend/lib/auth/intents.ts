export const AUTH_INTENTS = ["candidate", "recruiter", "company"] as const;

export type AuthIntent = (typeof AUTH_INTENTS)[number];

export const OAUTH_INTENT_KEY = "aijp_oauth_intent";
export const OAUTH_COMPANY_KEY = "aijp_oauth_company";

export function isAuthIntent(value: string | null | undefined): value is AuthIntent {
  return typeof value === "string" && (AUTH_INTENTS as readonly string[]).includes(value);
}

export function parseAuthIntent(value: string | null | undefined): AuthIntent {
  return isAuthIntent(value) ? value : "candidate";
}

export function loginPathForIntent(intent: AuthIntent): string {
  return `/login/${intent}`;
}

export function roleForIntent(intent: AuthIntent): "candidate" | "recruiter" | "company_admin" {
  if (intent === "company") {
    return "company_admin";
  }
  return intent;
}

export function roleMatchesIntent(role: string | null | undefined, intent: AuthIntent): boolean {
  return role === roleForIntent(intent);
}

export function intentFromAuthPath(pathname: string): AuthIntent | null {
  const match = /^\/(login|signup)\/([^/]+)\/?$/.exec(pathname);
  if (!match) {
    return null;
  }
  return isAuthIntent(match[2]) ? match[2] : null;
}

export function shouldRedirectSignedInFromAuth(
  role: string | null | undefined,
  pathname: string,
): boolean {
  const intent = intentFromAuthPath(pathname);
  return Boolean(intent && role && roleMatchesIntent(role, intent));
}

export function loginPathForRole(role: string): string {
  if (role === "candidate") {
    return "/login/candidate";
  }
  if (role === "recruiter") {
    return "/login/recruiter";
  }
  return "/login/company";
}

export function roleMismatchMessage(intent: AuthIntent, existingRole?: string | null): string {
  const existing = roleNoun(existingRole);
  const otherPortal = portalNameForRole(existingRole);
  if (otherPortal) {
    return `This Google account is already a ${existing}. Use ${otherPortal} sign-in, or a different Google account.`;
  }
  return `This Google account is already a ${existing}. Use the matching sign-in page, or a different Google account.`;
}

function roleNoun(role: string | null | undefined): string {
  if (role === "company_admin") {
    return "company admin";
  }
  if (role === "platform_admin") {
    return "platform admin";
  }
  if (role === "recruiter") {
    return "recruiter";
  }
  if (role === "candidate") {
    return "candidate";
  }
  return "different type of user";
}

function portalNameForRole(role: string | null | undefined): string | null {
  if (role === "company_admin" || role === "platform_admin") {
    return "Company";
  }
  if (role === "recruiter") {
    return "Recruiter";
  }
  if (role === "candidate") {
    return "Candidate";
  }
  return null;
}
