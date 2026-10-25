"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard/shell";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listMatchingRuns } from "@/lib/api";
import type { MatchingRunSummary } from "@/lib/types";

export default function MatchingRunsPage() {
  const [runs, setRuns] = useState<MatchingRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMatchingRuns()
      .then(setRuns)
      .catch((caught: Error) => setError(caught.message));
  }, []);

  return (
    <DashboardShell eyebrow="Matching" title="Matching Runs">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Ranking runs for jobs at your company. Other companies cannot see these results.
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {runs.length === 0 && !error ? (
        <p className="text-sm text-zinc-500">No matching runs yet. Rank a company job to create one.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {runs.map((run) => (
            <li
              key={run.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div>
                <p className="font-medium">{run.job_title || "Job"}</p>
                <p className="text-sm text-zinc-500">
                  {run.track} · {run.status}
                  {run.limit ? ` · top ${run.limit}` : ""}
                  {run.created_at ? ` · ${run.created_at}` : ""}
                </p>
              </div>
              <Link
                href={`/dashboard/jobs/${run.job_id}/${run.track === "internet" ? "internet" : "portal"}`}
                className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}
              >
                Open ranking
              </Link>
            </li>
          ))}
        </ul>
      )}
    </DashboardShell>
  );
}
