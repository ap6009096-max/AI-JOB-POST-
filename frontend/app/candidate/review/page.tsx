"use client";

import { useState } from "react";

import { AiProgressScreen } from "@/components/brand/ai-progress-screen";
import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { ReviewPanel } from "@/components/candidate/review-panel";
import { Button } from "@/components/ui/button";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { finalizeCandidateProfile } from "@/lib/api";

export default function CandidateReviewPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function onFinalize() {
    setPending(true);
    setFormError(null);
    try {
      setData(await finalizeCandidateProfile());
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not finalize profile");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <AiProgressScreen
        active={pending}
        title="Saving master candidate JSON"
        message="Analyzing sources, running LangGraph, and generating embeddings."
      />
      <CandidateHeading title="Review">
        Confirm your standing profile, then finalize to build master JSON and embeddings. Candidates
        never apply to jobs from here.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-4">
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            <Button type="button" onClick={() => void onFinalize()} disabled={pending} className="w-fit">
              Finalize profile
            </Button>
            <ReviewPanel graph={data} />
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
