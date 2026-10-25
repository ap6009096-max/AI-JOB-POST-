"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { analyzeCandidateSources, putCandidateProfessionalLinks } from "@/lib/api";
import type { CandidateLinkItem } from "@/lib/types";

type OtherLinkDraft = { id?: string; source: string; url: string };

function evidenceSummary(link: CandidateLinkItem): string {
  const analysis = link.analysis;
  if (!analysis) {
    return "Not analyzed yet.";
  }
  if (analysis.fetch_status !== "ok") {
    return analysis.skip_reason || analysis.fetch_status || "Skipped";
  }
  const evidence = analysis.evidence;
  const languages = Array.isArray(evidence.languages) ? evidence.languages.filter((item) => typeof item === "string") : [];
  const repos = Array.isArray(evidence.repositories) ? evidence.repositories : [];
  const summary = typeof analysis.analysis.summary === "string" ? analysis.analysis.summary : "";
  const parts = [
    analysis.provenance,
    languages.length ? `languages: ${languages.slice(0, 6).join(", ")}` : "",
    repos.length ? `${repos.length} repositories` : "",
    summary,
  ].filter(Boolean);
  return parts.join(" · ") || "Evidence saved.";
}

export default function CandidateLinksPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [linkedin, setLinkedin] = useState("");
  const [github, setGithub] = useState("");
  const [portfolio, setPortfolio] = useState("");
  const [website, setWebsite] = useState("");
  const [otherLinks, setOtherLinks] = useState<OtherLinkDraft[]>([]);
  const [pending, setPending] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setLinkedin(data.professional_links.linkedin);
    setGithub(data.professional_links.github);
    setPortfolio(data.professional_links.portfolio);
    setWebsite(data.professional_links.website);
    setOtherLinks(
      data.professional_links.other.map((item) => ({
        id: item.id,
        source: item.source,
        url: item.url ?? "",
      })),
    );
  }, [data]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(
        await putCandidateProfessionalLinks({
          linkedin,
          github,
          portfolio,
          website,
          other: otherLinks
            .filter((item) => item.source.trim() || item.url.trim())
            .map((item) => ({
              id: item.id,
              source: item.source.trim() || "other",
              url: item.url.trim() || null,
            })),
        }),
      );
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  async function onAnalyze() {
    setAnalyzing(true);
    setFormError(null);
    try {
      setData(await analyzeCandidateSources());
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not analyze sources");
    } finally {
      setAnalyzing(false);
    }
  }

  const savedLinks = data?.links ?? [];
  const hasSavedUrls = savedLinks.some((item) => Boolean(item.url));

  return (
    <>
      <CandidateHeading title="Professional Links">
        LinkedIn, GitHub, portfolio, personal website, and other public URLs. Analysis uses public APIs
        and public pages only; LinkedIn is stored as you provided it and is not scraped.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-8">
            <SectionForm onSave={onSave} pending={pending}>
              {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
              <FieldGroup>
                <Field>
                  <FieldLabel>LinkedIn</FieldLabel>
                  <Input value={linkedin} onChange={(event) => setLinkedin(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>GitHub</FieldLabel>
                  <Input value={github} onChange={(event) => setGithub(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>Portfolio</FieldLabel>
                  <Input value={portfolio} onChange={(event) => setPortfolio(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>Personal website</FieldLabel>
                  <Input value={website} onChange={(event) => setWebsite(event.target.value)} />
                </Field>
              </FieldGroup>
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">Other professional URLs</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setOtherLinks((current) => [...current, { source: "", url: "" }])}
                  >
                    Add URL
                  </Button>
                </div>
                {otherLinks.map((item, index) => (
                  <div key={item.id ?? `new-${index}`} className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
                    <Input
                      placeholder="Label"
                      value={item.source}
                      onChange={(event) =>
                        setOtherLinks((current) =>
                          current.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, source: event.target.value } : row,
                          ),
                        )
                      }
                    />
                    <Input
                      placeholder="https://"
                      value={item.url}
                      onChange={(event) =>
                        setOtherLinks((current) =>
                          current.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, url: event.target.value } : row,
                          ),
                        )
                      }
                    />
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={() => setOtherLinks((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            </SectionForm>

            <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">Source evidence</p>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    Save URLs first. Findings stay on the source and are not added to your profile.
                  </p>
                </div>
                <Button type="button" onClick={() => void onAnalyze()} disabled={analyzing || !hasSavedUrls}>
                  {analyzing ? "Analyzing…" : "Analyze sources"}
                </Button>
              </div>
              {savedLinks.length === 0 ? (
                <p className="text-sm text-zinc-500">No saved links yet.</p>
              ) : (
                savedLinks.map((link) => (
                  <div key={link.id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                    <p className="font-medium">
                      {link.source}: {link.url || "No URL"}
                    </p>
                    <p className="mt-1 text-zinc-600 dark:text-zinc-400">{evidenceSummary(link)}</p>
                    {link.analysis?.analyzed_at ? (
                      <p className="mt-1 text-xs text-zinc-500">{link.analysis.analyzed_at}</p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
