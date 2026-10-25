import { describe, expect, it } from "vitest";

import {
  cloneParseDraft,
  emptyExperience,
  emptyParseDraft,
  isResumeParsePendingReview,
  parseDraftToPayload,
} from "../../frontend/lib/candidate/resume-parse-draft";
import type { CandidateResumeParseResult } from "../../frontend/lib/types";

const parsed: CandidateResumeParseResult = {
  given_name: "Pat",
  middle_name: "",
  family_name: "Kumar",
  email: "from-resume@example.com",
  phone: "555",
  address: "",
  city: "Bengaluru",
  country: "India",
  current_role: "Engineer",
  summary: "Builds tools.",
  experience: [{ title: "Engineer", company_name: "Acme", start_date: "2020-01-01", end_date: "", description: "" }],
  education: [],
  skills: [{ skill: "Python", years: 4 }],
  technologies: [{ name: "FastAPI", years: null }],
  projects: [],
  certifications: [],
  achievements: [],
};

describe("resume parse draft helpers", () => {
  it("clones extracted fields into an editable draft", () => {
    const draft = cloneParseDraft(parsed);
    draft.given_name = "Patricia";
    draft.experience.push(emptyExperience());
    expect(parsed.given_name).toBe("Pat");
    expect(parsed.experience).toHaveLength(1);
    expect(draft.family_name).toBe("Kumar");
    expect(draft.skills[0]?.skill).toBe("Python");
    expect(draft.experience).toHaveLength(2);
  });

  it("serializes the draft back to an apply payload", () => {
    const draft = cloneParseDraft(parsed);
    draft.skills = [{ skill: "TypeScript", years: 3 }];
    draft.experience = [];
    draft.projects.push({ name: "Job Board", description: "Built it", url: "" });
    const payload = parseDraftToPayload(draft);
    expect(payload.skills).toEqual([{ skill: "TypeScript", years: 3 }]);
    expect(payload.experience).toEqual([]);
    expect(payload.projects[0]?.name).toBe("Job Board");
    expect(payload.email).toBe("from-resume@example.com");
  });

  it("starts empty lists so the form can add rows", () => {
    const empty = emptyParseDraft();
    expect(empty.experience).toEqual([]);
    expect(empty.skills).toEqual([]);
    expect(emptyExperience().title).toBe("");
  });

  it("treats a succeeded parse as pending until applied_at is set", () => {
    expect(
      isResumeParsePendingReview({
        parse_result: parsed,
        processing: { status: "succeeded" },
      }),
    ).toBe(true);
    expect(
      isResumeParsePendingReview({
        parse_result: parsed,
        processing: { status: "succeeded", applied_at: "2026-08-16T00:00:00+00:00" },
      }),
    ).toBe(false);
    expect(
      isResumeParsePendingReview({
        parse_result: null,
        processing: { status: "succeeded" },
      }),
    ).toBe(false);
  });
});
