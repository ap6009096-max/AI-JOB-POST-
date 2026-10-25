"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AiProgressScreen } from "@/components/brand/ai-progress-screen";
import { MatchResultCard } from "@/components/brand/match-result-card";
import { ShaderHero } from "@/components/brand/shader-hero";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getJob, getLatestInternetRank, rankInternet } from "@/lib/api";
import { RANK_VIEW_LIMITS, sliceStoredRanking, type RankViewLimit } from "@/lib/dashboard/ranking";
import type { Job, RankedCandidate, RankingRun, SourceSkip } from "@/lib/types";
import { cn } from "@/lib/utils";
const SECTIONS = [
  { key: "GitHub", title: "GitHub Results" },
  { key: "LinkedIn", title: "LinkedIn Results" },
  { key: "Portfolio", title: "Portfolio Results" },
  { key: "Website", title: "Website Results" },
  { key: "Reddit", title: "Reddit Results" },
  { key: "Other", title: "Other Authorized Source Results" },
] as const;
const NAMED_SOURCES = new Set(["GitHub", "LinkedIn", "Portfolio", "Website", "Reddit"]);

function skipCopy(item: SourceSkip): string {
  if (item.source === "LinkedIn") {
    return "LinkedIn skipped: authorized API required (URL stored only).";
  }
  return `${item.source} skipped: ${item.reason.replaceAll("_", " ")}.`;
}

function sectionKey(source: string | null | undefined): (typeof SECTIONS)[number]["key"] {
  const name = (source || "").trim();
  if (NAMED_SOURCES.has(name)) {
    return name as (typeof SECTIONS)[number]["key"];
  }
  return "Other";
}

function groupBySource(rows: RankedCandidate[]): Record<(typeof SECTIONS)[number]["key"], RankedCandidate[]> {
  const grouped: Record<(typeof SECTIONS)[number]["key"], RankedCandidate[]> = {
    GitHub: [],
    LinkedIn: [],
    Portfolio: [],
    Website: [],
    Reddit: [],
    Other: [],
  };
  for (const row of rows) {
    grouped[sectionKey(row.source)].push(row);
  }
  return grouped;
}

export function InternetTalentDashboard({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [run, setRun] = useState<RankingRun | null>(null);
  const [viewLimit, setViewLimit] = useState<RankViewLimit>(10);
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
      getLatestInternetRank(jobId)
        .then((nextRun) => {
          if (!cancelled) {
            setRun(nextRun);
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

  async function onSearch() {
    setPending(true);
    setError(null);
    try {
      setRun(await rankInternet(jobId, 100));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Internet search failed");
    } finally {
      setPending(false);
    }
  }

  const storedCount = run?.results.length ?? 0;
  const visible = useMemo(() => sliceStoredRanking(run?.results, viewLimit), [run, viewLimit]);
  const grouped = useMemo(() => groupBySource(visible), [visible]);
  const canSearch = Boolean(job && (job.status === "open" || job.has_job_json));
  const detailsBase = `/dashboard/jobs/${jobId}/internet`;
  const skipped = run?.skipped ?? [];

  return (
    <div className="flex flex-col gap-6">
      <AiProgressScreen
        active={pending}
        title="Searching internet talent"
        message="Collecting permitted sources, then scoring with the same engine as portal ranking."
      />
      <ShaderHero
        shader="spotlight"
        eyebrow="Internet talent search"
        title={job?.title ?? "Internet Talent Search"}
        subtitle="External sources only. This track does not mix with portal ranking."
      />
      {error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : null}
      {skipped.length > 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Skipped sources</p>
          <ul className="mt-1 list-disc pl-5">
            {skipped.map((item) => (
              <li key={`${item.source}-${item.reason}`}>{skipCopy(item)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        {canSearch ? (
          <Button type="button" onClick={() => void onSearch()} disabled={pending || !job}>
            Search all sources
          </Button>
        ) : null}
        {RANK_VIEW_LIMITS.map((value) => (
          <Button
            key={value}
            type="button"
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
      </div>
      {ready && !run ? (
        <Card>
          {canSearch ? (
            <>
              <CardHeader>
                <CardTitle>No internet search yet</CardTitle>
                <CardDescription>
                  Search all sources saves up to 100 ranked profiles. TOP 10 / 20 / 100 only change how many of that stored
                  list you see.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button type="button" onClick={() => void onSearch()} disabled={pending || !job}>
                  Search all sources
                </Button>
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader>
                <CardTitle>Job not ready to search</CardTitle>
                <CardDescription>
                  Run the job pipeline first so this job has job.json. Then you can search all sources without publishing.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link
                  href={`/dashboard/jobs/${jobId}/preview`}
                  className={cn(buttonVariants(), "inline-flex")}
                >
                  Open job preview
                </Link>
              </CardContent>
            </>
          )}
        </Card>
      ) : null}
      {run
        ? SECTIONS.map((section) => (
            <SourceSection
              key={section.key}
              title={section.title}
              rows={grouped[section.key]}
              skipped={skipped.filter((item) => item.source === section.key)}
              detailsBase={detailsBase}
              emptyHint={
                section.key === "LinkedIn"
                  ? "LinkedIn is not scraped. Authorized API required."
                  : `No ${section.title.toLowerCase()} in this stored Top ${viewLimit}.`
              }
            />
          ))
        : null}
    </div>
  );
}

function SourceSection({
  title,
  rows,
  skipped,
  detailsBase,
  emptyHint,
}: {
  title: string;
  rows: RankedCandidate[];
  skipped: SourceSkip[];
  detailsBase: string;
  emptyHint: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          <Badge variant="outline">Internet</Badge>
          {skipped.length > 0 ? ` · ${skipped.map(skipCopy).join(" ")}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {rows.length === 0 ? (
          <p className="text-sm text-zinc-600">{emptyHint}</p>
        ) : (
          rows.map((row) => (
            <MatchResultCard
              key={row.candidate_id}
              rank={row.rank}
              name={row.name}
              subtitle={row.title}
              score={row.score}
              parts={row.parts}
              matched={row.matched_requirements}
              missing={row.missing_requirements}
              detailsHref={`${detailsBase}/${row.candidate_id}`}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
