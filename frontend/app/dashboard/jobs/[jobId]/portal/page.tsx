"use client";

import { useParams } from "next/navigation";

import { PortalRankingDashboard } from "@/components/dashboard/portal-ranking-dashboard";

export default function PortalRankingPage() {
  const params = useParams<{ jobId: string }>();
  return <PortalRankingDashboard jobId={params.jobId} />;
}
