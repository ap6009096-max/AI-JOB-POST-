"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Candidate, Job, RankingRun } from "@/lib/types";

const LIMITS = [10, 20, 100] as const;

type Props = {
  jobId: string;
  track: "portal" | "internet";
  loadCandidates: () => Promise<Candidate[]>;
  loadJob: () => Promise<Job>;
  runRanking: (limit: number) => Promise<RankingRun>;
};

export function RankTrack({ jobId, track, loadCandidates, loadJob, runRanking }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [limit, setLimit] = useState<(typeof LIMITS)[number]>(10);
  const [run, setRun] = useState<RankingRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    Promise.all([loadJob(), loadCandidates()])
      .then(([nextJob, nextCandidates]) => {
        setJob(nextJob);
        setCandidates(nextCandidates);
      })
      .catch((caught: Error) => setError(caught.message));
  }, [loadCandidates, loadJob]);

  async function onRank() {
    setPending(true);
    setError(null);
    try {
      setRun(await runRanking(limit));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ranking failed");
    } finally {
      setPending(false);
    }
  }

  const detailsBase = `/dashboard/jobs/${jobId}/${track}`;
  const poolLabel = track === "portal" ? "Registered users" : "External sources";
  const jsonLabel = track === "portal" ? "Portal JSON" : "Source JSON";
  const engineLabel = track === "portal" ? "Ranking engine" : "AI ranking";
  const published = job?.status === "open";
  const comparisonCopy =
    "Skills 34%, experience 22%, projects 13%, technology 12%, semantic 11%, education 8%. Location and salary stored separately.";

  return (
    <div className="flex flex-col gap-6">
      {error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}. Start the API with `uvicorn app.main:app --reload --port 8000`.
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{job?.title ?? "Loading job"}</CardTitle>
          <CardDescription>{job?.description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {job?.requirements.skills.map((skill) => (
            <Badge key={skill} variant="secondary">
              {skill}
            </Badge>
          ))}
          {job ? (
            <Badge variant="outline">
              {job.requirements.experience_years}+ years · {job.requirements.location}
            </Badge>
          ) : null}
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{poolLabel}</CardTitle>
            <CardDescription>{candidates.length} profiles in {jsonLabel}</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Job comparison</CardTitle>
            <CardDescription>{comparisonCopy}</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{engineLabel}</CardTitle>
            <CardDescription>Top 10 / 20 / 100 against this job</CardDescription>
          </CardHeader>
        </Card>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        {LIMITS.map((value) => (
          <Button
            key={value}
            variant={limit === value ? "default" : "outline"}
            onClick={() => setLimit(value)}
          >
            Top {value}
          </Button>
        ))}
        <Button onClick={onRank} disabled={pending || !job || !published}>
          {pending ? "Ranking…" : `Run ${engineLabel.toLowerCase()}`}
        </Button>
        {job && !published ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">Publish the job first</p>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{poolLabel}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Location</TableHead>
                {track === "internet" ? <TableHead>Source</TableHead> : null}
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.map((candidate) => (
                <TableRow key={candidate.id}>
                  <TableCell>{candidate.profile.name}</TableCell>
                  <TableCell>{candidate.profile.title}</TableCell>
                  <TableCell>{candidate.profile.location}</TableCell>
                  {track === "internet" ? (
                    <TableCell>{candidate.profile.source}</TableCell>
                  ) : null}
                  <TableCell>
                    <Link className="text-sm font-medium underline" href={`${detailsBase}/${candidate.id}`}>
                      Details
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>
              Ranked results · Top {run.limit}
            </CardTitle>
            <CardDescription>Run {run.id}</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Why</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {run.results.map((row) => (
                  <TableRow key={row.candidate_id}>
                    <TableCell>{row.rank}</TableCell>
                    <TableCell>{row.name}</TableCell>
                    <TableCell>{Math.round(row.score * 100)}</TableCell>
                    <TableCell className="max-w-md whitespace-normal text-zinc-500">
                      {row.narrative?.recommendation || row.reasons[0]}
                    </TableCell>
                    <TableCell>
                      <Link
                        className="text-sm font-medium underline"
                        href={`${detailsBase}/${row.candidate_id}`}
                      >
                        {track === "portal" ? "Portal details" : "Source details"}
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
