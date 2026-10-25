"use client";

import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useState } from "react";

import { EMPTY_JOB_FORM, JobForm, payloadFromValues, valuesFromJob, type JobFormValues } from "@/components/dashboard/job-form";
import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { createJob, generateJob } from "@/lib/api";

const EXAMPLE_PROMPT =
  "Create a Python Developer position in Patna for 0–2 years of experience requiring Python, Django, SQL and basic AWS.";

export default function CreateJobPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"manual" | "ai">("ai");
  const [prompt, setPrompt] = useState("");
  const [values, setValues] = useState<JobFormValues>(EMPTY_JOB_FORM);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [generating, setGenerating] = useState(false);

  async function onGenerate(event: FormEvent) {
    event.preventDefault();
    setGenerating(true);
    setError(null);
    setWarnings([]);
    try {
      const result = await generateJob(prompt.trim());
      setValues(valuesFromJob(result.job));
      setWarnings(result.valid ? [] : result.errors);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Generate failed");
    } finally {
      setGenerating(false);
    }
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const created = await createJob(payloadFromValues(values));
      router.push(`/dashboard/jobs/${created.id}/edit`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  const busy = pending || generating;

  return (
    <DashboardShell eyebrow="Jobs" title="Create Job">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant={mode === "manual" ? "default" : "outline"} onClick={() => setMode("manual")}>
          Manual
        </Button>
        <Button type="button" variant={mode === "ai" ? "default" : "outline"} onClick={() => setMode("ai")}>
          AI prompt
        </Button>
      </div>
      {mode === "ai" ? (
        <form className="flex max-w-2xl flex-col gap-3" onSubmit={onGenerate}>
          <FieldGroup>
            <Field>
              <FieldLabel>Job request</FieldLabel>
              <Textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder={EXAMPLE_PROMPT}
              />
            </Field>
          </FieldGroup>
          <Button type="submit" disabled={busy || prompt.trim().length < 10} className="w-fit">
            {generating ? "Generating…" : "Generate with AI"}
          </Button>
        </form>
      ) : (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Fill the form below, then Save Draft. Publishing happens after validation and the job pipeline.
        </p>
      )}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {warnings.length > 0 ? (
        <ul className="list-disc pl-5 text-sm text-amber-700">
          {warnings.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      <JobForm values={values} onChange={setValues} onSave={onSave} pending={busy} />
    </DashboardShell>
  );
}
