"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getExternalCandidate, getInternetMatchDetails, getJob } from "@/lib/api";
import type { Candidate, Job, MatchResult } from "@/lib/types";

const SOURCE_LABEL = "SOURCE: INTERNET";

function percent(value: number | undefined): string {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function listText(items: string[] | undefined, empty: string): string {
  return items && items.length > 0 ? items.join(", ") : empty;
}

export function InternetCandidateDetails({ jobId, candidateId }: { jobId: string; candidateId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJob(jobId), getExternalCandidate(candidateId), getInternetMatchDetails(jobId, candidateId)])
      .then(([nextJob, nextCandidate, nextMatch]) => {
        setJob(nextJob);
        setCandidate(nextCandidate);
        setMatch(nextMatch);
      })
      .catch((caught: Error) => setError(caught.message));
  }, [candidateId, jobId]);

  const profile = candidate?.profile;

  return (
    <DashboardShell eyebrow="Internet Candidate Details" title={profile?.name ?? "Candidate"}>
      <p className="text-sm text-zinc-500">
        Compared against{" "}
        <Link className="underline" href={`/dashboard/jobs/${jobId}/internet`}>
          {job?.title ?? "job"}
        </Link>
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{SOURCE_LABEL}</Badge>
        {match?.source || profile?.source ? (
          <Badge variant="secondary">{match?.source || profile?.source}</Badge>
        ) : null}
      </div>
      {profile?.identity_status === "unverified_reddit_handle" ? (
        <Alert>
          <AlertTitle>Unverified Reddit handle</AlertTitle>
          <AlertDescription>
            This is a public Reddit username, not a verified candidate. Do not treat {profile.name} as a
            confirmed person or portal identity.
          </AlertDescription>
        </Alert>
      ) : null}
      {profile ? (
        <Card>
          <CardHeader>
            <CardTitle>{profile.title}</CardTitle>
            <CardDescription>
              {profile.location} · {SOURCE_LABEL}
              {profile.source ? ` · ${profile.source}` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {profile.url ? (
              <a className="text-sm underline" href={profile.url} target="_blank" rel="noreferrer">
                {profile.url}
              </a>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((skill) => (
                <Badge key={skill} variant="secondary">
                  {skill}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
      {!match ? (
        <Card>
          <CardHeader>
            <CardTitle>No match result yet</CardTitle>
            <CardDescription>SEARCH ALL SOURCES first to persist match_result.json for this internet candidate.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <MatchDocument match={match} />
      )}
    </DashboardShell>
  );
}

function MatchDocument({ match }: { match: MatchResult }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Match scores</CardTitle>
          <CardDescription>
            {SOURCE_LABEL} · {match.source}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm md:grid-cols-2">
          <p>Overall Match {percent(match.overall_match_score)}</p>
          <p>Skills {percent(match.skill_match_score)}</p>
          <p>Experience {percent(match.experience_match_score)}</p>
          <p>Projects {percent(match.project_match_score)}</p>
          <p>Education {percent(match.education_match_score)}</p>
          <p>Technology {percent(match.technology_match_score)}</p>
          <p>Semantic Match {percent(match.semantic_match_score)}</p>
          <p>Location {percent(match.location_match_score)}</p>
          <p>Salary {percent(match.salary_match_score)}</p>
          <p>Confidence {percent(match.confidence_score)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Explanation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <section>
            <h3 className="text-sm font-medium">Matched Requirements</h3>
            <p className="mt-1 text-sm text-zinc-600">{listText(match.matched_requirements, "None")}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Missing Requirements</h3>
            <p className="mt-1 text-sm text-zinc-600">{listText(match.missing_requirements, "None")}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Strengths</h3>
            <p className="mt-1 text-sm text-zinc-600">{listText(match.strengths, "None")}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Weaknesses</h3>
            <p className="mt-1 text-sm text-zinc-600">{listText(match.weaknesses, "None")}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Evidence</h3>
            <p className="mt-1 text-sm text-zinc-600">{match.evidence || "None"}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Match reasoning</h3>
            <p className="mt-1 text-sm text-zinc-600">{match.match_reasoning || "None"}</p>
          </section>
          <section>
            <h3 className="text-sm font-medium">Recommendation</h3>
            <p className="mt-1 text-sm text-zinc-600">{match.recommendation || "None"}</p>
          </section>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>match_result.json</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-xl bg-zinc-50 p-4 text-xs dark:bg-zinc-900">
            {JSON.stringify(match, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </>
  );
}
