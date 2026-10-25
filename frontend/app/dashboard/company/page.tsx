"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getCompanyProfile, getMe, patchCompanyProfile } from "@/lib/api";
import type { MeResponse } from "@/lib/api";
import type { CompanyProfile } from "@/lib/types";

function joinList(values: string[]): string {
  return values.join(", ");
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function CompanyProfilePage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [businessDomain, setBusinessDomain] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [companySize, setCompanySize] = useState("");
  const [departments, setDepartments] = useState("");
  const [hiringDomains, setHiringDomains] = useState("");
  const [technologies, setTechnologies] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    Promise.all([getMe(), getCompanyProfile()])
      .then(([nextMe, nextProfile]) => {
        setMe(nextMe);
        setProfile(nextProfile);
        setName(nextProfile.name);
        setIndustry(nextProfile.industry);
        setBusinessDomain(nextProfile.business_domain);
        setDescription(nextProfile.description);
        setLocation(nextProfile.location);
        setCompanySize(nextProfile.company_size);
        setDepartments(joinList(nextProfile.departments));
        setHiringDomains(joinList(nextProfile.hiring_domains));
        setTechnologies(joinList(nextProfile.technologies));
      })
      .catch((caught: Error) => setError(caught.message));
  }, []);

  const canEdit = Boolean(profile?.can_edit);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!canEdit) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const updated = await patchCompanyProfile({
        name,
        industry,
        business_domain: businessDomain,
        description,
        location,
        company_size: companySize,
        departments: splitList(departments),
        hiring_domains: splitList(hiringDomains),
        technologies: splitList(technologies),
      });
      setProfile(updated);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <DashboardShell eyebrow="Company profile" title="Company Profile">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        {canEdit
          ? "Visible to recruiters at your company only."
          : "Recruiters can view this profile. Company admins can edit it."}
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <form className="flex max-w-2xl flex-col gap-4" onSubmit={onSave}>
        <FieldGroup>
          <Field>
            <FieldLabel>Company Name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canEdit} />
          </Field>
          <Field>
            <FieldLabel>Industry</FieldLabel>
            <Input value={industry} onChange={(event) => setIndustry(event.target.value)} disabled={!canEdit} />
          </Field>
          <Field>
            <FieldLabel>Business Domain</FieldLabel>
            <Input
              value={businessDomain}
              onChange={(event) => setBusinessDomain(event.target.value)}
              disabled={!canEdit}
            />
          </Field>
          <Field>
            <FieldLabel>Description</FieldLabel>
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={!canEdit}
            />
          </Field>
          <Field>
            <FieldLabel>Location</FieldLabel>
            <Input value={location} onChange={(event) => setLocation(event.target.value)} disabled={!canEdit} />
          </Field>
          <Field>
            <FieldLabel>Company Size</FieldLabel>
            <Input
              value={companySize}
              onChange={(event) => setCompanySize(event.target.value)}
              disabled={!canEdit}
              placeholder="e.g. 51-200"
            />
          </Field>
          <Field>
            <FieldLabel>Departments</FieldLabel>
            <Input
              value={departments}
              onChange={(event) => setDepartments(event.target.value)}
              disabled={!canEdit}
              placeholder="Engineering, Product, Design"
            />
          </Field>
          <Field>
            <FieldLabel>Hiring Domains</FieldLabel>
            <Input
              value={hiringDomains}
              onChange={(event) => setHiringDomains(event.target.value)}
              disabled={!canEdit}
              placeholder="Backend, Data, Mobile"
            />
          </Field>
          <Field>
            <FieldLabel>Technologies</FieldLabel>
            <Input
              value={technologies}
              onChange={(event) => setTechnologies(event.target.value)}
              disabled={!canEdit}
              placeholder="Python, TypeScript, PostgreSQL"
            />
          </Field>
        </FieldGroup>
        {canEdit ? (
          <Button type="submit" disabled={pending} className="w-fit">
            {pending ? "Saving…" : "Save profile"}
          </Button>
        ) : null}
        {me ? (
          <p className="text-xs text-zinc-500">
            Signed in as {me.email} ({me.role})
          </p>
        ) : null}
      </form>
    </DashboardShell>
  );
}
