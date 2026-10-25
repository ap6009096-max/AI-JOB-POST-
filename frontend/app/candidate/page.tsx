"use client";

import Link from "next/link";
import { useState } from "react";

import { AiProgressScreen } from "@/components/brand/ai-progress-screen";
import { ShaderHero } from "@/components/brand/shader-hero";
import { StatBento } from "@/components/brand/stat-bento";
import { GraphGate } from "@/components/candidate/heading";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { appConfig } from "@/lib/config";
import { finalizeCandidateProfile } from "@/lib/api";
import { nextIncompleteStep } from "@/lib/candidate/nav";
import { isResumeParsePendingReview } from "@/lib/candidate/resume-parse-draft";
import { cn } from "@/lib/utils";

export default function CandidateDashboardPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [finalizing, setFinalizing] = useState(false);
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  async function onAnalyze() {
    setFinalizing(true);
    setFinalizeError(null);
    try {
      setData(await finalizeCandidateProfile());
    } catch (caught) {
      setFinalizeError(caught instanceof Error ? caught.message : "Could not analyze profile");
    } finally {
      setFinalizing(false);
    }
  }

  return (
    <>
      <AiProgressScreen
        active={finalizing}
        title="Analyzing profile"
        message="LangGraph is merging sources, validating, and generating your master candidate JSON."
      />
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-6">
            <ShaderHero
              shader="dots"
              eyebrow={appConfig.name}
              title="AI Profile Intelligence"
              subtitle="Your professional profile, automatically analyzed."
              completion={data.completion.percent}
              actions={
                <>
                  <Link href="/candidate/resume" className={cn(buttonVariants(), "inline-flex")}>
                    Upload Resume
                  </Link>
                  <button
                    type="button"
                    onClick={() => void onAnalyze()}
                    className={cn(buttonVariants({ variant: "outline" }), "border-white/30 bg-white/10 text-white hover:bg-white/20")}
                  >
                    Analyze Profile
                  </button>
                </>
              }
            />
            {finalizeError ? <p className="text-sm text-red-600">{finalizeError}</p> : null}
            {isResumeParsePendingReview(data.resume) ? (
              <Card>
                <CardHeader>
                  <CardTitle>Review extracted resume</CardTitle>
                  <CardDescription>
                    AI filled a draft from your upload. Edit and approve it before it becomes your
                    profile.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href="/candidate/resume" className={cn(buttonVariants(), "inline-flex")}>
                    Review extracted resume
                  </Link>
                </CardContent>
              </Card>
            ) : null}
            <StatBento
              items={[
                { label: "Experience", value: data.experience.length },
                { label: "Skills", value: data.skills.length },
                { label: "Projects", value: data.projects.length },
              ]}
            />
            <Card>
              <CardHeader>
                <CardTitle>Next step</CardTitle>
                <CardDescription>{data.intelligence.next_action}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Link href={nextIncompleteStep(data)} className={cn(buttonVariants(), "inline-flex")}>
                  Continue profile
                </Link>
                {data.profile_ready ? (
                  <Link href="/candidate/recommendations" className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                    View recommended jobs
                  </Link>
                ) : (
                  <Link href="/candidate/review" className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                    Review profile
                  </Link>
                )}
              </CardContent>
            </Card>
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
