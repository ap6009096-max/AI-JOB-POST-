"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { DashboardShell } from "@/components/dashboard/shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getExternalCandidate, getJob, getPortalCandidate } from "@/lib/api";
import type { Candidate, Job } from "@/lib/types";

export function CandidateDetails({
  jobId,
  candidateId,
  track,
}: {
  jobId: string;
  candidateId: string;
  track: "portal" | "internet";
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load =
      track === "portal" ? getPortalCandidate(candidateId) : getExternalCandidate(candidateId);
    Promise.all([getJob(jobId), load])
      .then(([nextJob, nextCandidate]) => {
        setJob(nextJob);
        setCandidate(nextCandidate);
      })
      .catch((caught: Error) => setError(caught.message));
  }, [candidateId, jobId, track]);

  const profile = candidate?.profile;

  return (
    <DashboardShell
      eyebrow={track === "portal" ? "Portal details" : "Source details"}
      title={profile?.name ?? "Candidate"}
    >
      <p className="text-sm text-zinc-500">
        Compared against{" "}
        <Link className="underline" href={`/dashboard/jobs/${jobId}/${track}`}>
          {job?.title ?? "job"}
        </Link>
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {profile ? (
        <Card>
          <CardHeader>
            <CardTitle>{profile.title}</CardTitle>
            <CardDescription>
              {profile.location}
              {profile.source ? ` · ${profile.source}` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {profile.identity_status === "unverified_reddit_handle" ? (
              <Alert>
                <AlertTitle>Unverified Reddit handle</AlertTitle>
                <AlertDescription>
                  This is a public Reddit username, not a verified candidate. Do not treat{" "}
                  {profile.name} as a confirmed person or portal identity.
                </AlertDescription>
              </Alert>
            ) : null}
            {profile.url ? (
              <a className="text-sm underline" href={profile.url} target="_blank" rel="noreferrer">
                {profile.url}
              </a>
            ) : null}
            <p className="text-sm leading-7 text-zinc-600 dark:text-zinc-300">{profile.resume_summary}</p>
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((skill) => (
                <Badge key={skill} variant="secondary">
                  {skill}
                </Badge>
              ))}
              <Badge variant="outline">{profile.experience_years} years</Badge>
            </div>
            <pre className="overflow-x-auto rounded-xl bg-zinc-50 p-4 text-xs dark:bg-zinc-900">
              {JSON.stringify(profile, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}
    </DashboardShell>
  );
}
