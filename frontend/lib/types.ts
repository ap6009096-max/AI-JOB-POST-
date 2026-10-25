export type JobRequirements = {
  skills: string[];
  experience_years: number;
  location: string;
  keywords: string[];
};

export type JobExperience = {
  years: number;
  text: string;
};

export type JobCheckStatus = "complete" | "missing" | "ambiguous" | "invalid";

export type JobPipelineCheck = {
  field: string;
  status: JobCheckStatus;
  message: string;
};

export type JobPipeline = {
  status: string;
  current_node: string;
  steps: { node: string; status: string; at: string }[];
  errors: { node: string; code: string; message: string }[];
  skipped: { node: string; reason: string }[];
  checks: JobPipelineCheck[];
  updated_at: string;
  review?: string;
};

export type Job = {
  id: string;
  company_id: string;
  title: string;
  description: string;
  location?: string;
  status?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  experience?: JobExperience;
  education?: string;
  technologies?: string[];
  responsibilities?: string[];
  salary_range?: string;
  employment_type?: string;
  seniority?: string;
  certifications?: string[];
  openings?: number;
  deadline?: string;
  requirements: JobRequirements;
  pipeline?: JobPipeline | null;
  embedding_id?: string | null;
  has_job_json?: boolean;
};

export type JobWritePayload = {
  title?: string;
  description?: string;
  location?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  experience?: JobExperience;
  education?: string;
  technologies?: string[];
  responsibilities?: string[];
  salary_range?: string;
  employment_type?: string;
  seniority?: string;
  certifications?: string[];
  openings?: number;
  deadline?: string;
};

export type JobValidateResult = {
  valid: boolean;
  errors: string[];
};

export type JobGenerateResult = {
  job: Job;
  valid: boolean;
  errors: string[];
};

export type CompanyProfile = {
  id: string;
  name: string;
  industry: string;
  business_domain: string;
  description: string;
  location: string;
  company_size: string;
  departments: string[];
  hiring_domains: string[];
  technologies: string[];
  can_edit: boolean;
};

export type CompanyMember = {
  user_id: string;
  email: string;
  role: string;
  company_id: string;
};

export type MatchingRunSummary = {
  id: string;
  job_id: string;
  job_title: string;
  track: "portal" | "internet";
  status: string;
  limit: number;
  created_at: string;
};

export type MatchNarrative = {
  explanation: string;
  evidence: string;
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
};

export type RankedCandidate = {
  rank: number;
  candidate_id: string;
  name: string;
  title: string;
  source?: string | null;
  identity_status?: string | null;
  location: string;
  url?: string;
  confidence?: number | null;
  score: number;
  parts: Record<string, number>;
  reasons: string[];
  calculation_version?: string;
  narrative?: MatchNarrative | null;
  matched_requirements?: string[];
  missing_requirements?: string[];
};

export type SourceSkip = {
  source: string;
  reason: string;
};

export type RankingRun = {
  id: string;
  job_id: string;
  track: "portal" | "internet";
  limit: number;
  results: RankedCandidate[];
  created_at: string;
  skipped?: SourceSkip[];
  sources?: string[];
};

export type MatchResult = {
  job_id: string;
  candidate_id: string;
  matching_run_id: string;
  source_type: "portal" | "internet";
  source: string;
  overall_match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  project_match_score: number;
  education_match_score: number;
  technology_match_score: number;
  semantic_match_score: number;
  location_match_score: number;
  salary_match_score: number;
  matched_requirements: string[];
  missing_requirements: string[];
  strengths: string[];
  weaknesses: string[];
  evidence: string;
  match_reasoning: string;
  recommendation: string;
  confidence_score: number;
};

export type RedditEvidence = {
  source: string;
  source_url: string;
  profile_identifier: string;
  professional_evidence: string[];
  skills: string[];
  technologies: string[];
  projects: string[];
  relevant_experience: string[];
  timestamp: string;
};

export type Candidate = {
  id: string;
  track: "portal" | "internet";
  profile: {
    name: string;
    title: string;
    skills: string[];
    experience_years: number;
    location: string;
    resume_summary: string;
    source?: string;
    url?: string;
    identity_status?: string;
    reddit_evidence?: RedditEvidence;
  };
};

export type ResumeParseExperience = {
  title: string;
  company_name: string;
  start_date: string;
  end_date: string;
  description: string;
};

export type ResumeParseEducation = {
  school: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date: string;
};

export type ResumeParseSkill = {
  skill: string;
  years: number | null;
};

export type ResumeParseTechnology = {
  name: string;
  years: number | null;
};

export type ResumeParseProject = {
  name: string;
  description: string;
  url: string;
};

export type ResumeParseCertification = {
  name: string;
  issuer: string;
  issued_on: string;
};

export type ResumeParseAchievement = {
  title: string;
  description: string;
  occurred_on: string;
};

export type CandidateResumeParseResult = {
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
  experience: ResumeParseExperience[];
  education: ResumeParseEducation[];
  skills: ResumeParseSkill[];
  technologies: ResumeParseTechnology[];
  projects: ResumeParseProject[];
  certifications: ResumeParseCertification[];
  achievements: ResumeParseAchievement[];
};

export type CandidateResume = {
  text: string;
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  processing: {
    status: string;
    error: string;
    started_at: string;
    finished_at: string;
    applied_at?: string;
  };
  parse_result: CandidateResumeParseResult | null;
};

export type CandidatePreferences = {
  open_to_work: boolean | null;
  remote: boolean | null;
  work_mode: "remote" | "hybrid" | "onsite" | null;
  salary_expectation: string;
  employment_type: "full_time" | "part_time" | "contract" | "internship" | "freelance" | null;
  locations: string[];
  desired_roles: string[];
  notes: string;
};

export type CandidatePersonal = {
  given_name: string;
  middle_name: string;
  family_name: string;
  email: string;
  phone: string;
  country: string;
  city: string;
  address: string;
};

export type CandidateExperienceItem = {
  id: string;
  company_name: string;
  title: string;
  start_date: string | null;
  end_date: string | null;
  description: string;
};

export type CandidateEducationItem = {
  id: string;
  school: string;
  degree: string;
  field_of_study: string;
  start_date: string | null;
  end_date: string | null;
};

export type CandidateSkillItem = {
  id: string;
  skill: string;
  years: number | null;
};

export type CandidateProjectItem = {
  id: string;
  name: string;
  description: string;
  url: string | null;
};

export type CandidateCertificationItem = {
  id: string;
  name: string;
  issuer: string;
  issued_on: string | null;
};

export type CandidateLinkAnalysis = {
  url: string;
  analyzed_at: string;
  provenance: string;
  fetch_status: string;
  skip_reason: string;
  evidence: Record<string, unknown>;
  analysis: Record<string, unknown>;
};

export type CandidateLinkItem = {
  id: string;
  source: string;
  url: string | null;
  created_at?: string;
  updated_at?: string;
  analysis?: CandidateLinkAnalysis | null;
};

export type CandidateTechnologyItem = {
  id: string;
  name: string;
  years: number | null;
};

export type CandidateAchievementItem = {
  id: string;
  title: string;
  description: string;
  occurred_on: string | null;
};

export type CandidateProfessionalLinks = {
  linkedin: string;
  github: string;
  portfolio: string;
  website: string;
  other: CandidateLinkItem[];
};

export type CandidateProfileGraph = {
  id: string;
  full_name: string;
  email: string;
  status: string;
  personal: CandidatePersonal;
  profile: {
    headline: string;
    summary: string;
    location: string;
  };
  resume: CandidateResume;
  preferences: CandidatePreferences;
  professional_links: CandidateProfessionalLinks;
  experience: CandidateExperienceItem[];
  education: CandidateEducationItem[];
  skills: CandidateSkillItem[];
  technologies: CandidateTechnologyItem[];
  projects: CandidateProjectItem[];
  certifications: CandidateCertificationItem[];
  achievements: CandidateAchievementItem[];
  links: CandidateLinkItem[];
  completion: {
    percent: number;
    flags: Record<string, boolean>;
  };
  intelligence: {
    missing_sections: string[];
    next_action: string;
    skill_count: number;
    experience_count: number;
  };
  pipeline?: {
    status: string;
    current_node: string;
    steps: { node: string; status: string; at: string }[];
    errors: { node: string; code: string; message: string }[];
    skipped: { node: string; reason: string }[];
    updated_at: string;
  } | null;
  master_candidate?: {
    given_name: string;
    middle_name: string;
    family_name: string;
    current_role: string;
    summary: string;
    city: string;
    country: string;
    skills: ResumeParseSkill[];
    technologies: ResumeParseTechnology[];
    experience: ResumeParseExperience[];
    education: ResumeParseEducation[];
    projects: ResumeParseProject[];
    certifications: ResumeParseCertification[];
    achievements: ResumeParseAchievement[];
    sources: Record<string, unknown>[];
    provenance: Record<string, string[]>;
    timestamp: string;
  } | null;
  embedding_id?: string | null;
  profile_ready?: boolean;
  profile_versions?: {
    id: string;
    version: number;
    source: string;
    change_summary: {
      added?: Record<string, string[]>;
      material?: boolean;
      unchanged?: boolean;
      source?: string;
    };
    created_at: string;
  }[];
};
