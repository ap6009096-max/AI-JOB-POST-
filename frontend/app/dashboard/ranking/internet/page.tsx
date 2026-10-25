"use client";

import { useEffect, useState } from "react";

import { ShaderHero } from "@/components/brand/shader-hero";
import { JobPicker } from "@/components/dashboard/job-picker";
import { listJobs } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function InternetRankingPickerPage() {
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
        shader="spotlight"
        eyebrow="Internet talent search"
        title="Internet Talent Search"
        subtitle="Choose a published job, then search permitted professional sources. Results stay on this track."
      />
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <JobPicker jobs={jobs} track="internet" />
    </div>
  );
}
