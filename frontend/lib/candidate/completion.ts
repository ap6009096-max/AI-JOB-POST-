export const COMPLETION_SECTIONS = [
  "profile",
  "resume",
  "experience",
  "education",
  "skills",
  "technologies",
  "projects",
  "certifications",
  "achievements",
  "links",
  "preferences",
] as const;

export type CompletionSection = (typeof COMPLETION_SECTIONS)[number];

export const SECTION_LABELS: Record<CompletionSection, string> = {
  profile: "Personal",
  resume: "Resume",
  experience: "Experience",
  education: "Education",
  skills: "Skills",
  technologies: "Technologies",
  projects: "Projects",
  certifications: "Certifications",
  achievements: "Achievements",
  links: "Professional Links",
  preferences: "Preferences",
};

export const SECTION_HREFS: Record<CompletionSection, string> = {
  profile: "/candidate/profile",
  resume: "/candidate/resume",
  experience: "/candidate/experience",
  education: "/candidate/education",
  skills: "/candidate/skills",
  technologies: "/candidate/technologies",
  projects: "/candidate/projects",
  certifications: "/candidate/certifications",
  achievements: "/candidate/achievements",
  links: "/candidate/links",
  preferences: "/candidate/preferences",
};

function filled(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === "string") {
    return value.trim().length > 0;
  }
  return true;
}

export function completionFlags(input: {
  headline?: string;
  location?: string;
  givenName?: string;
  familyName?: string;
  city?: string;
  resumeText?: string;
  resumeUrl?: string;
  experienceCount?: number;
  educationCount?: number;
  skillCount?: number;
  technologyCount?: number;
  projectCount?: number;
  certificationCount?: number;
  achievementCount?: number;
  linkCount?: number;
  openToWork?: boolean | null;
  workMode?: string | null;
}): Record<CompletionSection, boolean> {
  const namedProfile =
    filled(input.givenName) && filled(input.familyName) && filled(input.city) && filled(input.headline);
  const fallbackProfile = filled(input.headline) && filled(input.location);
  return {
    profile: namedProfile || fallbackProfile,
    resume: filled(input.resumeText) || filled(input.resumeUrl),
    experience: (input.experienceCount ?? 0) >= 1,
    education: (input.educationCount ?? 0) >= 1,
    skills: (input.skillCount ?? 0) >= 1,
    technologies: (input.technologyCount ?? 0) >= 1,
    projects: (input.projectCount ?? 0) >= 1,
    certifications: (input.certificationCount ?? 0) >= 1,
    achievements: (input.achievementCount ?? 0) >= 1,
    links: (input.linkCount ?? 0) >= 1,
    preferences:
      (input.openToWork !== null && input.openToWork !== undefined) || filled(input.workMode),
  };
}

export function completionPercent(flags: Record<string, boolean>): number {
  const done = COMPLETION_SECTIONS.filter((key) => flags[key]).length;
  return Math.round((100 * done) / COMPLETION_SECTIONS.length);
}
