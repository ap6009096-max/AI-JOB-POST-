"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { patchCandidateSettings } from "@/lib/api";

export default function CandidateSettingsPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [fullName, setFullName] = useState("");
  const [status, setStatus] = useState("active");
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setFullName(data.full_name);
    setStatus(data.status === "hidden" ? "hidden" : "active");
  }, [data]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(await patchCandidateSettings({ full_name: fullName, status }));
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <CandidateHeading title="Settings">Display name and whether this profile is visible.</CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <SectionForm onSave={onSave} pending={pending}>
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            <FieldGroup>
              <Field>
                <FieldLabel>Full name</FieldLabel>
                <Input value={fullName} onChange={(event) => setFullName(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Visibility</FieldLabel>
                <select
                  className="h-9 w-full rounded-xl border border-input bg-input/30 px-3 text-sm"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="active">Active</option>
                  <option value="hidden">Hidden</option>
                </select>
              </Field>
            </FieldGroup>
          </SectionForm>
        ) : null}
      </GraphGate>
    </>
  );
}
