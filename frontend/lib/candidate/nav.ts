import type { CandidateProfileGraph } from "@/lib/types";

export const CANDIDATE_NAV = [
  { href: "/candidate", label: "Dashboard" },
  { href: "/candidate/profile", label: "Personal" },
  { href: "/candidate/resume", label: "Resume" },
  { href: "/candidate/professional", label: "Professional" },
  { href: "/candidate/experience", label: "Experience" },
  { href: "/candidate/education", label: "Education" },
  { href: "/candidate/skills", label: "Skills" },
  { href: "/candidate/technologies", label: "Technologies" },
  { href: "/candidate/projects", label: "Projects" },
  { href: "/candidate/certifications", label: "Certifications" },
  { href: "/candidate/achievements", label: "Achievements" },
  { href: "/candidate/preferences", label: "Preferences" },
  { href: "/candidate/links", label: "Professional Links" },
  { href: "/candidate/review", label: "Review" },
  { href: "/candidate/intelligence", label: "Profile Intelligence" },
  { href: "/candidate/recommendations", label: "Job recommendations" },
  { href: "/candidate/settings", label: "Settings" },
] as const;

export const CANDIDATE_STEPS = [
  { href: "/candidate/profile", label: "Personal" },
  { href: "/candidate/resume", label: "Resume" },
  { href: "/candidate/professional", label: "Professional" },
  { href: "/candidate/review", label: "Review" },
  { href: "/candidate/intelligence", label: "Analyze" },
  { href: "/candidate/recommendations", label: "Jobs" },
] as const;

export function nextIncompleteStep(data: CandidateProfileGraph): string {
  const flags = data.completion.flags;
  if (!flags.profile) {
    return "/candidate/profile";
  }
  if (!flags.resume) {
    return "/candidate/resume";
  }
  if (!flags.experience && !flags.skills) {
    return "/candidate/professional";
  }
  if (!flags.links) {
    return "/candidate/links";
  }
  if (!flags.preferences) {
    return "/candidate/preferences";
  }
  if (!data.profile_ready) {
    return "/candidate/review";
  }
  return "/candidate/recommendations";
}
