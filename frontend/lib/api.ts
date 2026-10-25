import { appConfig, isSupabaseConfigured } from "@/lib/config";
import { createClient } from "@/lib/supabase/client";
import type {
  Candidate,
  CandidateAchievementItem,
  CandidateCertificationItem,
  CandidateEducationItem,
  CandidateExperienceItem,
  CandidateLinkItem,
  CandidateProfileGraph,
  CandidateProjectItem,
  CandidateResumeParseResult,
  CandidateSkillItem,
  CandidateTechnologyItem,
  CompanyMember,
  CompanyProfile,
  Job,
  JobGenerateResult,
  JobValidateResult,
  JobWritePayload,
  MatchingRunSummary,
  RankingRun,
  MatchResult,
} from "@/lib/types";

async function authHeaders(json = true): Promise<HeadersInit> {
  const headers: Record<string, string> = {};
  if (json) {
    headers["Content-Type"] = "application/json";
  }
  if (!isSupabaseConfigured()) {
    return headers;
  }
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  if (data.session?.access_token) {
    headers.Authorization = `Bearer ${data.session.access_token}`;
  }
  return headers;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${appConfig.apiUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        ...(await authHeaders()),
        ...init?.headers,
      },
    });
  } catch {
    throw new Error(
      `Cannot reach the API at ${appConfig.apiUrl}. Start the backend (uvicorn on port 8000) and try again.`,
    );
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response, path));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function errorMessage(response: Response, path: string): Promise<string> {
  const fallback = `Request failed (${response.status}) ${path}`;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string") {
          return first.msg;
        }
      }
      if (detail && typeof detail === "object" && "errors" in detail) {
        const errors = (detail as { errors: unknown }).errors;
        if (Array.isArray(errors) && errors.every((item) => typeof item === "string")) {
          return errors.join(" ");
        }
      }
    }
  } catch {
    // Non-JSON error body.
  }
  return fallback;
}

export type MeResponse = {
  id: string;
  email: string;
  full_name: string;
  role: string | null;
  status: string;
  memberships: { company_id: string; role: string }[];
};

export function getMe() {
  return api<MeResponse>("/v1/me");
}

export function bootstrapAuth(body: {
  intent: "candidate" | "recruiter" | "company";
  company_name?: string;
  full_name?: string;
}) {
  return api<MeResponse>("/v1/auth/bootstrap", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listJobs() {
  return api<Job[]>("/v1/jobs");
}

export function createJob(body: JobWritePayload) {
  return api<Job>("/v1/jobs", { method: "POST", body: JSON.stringify(body) });
}

export function generateJob(prompt: string) {
  return api<JobGenerateResult>("/v1/jobs/generate", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function getJob(jobId: string) {
  return api<Job>(`/v1/jobs/${jobId}`);
}

export function patchJob(jobId: string, body: JobWritePayload) {
  return api<Job>(`/v1/jobs/${jobId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function validateJob(jobId: string) {
  return api<JobValidateResult>(`/v1/jobs/${jobId}/validate`, { method: "POST" });
}

export function publishJob(jobId: string) {
  return api<Job>(`/v1/jobs/${jobId}/publish`, { method: "POST" });
}

export function runJobPipeline(jobId: string) {
  return api<Job>(`/v1/jobs/${jobId}/pipeline`, { method: "POST" });
}

export function refreshJobEmbedding(jobId: string) {
  return api<{ embedding_id: string }>(`/v1/jobs/${jobId}/embedding`, { method: "POST" });
}

export function getCompanyProfile() {
  return api<CompanyProfile>("/v1/companies/current");
}

export function patchCompanyProfile(body: Partial<Omit<CompanyProfile, "id" | "can_edit">>) {
  return api<CompanyProfile>("/v1/companies/current", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function listCompanyMembers() {
  return api<CompanyMember[]>("/v1/companies/current/members");
}

export function addCompanyMember(email: string, companyId?: string) {
  return api<CompanyMember>("/v1/companies/current/members", {
    method: "POST",
    body: JSON.stringify({ email, company_id: companyId }),
  });
}

export function listMatchingRuns() {
  return api<MatchingRunSummary[]>("/v1/companies/current/matching-runs");
}

export function listPortalCandidates() {
  return api<Candidate[]>("/v1/candidates/portal");
}

export function listExternalCandidates() {
  return api<Candidate[]>("/v1/candidates/external");
}

export function getPortalCandidate(id: string) {
  return api<Candidate>(`/v1/candidates/portal/${id}`);
}

export function getExternalCandidate(id: string) {
  return api<Candidate>(`/v1/candidates/external/${id}`);
}

export function rankPortal(jobId: string, limit: number) {
  return api<RankingRun>(`/v1/jobs/${jobId}/rank/portal?limit=${limit}`, { method: "POST" });
}

export async function getLatestPortalRank(jobId: string): Promise<RankingRun | null> {
  const path = `/v1/jobs/${jobId}/rank/portal/latest`;
  const response = await fetch(`${appConfig.apiUrl}${path}`, {
    headers: await authHeaders(false),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) ${path}`);
  }
  return response.json() as Promise<RankingRun>;
}

export function rankInternet(jobId: string, limit: number) {
  return api<RankingRun>(`/v1/jobs/${jobId}/rank/internet?limit=${limit}`, { method: "POST" });
}

export async function getLatestInternetRank(jobId: string): Promise<RankingRun | null> {
  const path = `/v1/jobs/${jobId}/rank/internet/latest`;
  const response = await fetch(`${appConfig.apiUrl}${path}`, {
    headers: await authHeaders(false),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) ${path}`);
  }
  return response.json() as Promise<RankingRun>;
}

async function getMatchDetails(path: string): Promise<MatchResult | null> {
  const response = await fetch(`${appConfig.apiUrl}${path}`, {
    headers: await authHeaders(false),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) ${path}`);
  }
  return response.json() as Promise<MatchResult>;
}

export function getPortalMatchDetails(jobId: string, candidateId: string) {
  return getMatchDetails(`/v1/jobs/${jobId}/rank/portal/candidates/${candidateId}`);
}

export function getInternetMatchDetails(jobId: string, candidateId: string) {
  return getMatchDetails(`/v1/jobs/${jobId}/rank/internet/candidates/${candidateId}`);
}

export function getCandidateGraph() {
  return api<CandidateProfileGraph>("/v1/me/candidate");
}

export function patchCandidateProfile(body: {
  headline?: string;
  summary?: string;
  location?: string;
}) {
  return api<CandidateProfileGraph>("/v1/me/candidate/profile", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function patchCandidatePersonal(body: {
  given_name?: string;
  middle_name?: string;
  family_name?: string;
  phone?: string;
  country?: string;
  city?: string;
  address?: string;
}) {
  return api<CandidateProfileGraph>("/v1/me/candidate/personal", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function putCandidateResume(body: { text: string; url: string }) {
  return api<CandidateProfileGraph>("/v1/me/candidate/resume", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function uploadCandidateResume(file: File) {
  const path = "/v1/me/candidate/resume/upload";
  const form = new FormData();
  form.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${appConfig.apiUrl}${path}`, {
      method: "POST",
      headers: await authHeaders(false),
      body: form,
    });
  } catch {
    throw new Error(
      `Cannot reach the API at ${appConfig.apiUrl}. Start the backend (uvicorn on port 8000) and try again.`,
    );
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response, path));
  }
  return response.json() as Promise<CandidateProfileGraph>;
}

export function applyCandidateResumeParse(body?: CandidateResumeParseResult) {
  return api<CandidateProfileGraph>("/v1/me/candidate/resume/apply", {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function putCandidatePreferences(body: {
  open_to_work?: boolean | null;
  remote?: boolean | null;
  work_mode?: "remote" | "hybrid" | "onsite" | null;
  salary_expectation?: string;
  employment_type?: "full_time" | "part_time" | "contract" | "internship" | "freelance" | null;
  locations?: string[];
  desired_roles?: string[];
  notes?: string;
}) {
  return api<CandidateProfileGraph>("/v1/me/candidate/preferences", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function putCandidateProfessionalLinks(body: {
  linkedin: string;
  github: string;
  portfolio: string;
  website: string;
  other: { id?: string; source: string; url?: string | null }[];
}) {
  return api<CandidateProfileGraph>("/v1/me/candidate/professional-links", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function analyzeCandidateSources() {
  return api<CandidateProfileGraph>("/v1/me/candidate/sources/analyze", { method: "POST" });
}

export function runCandidatePipeline() {
  return api<CandidateProfileGraph>("/v1/me/candidate/pipeline", { method: "POST" });
}

export function finalizeCandidateProfile() {
  return api<CandidateProfileGraph>("/v1/me/candidate/finalize", { method: "POST" });
}

export type JobRecommendation = {
  rank: number;
  job_id: string;
  title: string;
  location: string;
  company_id: string;
  score: number;
  parts: Record<string, number>;
  matched_requirements: string[];
  missing_requirements: string[];
  calculation_version: string;
};

export function listCandidateRecommendations() {
  return api<JobRecommendation[]>("/v1/me/candidate/recommendations");
}

export function patchCandidateSettings(body: { full_name?: string; status?: string }) {
  return api<CandidateProfileGraph>("/v1/me/candidate/settings", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

function collection<T>(path: string) {
  return {
    create(body: unknown) {
      return api<T>(`/v1/me/candidate/${path}`, { method: "POST", body: JSON.stringify(body) });
    },
    update(id: string, body: unknown) {
      return api<T>(`/v1/me/candidate/${path}/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    remove(id: string) {
      return api<void>(`/v1/me/candidate/${path}/${id}`, { method: "DELETE" });
    },
  };
}

export const candidateExperienceApi = collection<CandidateExperienceItem>("experience");
export const candidateEducationApi = collection<CandidateEducationItem>("education");
export const candidateSkillsApi = collection<CandidateSkillItem>("skills");
export const candidateProjectsApi = collection<CandidateProjectItem>("projects");
export const candidateCertificationsApi = collection<CandidateCertificationItem>("certifications");
export const candidateLinksApi = collection<CandidateLinkItem>("links");
export const candidateTechnologiesApi = collection<CandidateTechnologyItem>("technologies");
export const candidateAchievementsApi = collection<CandidateAchievementItem>("achievements");
