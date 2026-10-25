"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/types";

export function JobPicker({
  jobs,
  track,
  emptyHint,
}: {
  jobs: Job[];
  track: "portal" | "internet";
  emptyHint?: string;
}) {
  if (jobs.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {emptyHint ?? "Create a job before ranking talent."}
        </p>
        <Link href="/dashboard/jobs/new" className={cn(buttonVariants(), "inline-flex w-fit")}>
          Create Job
        </Link>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {jobs.map((job) => (
        <li
          key={job.id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div>
            <p className="font-medium">{job.title}</p>
            <p className="text-sm text-zinc-500">
              {job.location || job.requirements.location || "Location not set"}
              {job.status ? ` · ${job.status}` : ""}
            </p>
          </div>
          <Link
            href={`/dashboard/jobs/${job.id}/${track}`}
            className={cn(buttonVariants(), "inline-flex")}
          >
            Rank
          </Link>
        </li>
      ))}
    </ul>
  );
}
