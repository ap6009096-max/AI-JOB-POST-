"use client";

import { useState } from "react";
import Link from "next/link";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { SECTION_HREFS, SECTION_LABELS, type CompletionSection } from "@/lib/candidate/completion";
import { runCandidatePipeline } from "@/lib/api";

function addedSummary(change: { added?: Record<string, string[]> } | undefined): string {
  const added = change?.added ?? {};
  const parts = Object.entries(added).flatMap(([field, values]) =>
    (values ?? []).map((value) => `${field}: ${value}`),
  );
  return parts.length ? parts.join(", ") : "No new items";
}

export default function CandidateIntelligencePage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [running, setRunning] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const missing = (data?.intelligence.missing_sections ?? []).filter(
    (key): key is CompletionSection => key in SECTION_HREFS,
  );
  const pipeline = data?.pipeline;
  const versions = data?.profile_versions ?? [];
  const latest = versions[0];

  async function onRunPipeline() {
    setRunning(true);
    setPipelineError(null);
    try {
      setData(await runCandidatePipeline());
    } catch (caught) {
      setPipelineError(caught instanceof Error ? caught.message : "Could not run the profile pipeline");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <CandidateHeading title="Profile Intelligence">
        Saved profile signals plus an optional AI pipeline that builds a versioned master profile
        JSON. Automatic source updates never overwrite your standing profile.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Master profile versions</CardTitle>
                <CardDescription>
                  {latest
                    ? `Latest version ${latest.version} from ${latest.source || "pipeline"}. Standing profile rows were not overwritten.`
                    : "No master JSON yet. Analyze professional links or run the pipeline."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                {latest ? <p>Last change: {addedSummary(latest.change_summary)}</p> : null}
                {versions.slice(0, 8).map((row) => (
                  <p key={row.id} className="text-zinc-600 dark:text-zinc-300">
                    v{row.version} · {row.source || "pipeline"} · {addedSummary(row.change_summary)}
                  </p>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Profile pipeline</CardTitle>
                <CardDescription>
                  {pipeline?.status
                    ? `Last run: ${pipeline.status.replaceAll("_", " ")}`
                    : "Not run yet. Uses your resume and professional links."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {pipeline?.current_node ? (
                  <p className="text-sm">Current node: {pipeline.current_node}</p>
                ) : null}
                {pipeline?.skipped.length ? (
                  <ul className="list-disc pl-5 text-sm text-zinc-600 dark:text-zinc-300">
                    {pipeline.skipped.map((item) => (
                      <li key={`${item.node}-${item.reason}`}>
                        {item.node}: {item.reason.replaceAll("_", " ")}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {pipelineError ? <p className="text-sm text-red-600">{pipelineError}</p> : null}
                <Button type="button" onClick={onRunPipeline} disabled={running}>
                  {running ? "Running…" : "Run profile pipeline"}
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Master candidate JSON</CardTitle>
                <CardDescription>
                  {data.profile_ready
                    ? "Profile is ready for job comparisons."
                    : "Finalize your profile to generate embeddings and master JSON."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <p>Pipeline: {pipeline?.status?.replaceAll("_", " ") || "not run"}</p>
                <p>Embedding: {data.embedding_id ? "generated" : "missing"}</p>
                {data.master_candidate ? (
                  <pre className="max-h-80 overflow-auto rounded-xl bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
                    {JSON.stringify(data.master_candidate, null, 2)}
                  </pre>
                ) : (
                  <p className="text-zinc-500">No master JSON yet.</p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Missing sections</CardTitle>
                <CardDescription>
                  {missing.length === 0 ? "No missing sections." : "Open a section to fill the gap."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {missing.map((key) => (
                  <Link
                    key={key}
                    href={SECTION_HREFS[key]}
                    className="rounded-lg border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                  >
                    {SECTION_LABELS[key]}
                  </Link>
                ))}
              </CardContent>
            </Card>
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
