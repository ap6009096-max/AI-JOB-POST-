"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listJobs } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch((caught: Error) => setError(caught.message));
  }, []);

  return (
    <DashboardShell eyebrow="Jobs" title="Jobs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Drafts stay unpublished until you confirm Publish.
        </p>
        <Link href="/dashboard/jobs/new" className={cn(buttonVariants(), "inline-flex")}>
          Create Job
        </Link>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {jobs.length === 0 && !error ? (
        <p className="text-sm text-zinc-500">No jobs yet. Create a draft to get started.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{job.title}</p>
                  <Badge variant={job.status === "open" ? "default" : "secondary"}>{job.status ?? "draft"}</Badge>
                </div>
                <p className="text-sm text-zinc-500">
                  {job.location || job.requirements.location || "Location not set"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/dashboard/jobs/${job.id}/edit`}
                  className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}
                >
                  Edit
                </Link>
                <Link
                  href={`/dashboard/jobs/${job.id}/preview`}
                  className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}
                >
                  Preview
                </Link>
                <Link
                  href={`/dashboard/jobs/${job.id}/portal`}
                  className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}
                >
                  Portal ranking
                </Link>
                <Link
                  href={`/dashboard/jobs/${job.id}/internet`}
                  className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}
                >
                  Internet search
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </DashboardShell>
  );
}
