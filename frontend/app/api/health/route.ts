import { appConfig, isSupabaseConfigured } from "@/lib/config";
import { logger } from "@/lib/logger";

export async function GET() {
  logger.info("frontend_health_checked");

  return Response.json({
    status: "ok",
    service: "ai-job-post-frontend",
    supabaseConfigured: isSupabaseConfigured(),
    apiUrl: appConfig.apiUrl,
  });
}
