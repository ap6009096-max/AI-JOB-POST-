const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL;
const PUBLIC_ENVIRONMENT = process.env.NEXT_PUBLIC_ENVIRONMENT ?? "local";
const PUBLIC_SITE_URL = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? "";

if (process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY) {
  throw new Error(
    "Never expose SUPABASE_SERVICE_ROLE_KEY to the frontend. Remove NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY.",
  );
}

if (
  !PUBLIC_API_URL &&
  (PUBLIC_ENVIRONMENT === "staging" || PUBLIC_ENVIRONMENT === "production")
) {
  throw new Error(`Missing required configuration for ${PUBLIC_ENVIRONMENT}: NEXT_PUBLIC_API_URL`);
}

export const appConfig = {
  name: "AI Job Post",
  tagline: "AI-Powered Talent Intelligence",
  environment: PUBLIC_ENVIRONMENT,
  apiUrl: PUBLIC_API_URL ?? "http://localhost:8000",
  /** Canonical browser origin for OAuth redirects (production). Empty = use window.location.origin. */
  siteUrl: PUBLIC_SITE_URL,
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabasePublishableKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "",
} as const;

export function isSupabaseConfigured(): boolean {
  return Boolean(appConfig.supabaseUrl && appConfig.supabasePublishableKey);
}
