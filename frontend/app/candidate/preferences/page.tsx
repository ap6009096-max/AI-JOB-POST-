"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { putCandidatePreferences } from "@/lib/api";

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function triState(value: boolean | null): "" | "yes" | "no" {
  if (value === true) {
    return "yes";
  }
  if (value === false) {
    return "no";
  }
  return "";
}

function fromTriState(value: string): boolean | null {
  if (value === "yes") {
    return true;
  }
  if (value === "no") {
    return false;
  }
  return null;
}

export default function CandidatePreferencesPage() {
  const { data, error, loading, setData } = useCandidateGraph();
  const [openToWork, setOpenToWork] = useState<"" | "yes" | "no">("");
  const [workMode, setWorkMode] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [salary, setSalary] = useState("");
  const [locations, setLocations] = useState("");
  const [roles, setRoles] = useState("");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setOpenToWork(triState(data.preferences.open_to_work));
    setWorkMode(data.preferences.work_mode ?? "");
    setEmploymentType(data.preferences.employment_type ?? "");
    setSalary(data.preferences.salary_expectation);
    setLocations(data.preferences.locations.join(", "));
    setRoles(data.preferences.desired_roles.join(", "));
    setNotes(data.preferences.notes);
  }, [data]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(
        await putCandidatePreferences({
          open_to_work: fromTriState(openToWork),
          work_mode: workMode ? (workMode as "remote" | "hybrid" | "onsite") : undefined,
          employment_type: employmentType
            ? (employmentType as "full_time" | "part_time" | "contract" | "internship" | "freelance")
            : undefined,
          salary_expectation: salary,
          locations: splitList(locations),
          desired_roles: splitList(roles),
          notes,
        }),
      );
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <CandidateHeading title="Preferences">
        Work preferences for this standing profile. Set “open to work” to count toward completion.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <SectionForm onSave={onSave} pending={pending}>
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            <FieldGroup>
              <Field>
                <FieldLabel>Open to work</FieldLabel>
                <select
                  className="h-9 w-full rounded-xl border border-input bg-input/30 px-3 text-sm"
                  value={openToWork}
                  onChange={(event) => setOpenToWork(event.target.value as "" | "yes" | "no")}
                >
                  <option value="">Not set</option>
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </Field>
              <Field>
                <FieldLabel>Remote / hybrid / on-site</FieldLabel>
                <select
                  className="h-9 w-full rounded-xl border border-input bg-input/30 px-3 text-sm"
                  value={workMode}
                  onChange={(event) => setWorkMode(event.target.value)}
                >
                  <option value="">Not set</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">On-site</option>
                </select>
              </Field>
              <Field>
                <FieldLabel>Employment type</FieldLabel>
                <select
                  className="h-9 w-full rounded-xl border border-input bg-input/30 px-3 text-sm"
                  value={employmentType}
                  onChange={(event) => setEmploymentType(event.target.value)}
                >
                  <option value="">Not set</option>
                  <option value="full_time">Full-time</option>
                  <option value="part_time">Part-time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                  <option value="freelance">Freelance</option>
                </select>
              </Field>
              <Field>
                <FieldLabel>Salary expectations</FieldLabel>
                <Input value={salary} onChange={(event) => setSalary(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Preferred locations</FieldLabel>
                <Input
                  value={locations}
                  onChange={(event) => setLocations(event.target.value)}
                  placeholder="Bengaluru, Remote"
                />
              </Field>
              <Field>
                <FieldLabel>Preferred roles</FieldLabel>
                <Input
                  value={roles}
                  onChange={(event) => setRoles(event.target.value)}
                  placeholder="Platform engineer, Backend"
                />
              </Field>
              <Field>
                <FieldLabel>Notes</FieldLabel>
                <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
              </Field>
            </FieldGroup>
          </SectionForm>
        ) : null}
      </GraphGate>
    </>
  );
}
