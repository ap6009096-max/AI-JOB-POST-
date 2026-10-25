import { createBrowserClient } from "@supabase/ssr";
import { appConfig, isSupabaseConfigured } from "@/lib/config";

export function createClient() {
  if (!isSupabaseConfigured()) {
    throw new Error("Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.");
  }

  return createBrowserClient(appConfig.supabaseUrl, appConfig.supabasePublishableKey);
}
