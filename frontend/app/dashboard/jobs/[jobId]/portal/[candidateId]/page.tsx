"use client";

import { useParams } from "next/navigation";

import { PortalCandidateDetails } from "@/components/dashboard/portal-candidate-details";

export default function PortalDetailsPage() {
  const params = useParams<{ jobId: string; candidateId: string }>();
  return <PortalCandidateDetails jobId={params.jobId} candidateId={params.candidateId} />;
}
