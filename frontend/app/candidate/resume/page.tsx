"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { ResumeParseReview } from "@/components/candidate/resume-parse-review";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { isResumeParsePendingReview } from "@/lib/candidate/resume-parse-draft";
import { applyCandidateResumeParse, putCandidateResume, uploadCandidateResume } from "@/lib/api";
import type { CandidateResumeParseResult } from "@/lib/types";

const MAX_BYTES = 5 * 1024 * 1024;
const ACTIVE = new Set(["queued", "processing"]);

export default function CandidateResumePage() {
  const { data, error, loading, reload, setData } = useCandidateGraph();
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [applying, setApplying] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setText(data.resume.text);
    setUrl(data.resume.url);
  }, [data]);

  const status = data?.resume.processing.status ?? "";

  useEffect(() => {
    if (!ACTIVE.has(status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void reload();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [reload, status]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(await putCandidateResume({ text, url }));
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  async function onUpload(file: File | undefined) {
    if (!file) {
      return;
    }
    setFileError(null);
    if (file.size > MAX_BYTES) {
      setFileError("Resume must be 5 MB or smaller");
      return;
    }
    setPending(true);
    try {
      setData(await uploadCandidateResume(file));
    } catch (caught) {
      setFileError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setPending(false);
    }
  }

  async function onApprove(draft: CandidateResumeParseResult) {
    setApplying(true);
    setFormError(null);
    try {
      setData(await applyCandidateResumeParse(draft));
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not save extracted fields");
    } finally {
      setApplying(false);
    }
  }

  const parseResult = data?.resume.parse_result;
  const processing = data?.resume.processing;
  const pendingReview = data ? isResumeParsePendingReview(data.resume) : false;
  const appliedAt = processing?.applied_at ?? "";
  const parseKey = [
    processing?.started_at ?? "",
    data?.resume.filename ?? "",
    processing?.finished_at ?? "",
  ].join(":");

  return (
    <>
      <CandidateHeading title="Resume">
        Upload a PDF, Word, PNG, or JPG file (5 MB max). Processing runs on the server; you can also paste text.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-8">
            <Field>
              <FieldLabel>Resume file</FieldLabel>
              <Input
                type="file"
                accept=".pdf,.docx,.png,.jpg,.jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg"
                disabled={pending || ACTIVE.has(status)}
                onChange={(event) => void onUpload(event.target.files?.[0])}
              />
            </Field>
            {fileError ? <p className="text-sm text-red-600">{fileError}</p> : null}
            {data.resume.filename ? (
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {data.resume.filename}
                {data.resume.size_bytes ? ` · ${Math.ceil(data.resume.size_bytes / 1024)} KB` : ""}
              </p>
            ) : null}
            {processing?.status ? (
              <p className="text-sm">
                Status: {processing.status}
                {processing.error ? ` — ${processing.error}` : ""}
              </p>
            ) : null}
            {pendingReview && parseResult ? (
              <ResumeParseReview
                parseResult={parseResult}
                parseKey={parseKey}
                pending={applying}
                error={formError}
                onApprove={onApprove}
              />
            ) : null}
            {appliedAt && parseResult ? (
              <div className="rounded-xl border border-zinc-200 p-4 text-sm dark:border-zinc-800">
                <p className="font-medium">Extracted profile saved</p>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                  Approved fields are on your standing profile. You can keep editing them from each
                  section.
                </p>
                <Link
                  href="/candidate/review"
                  className="mt-3 inline-flex h-9 items-center justify-center rounded-4xl bg-primary px-3 text-sm font-medium text-primary-foreground"
                >
                  Review profile
                </Link>
              </div>
            ) : null}

            <SectionForm onSave={onSave} pending={pending}>
              {formError && !pendingReview ? <p className="text-sm text-red-600">{formError}</p> : null}
              <FieldGroup>
                <Field>
                  <FieldLabel>Resume text</FieldLabel>
                  <Textarea value={text} onChange={(event) => setText(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>Resume URL</FieldLabel>
                  <Input value={url} onChange={(event) => setUrl(event.target.value)} />
                </Field>
              </FieldGroup>
            </SectionForm>
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
