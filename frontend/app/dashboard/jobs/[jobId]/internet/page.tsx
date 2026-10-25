"use client";

import { useParams } from "next/navigation";

import { InternetTalentDashboard } from "@/components/dashboard/internet-talent-dashboard";

export default function InternetTalentPage() {
  const params = useParams<{ jobId: string }>();
  return <InternetTalentDashboard jobId={params.jobId} />;
}
