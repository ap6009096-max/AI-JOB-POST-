"use client";

import { useEffect, useState } from "react";

import { MatchResultCard } from "@/components/brand/match-result-card";
import { ShaderHero } from "@/components/brand/shader-hero";
import { CandidateHeading } from "@/components/candidate/heading";
import { listCandidateRecommendations, type JobRecommendation } from "@/lib/api";

export default function CandidateRecommendationsPage() {
  const [rows, setRows] = useState<JobRecommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCandidateRecommendations()
      .then(setRows)
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <ShaderHero
        shader="spotlight"
        eyebrow="Recommendations"
        title="AI job recommendations"
        subtitle="One standing profile compared to open jobs. There is no apply button — recruiters rank you on the portal."
      />
      <div className="mt-6">
        <CandidateHeading title="Open roles that fit your profile" />
        {loading ? <p className="text-sm text-zinc-500">Loading recommendations…</p> : null}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        {!loading && !error && rows.length === 0 ? (
          <p className="text-sm text-zinc-600">
            No published jobs to compare yet. Finalize your profile so embeddings can match future
            openings.
          </p>
        ) : null}
        <div className="flex flex-col gap-4">
          {rows.map((row) => (
            <MatchResultCard
              key={row.job_id}
              rank={row.rank}
              name={row.title}
              subtitle={row.location || "Location not specified"}
              score={row.score}
              parts={row.parts}
              matched={row.matched_requirements}
              missing={row.missing_requirements}
            />
          ))}
        </div>
      </div>
    </>
  );
}
