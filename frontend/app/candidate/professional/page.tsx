"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { patchCandidateProfile } from "@/lib/api";

const LIST_LINKS = [
  { href: "/candidate/experience", label: "Experience" },
  { href: "/candidate/education", label: "Education" },
  { href: "/candidate/skills", label: "Skills" },
  { href: "/candidate/technologies", label: "Technologies" },
  { href: "/candidate/projects", label: "Projects" },
  { href: "/candidate/certifications", label: "Certifications" },
  { href: "/candidate/achievements", label: "Achievements" },
] as const;

export default function CandidateProfessionalPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [currentRole, setCurrentRole] = useState("");
  const [summary, setSummary] = useState("");
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setCurrentRole(data.profile.headline);
    setSummary(data.profile.summary);
  }, [data]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(await patchCandidateProfile({ headline: currentRole, summary }));
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <CandidateHeading title="Professional information">
        Headline, summary, and standing career records. Preferences and links stay on their own pages.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-6">
            <SectionForm onSave={onSave} pending={pending} saveLabel="Save professional summary">
              {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
              <FieldGroup>
                <Field>
                  <FieldLabel>Current role</FieldLabel>
                  <Input value={currentRole} onChange={(event) => setCurrentRole(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>Professional summary</FieldLabel>
                  <Textarea value={summary} onChange={(event) => setSummary(event.target.value)} />
                </Field>
              </FieldGroup>
            </SectionForm>
            <div className="grid gap-2 sm:grid-cols-2">
              {LIST_LINKS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-xl border border-zinc-200 px-4 py-3 text-sm hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                >
                  Manage {item.label.toLowerCase()}
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
