"use client";

import { useParams } from "next/navigation";

import { InternetCandidateDetails } from "@/components/dashboard/internet-candidate-details";

export default function SourceDetailsPage() {
  const params = useParams<{ jobId: string; candidateId: string }>();
  return <InternetCandidateDetails jobId={params.jobId} candidateId={params.candidateId} />;
}
