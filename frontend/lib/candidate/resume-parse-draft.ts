import type {
  CandidateResumeParseResult,
  ResumeParseAchievement,
  ResumeParseCertification,
  ResumeParseEducation,
  ResumeParseExperience,
  ResumeParseProject,
  ResumeParseSkill,
  ResumeParseTechnology,
} from "@/lib/types";

function asText(value: unknown): string {
  return value == null ? "" : String(value);
}

function asYears(value: unknown): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export type ResumeExperienceDraft = ResumeParseExperience;
export type ResumeEducationDraft = ResumeParseEducation;
export type ResumeSkillDraft = ResumeParseSkill;
export type ResumeTechnologyDraft = ResumeParseTechnology;
export type ResumeProjectDraft = ResumeParseProject;
export type ResumeCertificationDraft = ResumeParseCertification;
export type ResumeAchievementDraft = ResumeParseAchievement;

export type ResumeParseDraft = {
  given_name: string;
  middle_name: string;
  family_name: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  country: string;
  current_role: string;
  summary: string;
  experience: ResumeExperienceDraft[];
  education: ResumeEducationDraft[];
  skills: ResumeSkillDraft[];
  technologies: ResumeTechnologyDraft[];
  projects: ResumeProjectDraft[];
  certifications: ResumeCertificationDraft[];
  achievements: ResumeAchievementDraft[];
};

export function emptyExperience(): ResumeExperienceDraft {
  return { title: "", company_name: "", start_date: "", end_date: "", description: "" };
}

export function emptyEducation(): ResumeEducationDraft {
  return { school: "", degree: "", field_of_study: "", start_date: "", end_date: "" };
}

export function emptySkill(): ResumeSkillDraft {
  return { skill: "", years: null };
}

export function emptyTechnology(): ResumeTechnologyDraft {
  return { name: "", years: null };
}

export function emptyProject(): ResumeProjectDraft {
  return { name: "", description: "", url: "" };
}

export function emptyCertification(): ResumeCertificationDraft {
  return { name: "", issuer: "", issued_on: "" };
}

export function emptyAchievement(): ResumeAchievementDraft {
  return { title: "", description: "", occurred_on: "" };
}

export function emptyParseDraft(): ResumeParseDraft {
  return {
    given_name: "",
    middle_name: "",
    family_name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    country: "",
    current_role: "",
    summary: "",
    experience: [],
    education: [],
    skills: [],
    technologies: [],
    projects: [],
    certifications: [],
    achievements: [],
  };
}

function toExperience(value: unknown): ResumeExperienceDraft {
  const row = asRecord(value);
  return {
    title: asText(row.title),
    company_name: asText(row.company_name),
    start_date: asText(row.start_date),
    end_date: asText(row.end_date),
    description: asText(row.description),
  };
}

function toEducation(value: unknown): ResumeEducationDraft {
  const row = asRecord(value);
  return {
    school: asText(row.school),
    degree: asText(row.degree),
    field_of_study: asText(row.field_of_study),
    start_date: asText(row.start_date),
    end_date: asText(row.end_date),
  };
}

function toSkill(value: unknown): ResumeSkillDraft {
  const row = asRecord(value);
  return { skill: asText(row.skill), years: asYears(row.years) };
}

function toTechnology(value: unknown): ResumeTechnologyDraft {
  const row = asRecord(value);
  return { name: asText(row.name), years: asYears(row.years) };
}

function toProject(value: unknown): ResumeProjectDraft {
  const row = asRecord(value);
  return {
    name: asText(row.name),
    description: asText(row.description),
    url: asText(row.url),
  };
}

function toCertification(value: unknown): ResumeCertificationDraft {
  const row = asRecord(value);
  return {
    name: asText(row.name),
    issuer: asText(row.issuer),
    issued_on: asText(row.issued_on),
  };
}

function toAchievement(value: unknown): ResumeAchievementDraft {
  const row = asRecord(value);
  return {
    title: asText(row.title),
    description: asText(row.description),
    occurred_on: asText(row.occurred_on),
  };
}

export function cloneParseDraft(source: CandidateResumeParseResult): ResumeParseDraft {
  return {
    given_name: asText(source.given_name),
    middle_name: asText(source.middle_name),
    family_name: asText(source.family_name),
    email: asText(source.email),
    phone: asText(source.phone),
    address: asText(source.address),
    city: asText(source.city),
    country: asText(source.country),
    current_role: asText(source.current_role),
    summary: asText(source.summary),
    experience: (source.experience ?? []).map(toExperience),
    education: (source.education ?? []).map(toEducation),
    skills: (source.skills ?? []).map(toSkill),
    technologies: (source.technologies ?? []).map(toTechnology),
    projects: (source.projects ?? []).map(toProject),
    certifications: (source.certifications ?? []).map(toCertification),
    achievements: (source.achievements ?? []).map(toAchievement),
  };
}

export function parseDraftToPayload(draft: ResumeParseDraft): CandidateResumeParseResult {
  return {
    ...draft,
    experience: draft.experience.map((row) => ({ ...row })),
    education: draft.education.map((row) => ({ ...row })),
    skills: draft.skills.map((row) => ({ ...row })),
    technologies: draft.technologies.map((row) => ({ ...row })),
    projects: draft.projects.map((row) => ({ ...row })),
    certifications: draft.certifications.map((row) => ({ ...row })),
    achievements: draft.achievements.map((row) => ({ ...row })),
  };
}

export function isResumeParsePendingReview(resume: {
  parse_result: CandidateResumeParseResult | null;
  processing: { status: string; applied_at?: string };
}): boolean {
  return Boolean(
    resume.parse_result && resume.processing.status === "succeeded" && !resume.processing.applied_at,
  );
}
