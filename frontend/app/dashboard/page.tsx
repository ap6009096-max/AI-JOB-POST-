"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DiscoveryCard } from "@/components/brand/discovery-card";
import { ShaderHero } from "@/components/brand/shader-hero";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCompanyProfile, getMe, listJobs, listMatchingRuns, type MeResponse } from "@/lib/api";
import { appConfig } from "@/lib/config";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CompanyProfile, Job, MatchingRunSummary } from "@/lib/types";

const PROFILE_FIELDS: (keyof CompanyProfile)[] = [
  "name",
  "industry",
  "business_domain",
  "description",
  "location",
  "company_size",
  "departments",
  "hiring_domains",
  "technologies",
];

function profileCompleteness(profile: CompanyProfile | null): number {
  if (!profile) {
    return 0;
  }
  const filled = PROFILE_FIELDS.filter((key) => {
    const value = profile[key];
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return Boolean(typeof value === "string" ? value.trim() : value);
  }).length;
  return Math.round((filled / PROFILE_FIELDS.length) * 100);
}

export default function DashboardPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<MatchingRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then(async (nextMe) => {
        setMe(nextMe);
        if (nextMe.role === "recruiter" && nextMe.memberships.length === 0) {
          return;
        }
        const [nextProfile, nextJobs, nextRuns] = await Promise.all([
          getCompanyProfile(),
          listJobs(),
          listMatchingRuns(),
        ]);
        setProfile(nextProfile);
        setJobs(nextJobs);
        setRuns(nextRuns);
      })
      .catch((caught: Error) => setError(caught.message));
  }, []);

  const awaitingCompany = me?.role === "recruiter" && (me.memberships.length ?? 0) === 0;
  const completeness = profileCompleteness(profile);

  return (
    <div className="flex flex-col gap-6">
      <ShaderHero
        shader="spotlight"
        eyebrow={appConfig.name}
        title="Talent Intelligence"
        subtitle="Find the strongest candidates for your jobs."
      />
      {awaitingCompany ? (
        <Card>
          <CardHeader>
            <CardTitle>Awaiting company access</CardTitle>
            <CardDescription>
              A company admin must invite this recruiter before jobs and ranking APIs will work.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <>
          {error ? (
            <p className="text-sm text-red-600">
              {error}. Start the backend on port 8000, then refresh.
            </p>
          ) : null}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Company profile</CardTitle>
                <CardDescription>{completeness}% complete</CardDescription>
              </CardHeader>
              <CardContent>
                <Link href="/dashboard/company" className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                  Edit profile
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Jobs</CardTitle>
                <CardDescription>
                  {jobs.length} posting{jobs.length === 1 ? "" : "s"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Link href="/dashboard/jobs" className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                  View jobs
                </Link>
                <Link href="/dashboard/jobs/new" className={cn(buttonVariants(), "inline-flex")}>
                  Create job
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Matching runs</CardTitle>
                <CardDescription>
                  {runs.length} recent run{runs.length === 1 ? "" : "s"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href="/dashboard/runs" className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
                  View runs
                </Link>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <DiscoveryCard
              title="Portal Ranking"
              description="Registered candidates. Rank against a published job."
              href="/dashboard/ranking/portal"
              action="Rank candidates"
            />
            <DiscoveryCard
              title="Internet Talent Search"
              description="External sources. Separate from portal ranking."
              href="/dashboard/ranking/internet"
              action="Search all sources"
            />
          </div>
        </>
      )}
    </div>
  );
}
