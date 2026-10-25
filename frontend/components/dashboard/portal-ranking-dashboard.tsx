"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AiProgressScreen } from "@/components/brand/ai-progress-screen";
import { MatchResultCard } from "@/components/brand/match-result-card";
import { ShaderHero } from "@/components/brand/shader-hero";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getJob, getLatestPortalRank, rankPortal } from "@/lib/api";
import { RANK_VIEW_LIMITS, sliceStoredRanking, type RankViewLimit } from "@/lib/dashboard/ranking";
import type { Job, RankedCandidate, RankingRun } from "@/lib/types";
import { cn } from "@/lib/utils";

function listText(items: string[] | undefined, empty: string): string {
  return items && items.length > 0 ? items.join(", ") : empty;
}

export function PortalRankingDashboard({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [run, setRun] = useState<RankingRun | null>(null);
  const [viewLimit, setViewLimit] = useState<RankViewLimit>(10);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    void Promise.all([
      getJob(jobId)
        .then((nextJob) => {
          if (!cancelled) {
            setJob(nextJob);
          }
        })
        .catch((caught: Error) => {
          if (!cancelled) {
            setError(caught.message);
          }
        }),
      getLatestPortalRank(jobId)
        .then((nextRun) => {
          if (!cancelled) {
            setRun(nextRun);
            setSelectedId(nextRun?.results[0]?.candidate_id ?? null);
          }
        })
        .catch((caught: Error) => {
          if (!cancelled) {
            setError(caught.message);
          }
        }),
    ]).finally(() => {
      if (!cancelled) {
        setReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  async function onRank() {
    setPending(true);
    setError(null);
    try {
      const nextRun = await rankPortal(jobId, 100);
      setRun(nextRun);
      setSelectedId(nextRun.results[0]?.candidate_id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ranking failed");
    } finally {
      setPending(false);
    }
  }

  const visible = useMemo(() => sliceStoredRanking(run?.results, viewLimit), [run, viewLimit]);
  const selected = visible.find((row) => row.candidate_id === selectedId) ?? visible[0] ?? null;
  const published = job?.status === "open";
  const detailsBase = `/dashboard/jobs/${jobId}/portal`;
  const storedCount = run?.results.length ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <AiProgressScreen
        active={pending}
        title="Ranking portal candidates"
        message="Scoring registered profiles against this job. Gemini explains; the backend calculates."
      />
      <ShaderHero
        shader="dots"
        subtle
        eyebrow="Portal ranking"
        title={job?.title ?? "Portal Ranking"}
        subtitle="Registered ai-job-post candidates only. Internet search is a separate track."
      />
      {error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void onRank()} disabled={pending || !job || !published}>
          Rank candidates
        </Button>
        {RANK_VIEW_LIMITS.map((value) => (
          <Button
            key={value}
            variant={viewLimit === value ? "default" : "outline"}
            disabled={!run}
            onClick={() => setViewLimit(value)}
          >
            TOP {value}
          </Button>
        ))}
        {run ? (
          <p className="text-sm text-zinc-600">
            Showing Top {Math.min(viewLimit, storedCount)} of {storedCount} stored
          </p>
        ) : null}
        {job && !published ? (
          <Link href={`/dashboard/jobs/${jobId}/preview`} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
            Publish the job first
          </Link>
        ) : null}
      </div>
      {ready && !run ? (
        <Card>
          <CardHeader>
            <CardTitle>No stored ranking yet</CardTitle>
            <CardDescription>
              Rank candidates once to save up to 100 matches. TOP 10 / 20 / 100 only change how many of that stored list
              you see.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => void onRank()} disabled={pending || !job || !published}>
              Rank candidates
            </Button>
          </CardContent>
        </Card>
      ) : null}
      {run ? (
        <div className="flex flex-col gap-4">
          {visible.map((row) => (
            <button key={row.candidate_id} type="button" className="text-left" onClick={() => setSelectedId(row.candidate_id)}>
              <MatchResultCard
                rank={row.rank}
                name={row.name}
                subtitle={row.title}
                score={row.score}
                parts={row.parts}
                matched={row.matched_requirements}
                missing={row.missing_requirements}
                profileHref={`${detailsBase}/${row.candidate_id}`}
                detailsHref={`${detailsBase}/${row.candidate_id}`}
              />
            </button>
          ))}
          {selected ? <NarrativePanel row={selected} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function NarrativePanel({ row }: { row: RankedCandidate }) {
  const narrative = row.narrative;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{row.name}</CardTitle>
        <CardDescription>
          <Badge variant="outline">Registered portal</Badge>
          {narrative?.recommendation ? ` · ${narrative.recommendation}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <section>
          <h3 className="text-sm font-medium">Strengths</h3>
          <p className="mt-1 text-sm text-zinc-600">{listText(narrative?.strengths, "No strengths stored.")}</p>
        </section>
        <section>
          <h3 className="text-sm font-medium">Weaknesses</h3>
          <p className="mt-1 text-sm text-zinc-600">{listText(narrative?.weaknesses, "No weaknesses stored.")}</p>
        </section>
        <section>
          <h3 className="text-sm font-medium">Evidence</h3>
          <p className="mt-1 text-sm text-zinc-600">{narrative?.evidence || "No evidence stored."}</p>
        </section>
        <section>
          <h3 className="text-sm font-medium">AI explanation</h3>
          <p className="mt-1 text-sm text-zinc-600">{narrative?.explanation || "No explanation stored."}</p>
        </section>
      </CardContent>
    </Card>
  );
}
