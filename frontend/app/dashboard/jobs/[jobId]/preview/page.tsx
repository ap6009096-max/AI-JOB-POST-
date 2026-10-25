"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { JobPipelinePanel } from "@/components/dashboard/job-pipeline";
import { DashboardShell } from "@/components/dashboard/shell";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getJob, publishJob, runJobPipeline } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function PreviewJobPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    getJob(jobId)
      .then(setJob)
      .catch((caught: Error) => setError(caught.message));
  }, [jobId]);

  async function onPublish() {
    setPending(true);
    setError(null);
    try {
      const published = await publishJob(jobId);
      setJob(published);
      router.push("/dashboard/jobs");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Publish failed. Validate the job first.");
    } finally {
      setPending(false);
    }
  }

  async function onRunPipeline() {
    setPending(true);
    setError(null);
    try {
      const next = await runJobPipeline(jobId);
      setJob(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pipeline failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <DashboardShell eyebrow="Jobs" title={job?.title || "Preview job"}>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Standardized job.json. Status: {job?.status ?? "…"}. Publishing requires confirmation.
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Link href={`/dashboard/jobs/${jobId}/edit`} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
          Edit
        </Link>
        {job?.status !== "open" && job?.has_job_json && job.pipeline?.status !== "validation_failed" ? (
          <AlertDialog>
            <AlertDialogTrigger render={<Button type="button" disabled={pending} />}>
              Publish
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Publish this job?</AlertDialogTitle>
                <AlertDialogDescription>
                  It will be used for ranking. This cannot happen automatically.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction type="button" onClick={() => void onPublish()}>
                  Publish
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
            </AlertDialog>
          ) : job?.status === "open" ? (
            <>
              <Link href={`/dashboard/jobs/${jobId}/portal`} className={cn(buttonVariants(), "inline-flex")}>
                Portal Ranking
              </Link>
              <Link href={`/dashboard/jobs/${jobId}/internet`} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                Internet Talent Search
              </Link>
            </>
          ) : (
            <p className="text-sm text-zinc-500">Run the job pipeline to create job.json before publishing.</p>
          )}
      </div>
      <JobPipelinePanel pipeline={job?.pipeline} pending={pending} onRun={() => void onRunPipeline()} />
      {job ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-zinc-500">Job Title</dt>
              <dd>{job.title}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Job Description</dt>
              <dd className="whitespace-pre-wrap">{job.description || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Required Skills</dt>
              <dd>{(job.required_skills ?? job.requirements.skills).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Preferred Skills</dt>
              <dd>{(job.preferred_skills ?? []).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Experience</dt>
              <dd>
                {job.experience?.years ?? job.requirements.experience_years} years
                {job.experience?.text ? ` · ${job.experience.text}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Education</dt>
              <dd>{job.education || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Technologies</dt>
              <dd>{(job.technologies ?? []).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Responsibilities</dt>
              <dd>{(job.responsibilities ?? []).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Location</dt>
              <dd>{job.location || job.requirements.location || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Salary Range</dt>
              <dd>{job.salary_range || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Employment Type</dt>
              <dd>{job.employment_type || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Seniority</dt>
              <dd>{job.seniority || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Certifications</dt>
              <dd>{(job.certifications ?? []).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Openings</dt>
              <dd>{job.openings ?? 1}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Deadline</dt>
              <dd>{job.deadline || "—"}</dd>
            </div>
          </dl>
          <pre className="overflow-auto rounded-xl border border-zinc-200 bg-white p-4 text-xs dark:border-zinc-800 dark:bg-zinc-950">
            {JSON.stringify(job, null, 2)}
          </pre>
        </div>
      ) : null}
    </DashboardShell>
  );
}
