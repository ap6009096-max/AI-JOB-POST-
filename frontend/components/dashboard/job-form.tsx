"use client";

import type { FormEvent, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Job, JobWritePayload } from "@/lib/types";

export type JobFormValues = {
  title: string;
  description: string;
  requiredSkills: string;
  preferredSkills: string;
  experienceYears: string;
  experienceText: string;
  education: string;
  technologies: string;
  responsibilities: string;
  location: string;
  salaryRange: string;
  employmentType: string;
  seniority: string;
  certifications: string;
  openings: string;
  deadline: string;
};

const selectClass = "h-9 w-full rounded-xl border border-input bg-input/30 px-3 text-sm";

export const EMPTY_JOB_FORM: JobFormValues = {
  title: "",
  description: "",
  requiredSkills: "",
  preferredSkills: "",
  experienceYears: "0",
  experienceText: "",
  education: "",
  technologies: "",
  responsibilities: "",
  location: "",
  salaryRange: "",
  employmentType: "",
  seniority: "",
  certifications: "",
  openings: "1",
  deadline: "",
};

export function splitList(value: string): string[] {
  return value
    .replace(/\n/g, ",")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function joinList(values: string[] | undefined): string {
  return (values ?? []).join(", ");
}

export function valuesFromJob(job: Job): JobFormValues {
  return {
    title: job.title ?? "",
    description: job.description ?? "",
    requiredSkills: joinList(job.required_skills ?? job.requirements?.skills),
    preferredSkills: joinList(job.preferred_skills),
    experienceYears: String(job.experience?.years ?? job.requirements?.experience_years ?? 0),
    experienceText: job.experience?.text ?? "",
    education: job.education ?? "",
    technologies: joinList(job.technologies),
    responsibilities: joinList(job.responsibilities),
    location: job.location ?? job.requirements?.location ?? "",
    salaryRange: job.salary_range ?? "",
    employmentType: job.employment_type ?? "",
    seniority: job.seniority ?? "",
    certifications: joinList(job.certifications),
    openings: String(job.openings ?? 1),
    deadline: job.deadline ?? "",
  };
}

export function payloadFromValues(values: JobFormValues): JobWritePayload {
  return {
    title: values.title.trim(),
    description: values.description,
    location: values.location.trim(),
    required_skills: splitList(values.requiredSkills),
    preferred_skills: splitList(values.preferredSkills),
    experience: {
      years: Number(values.experienceYears) || 0,
      text: values.experienceText,
    },
    education: values.education,
    technologies: splitList(values.technologies),
    responsibilities: splitList(values.responsibilities),
    salary_range: values.salaryRange,
    employment_type: values.employmentType,
    seniority: values.seniority,
    certifications: splitList(values.certifications),
    openings: Math.max(1, Number(values.openings) || 1),
    deadline: values.deadline,
  };
}

export function JobForm({
  values,
  onChange,
  onSave,
  pending,
  saveLabel = "Save Draft",
  children,
}: {
  values: JobFormValues;
  onChange: (next: JobFormValues) => void;
  onSave: (event: FormEvent) => void | Promise<void>;
  pending?: boolean;
  saveLabel?: string;
  children?: ReactNode;
}) {
  function set<K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) {
    onChange({ ...values, [key]: value });
  }

  return (
    <form className="flex max-w-2xl flex-col gap-4" onSubmit={onSave}>
      <FieldGroup>
        <Field>
          <FieldLabel>Job Title</FieldLabel>
          <Input value={values.title} onChange={(event) => set("title", event.target.value)} required />
        </Field>
        <Field>
          <FieldLabel>Job Description</FieldLabel>
          <Textarea value={values.description} onChange={(event) => set("description", event.target.value)} />
        </Field>
        <Field>
          <FieldLabel>Required Skills</FieldLabel>
          <Input
            value={values.requiredSkills}
            onChange={(event) => set("requiredSkills", event.target.value)}
            placeholder="Python, TypeScript, React"
          />
        </Field>
        <Field>
          <FieldLabel>Preferred Skills</FieldLabel>
          <Input
            value={values.preferredSkills}
            onChange={(event) => set("preferredSkills", event.target.value)}
            placeholder="GraphQL, Kubernetes"
          />
        </Field>
        <Field>
          <FieldLabel>Experience</FieldLabel>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              type="number"
              min={0}
              step="0.5"
              value={values.experienceYears}
              onChange={(event) => set("experienceYears", event.target.value)}
              placeholder="Years"
            />
            <Input
              value={values.experienceText}
              onChange={(event) => set("experienceText", event.target.value)}
              placeholder="e.g. 5+ years backend"
            />
          </div>
        </Field>
        <Field>
          <FieldLabel>Education</FieldLabel>
          <Input
            value={values.education}
            onChange={(event) => set("education", event.target.value)}
            placeholder="Bachelor's in Computer Science"
          />
        </Field>
        <Field>
          <FieldLabel>Technologies</FieldLabel>
          <Input
            value={values.technologies}
            onChange={(event) => set("technologies", event.target.value)}
            placeholder="PostgreSQL, FastAPI, Next.js"
          />
        </Field>
        <Field>
          <FieldLabel>Responsibilities</FieldLabel>
          <Textarea
            value={values.responsibilities}
            onChange={(event) => set("responsibilities", event.target.value)}
            placeholder="Own APIs, review hiring workflows"
          />
        </Field>
        <Field>
          <FieldLabel>Location</FieldLabel>
          <Input value={values.location} onChange={(event) => set("location", event.target.value)} />
        </Field>
        <Field>
          <FieldLabel>Salary Range</FieldLabel>
          <Input
            value={values.salaryRange}
            onChange={(event) => set("salaryRange", event.target.value)}
            placeholder="₹20–30 LPA"
          />
        </Field>
        <Field>
          <FieldLabel>Employment Type</FieldLabel>
          <select
            className={selectClass}
            value={values.employmentType}
            onChange={(event) => set("employmentType", event.target.value)}
          >
            <option value="">Select</option>
            <option value="full_time">Full time</option>
            <option value="part_time">Part time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
            <option value="freelance">Freelance</option>
          </select>
        </Field>
        <Field>
          <FieldLabel>Seniority</FieldLabel>
          <select
            className={selectClass}
            value={values.seniority}
            onChange={(event) => set("seniority", event.target.value)}
          >
            <option value="">Select</option>
            <option value="intern">Intern</option>
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
            <option value="staff">Staff</option>
            <option value="principal">Principal</option>
          </select>
        </Field>
        <Field>
          <FieldLabel>Certifications</FieldLabel>
          <Input
            value={values.certifications}
            onChange={(event) => set("certifications", event.target.value)}
            placeholder="AWS, Kubernetes"
          />
        </Field>
        <Field>
          <FieldLabel>Openings</FieldLabel>
          <Input
            type="number"
            min={1}
            value={values.openings}
            onChange={(event) => set("openings", event.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel>Deadline</FieldLabel>
          <Input type="date" value={values.deadline} onChange={(event) => set("deadline", event.target.value)} />
        </Field>
      </FieldGroup>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={pending || !values.title.trim()}>
          {pending ? "Saving…" : saveLabel}
        </Button>
        {children}
      </div>
    </form>
  );
}
