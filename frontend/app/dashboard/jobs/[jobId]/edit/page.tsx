"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { AiProgressScreen } from "@/components/brand/ai-progress-screen";
import {
  EMPTY_JOB_FORM,
  JobForm,
  payloadFromValues,
  valuesFromJob,
  type JobFormValues,
} from "@/components/dashboard/job-form";
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
import { getJob, patchJob, publishJob, refreshJobEmbedding, runJobPipeline, validateJob } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function EditJobPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<Job | null>(null);
  const [values, setValues] = useState<JobFormValues>(EMPTY_JOB_FORM);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string[] | null>(null);
  const [pending, setPending] = useState(false);
  const [pipelining, setPipelining] = useState(false);

  useEffect(() => {
    getJob(jobId)
      .then((next) => {
        setJob(next);
        setValues(valuesFromJob(next));
      })
      .catch((caught: Error) => setError(caught.message));
  }, [jobId]);

  async function saveDraft() {
    const updated = await patchJob(jobId, payloadFromValues(values));
    setJob(updated);
    setValues(valuesFromJob(updated));
    return updated;
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await saveDraft();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  async function onValidate() {
    setPending(true);
    setError(null);
    try {
      await saveDraft();
      const result = await validateJob(jobId);
      setValidation(result.valid ? [] : result.errors);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Validate failed");
    } finally {
      setPending(false);
    }
  }

  async function onPublish() {
    setPending(true);
    setError(null);
    try {
      await saveDraft();
      const published = await publishJob(jobId);
      setJob(published);
      router.push(`/dashboard/jobs/${jobId}/preview`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Publish failed. Validate the job first.");
    } finally {
      setPending(false);
    }
  }

  async function onRunPipeline() {
    setPipelining(true);
    setError(null);
    try {
      await saveDraft();
      const next = await runJobPipeline(jobId);
      setJob(next);
      setValues(valuesFromJob(next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pipeline failed");
    } finally {
      setPipelining(false);
    }
  }

  async function onRefreshEmbedding() {
    setPending(true);
    setError(null);
    try {
      await refreshJobEmbedding(jobId);
      setJob(await getJob(jobId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Embedding refresh failed");
    } finally {
      setPending(false);
    }
  }

  const canPublish =
    Boolean(job?.has_job_json) && job?.pipeline?.status !== "validation_failed";

  return (
    <DashboardShell eyebrow="Jobs" title="Edit job">
      <AiProgressScreen
        active={pipelining}
        title="Running job pipeline"
        message="Validating, normalizing, and writing job.json."
      />
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Draft → Validate → Pipeline → Review job.json → Publish. Status: {job?.status ?? "draft"}.
      </p>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Embedding: {job?.embedding_id ? "ready" : "not generated yet"}. job.json:{" "}
        {job?.has_job_json ? "ready" : "run the pipeline first"}.
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {validation ? (
        validation.length === 0 ? (
          <p className="text-sm text-emerald-700">Field checks passed. Run the pipeline before publishing.</p>
        ) : (
          <ul className="list-disc pl-5 text-sm text-red-600">
            {validation.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )
      ) : null}
      <JobForm values={values} onChange={setValues} onSave={onSave} pending={pending || pipelining}>
        <Button type="button" variant="outline" disabled={pending || pipelining} onClick={() => void onValidate()}>
          Validate
        </Button>
        <Link href={`/dashboard/jobs/${jobId}/preview`} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
          Preview
        </Link>
        <Button type="button" variant="outline" disabled={pending || pipelining} onClick={() => void onRefreshEmbedding()}>
          Refresh embedding
        </Button>
        {canPublish ? (
          <AlertDialog>
            <AlertDialogTrigger render={<Button type="button" variant="secondary" disabled={pending || pipelining} />}>
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
        ) : (
          <Button type="button" variant="secondary" disabled>
            Publish after pipeline
          </Button>
        )}
      </JobForm>
      {job?.status === "open" ? (
        <div className="flex flex-wrap gap-2">
          <Link href={`/dashboard/jobs/${jobId}/portal`} className={cn(buttonVariants(), "inline-flex")}>
            Portal Ranking
          </Link>
          <Link href={`/dashboard/jobs/${jobId}/internet`} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
            Internet Talent Search
          </Link>
        </div>
      ) : null}
      <JobPipelinePanel pipeline={job?.pipeline} pending={pending || pipelining} onRun={() => void onRunPipeline()} />
    </DashboardShell>
  );
}
