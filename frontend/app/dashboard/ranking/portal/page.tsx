"use client";

import { useEffect, useState } from "react";

import { ShaderHero } from "@/components/brand/shader-hero";
import { JobPicker } from "@/components/dashboard/job-picker";
import { listJobs } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function PortalRankingPickerPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch((caught: Error) => setError(caught.message));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <ShaderHero
        shader="dots"
        subtle
        eyebrow="Portal ranking"
        title="Portal Ranking"
        subtitle="Choose a published job, then rank registered ai-job-post candidates."
      />
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <JobPicker jobs={jobs} track="portal" />
    </div>
  );
}
