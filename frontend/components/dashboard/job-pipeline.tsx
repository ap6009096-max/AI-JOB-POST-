"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { JobCheckStatus, JobPipeline } from "@/lib/types";

const STATUS_LABEL: Record<JobCheckStatus, string> = {
  complete: "✓ Complete",
  missing: "⚠ Missing",
  ambiguous: "⚠ Ambiguous",
  invalid: "✕ Invalid",
};

const STATUS_CLASS: Record<JobCheckStatus, string> = {
  complete: "text-emerald-700 dark:text-emerald-400",
  missing: "text-amber-700 dark:text-amber-400",
  ambiguous: "text-amber-700 dark:text-amber-400",
  invalid: "text-red-600 dark:text-red-400",
};

type JobPipelinePanelProps = {
  pipeline?: JobPipeline | null;
  pending?: boolean;
  error?: string | null;
  onRun: () => void;
};

export function JobPipelinePanel({ pipeline, pending, error, onRun }: JobPipelinePanelProps) {
  const checks = pipeline?.checks ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Job pipeline</CardTitle>
        <CardDescription>
          {pipeline?.status
            ? `Last run: ${pipeline.status.replaceAll("_", " ")}`
            : "Run the job LangGraph to check completeness and produce job.json."}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {pipeline?.review ? <p className="text-sm text-zinc-600 dark:text-zinc-400">{pipeline.review}</p> : null}
        {pipeline?.skipped.length ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Skipped: {pipeline.skipped.map((item) => `${item.node} (${item.reason})`).join(", ")}
          </p>
        ) : null}
        {checks.length ? (
          <ul className="grid gap-1 text-sm">
            {checks.map((check, index) => (
              <li key={`${check.field}-${check.status}-${index}`}>
                <span className={STATUS_CLASS[check.status]}>{STATUS_LABEL[check.status]}</span>
                <span className="text-zinc-700 dark:text-zinc-300"> {check.field}</span>
                {check.message ? <span className="text-zinc-500"> — {check.message}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">No validation results yet.</p>
        )}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <div>
          <Button type="button" variant="outline" disabled={pending} onClick={onRun}>
            {pending ? "Running…" : "Run job pipeline"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
