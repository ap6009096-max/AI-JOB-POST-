import { describe, expect, it } from "vitest";

import {
  completionFlags,
  completionPercent,
} from "../../frontend/lib/candidate/completion";

describe("candidate completion helper", () => {
  it("starts at 0% when nothing is filled", () => {
    const flags = completionFlags({});
    expect(Object.values(flags).every((value) => value === false)).toBe(true);
    expect(completionPercent(flags)).toBe(0);
  });

  it("requires both headline and location for profile fallback", () => {
    expect(completionFlags({ headline: "Engineer" }).profile).toBe(false);
    expect(completionFlags({ location: "Bengaluru" }).profile).toBe(false);
    expect(completionFlags({ headline: "Engineer", location: "Bengaluru" }).profile).toBe(true);
  });

  it("counts named personal fields plus current role as profile", () => {
    expect(
      completionFlags({
        givenName: "Pat",
        familyName: "Kumar",
        city: "Bengaluru",
        headline: "Engineer",
      }).profile,
    ).toBe(true);
  });

  it("counts resume when text or url is present", () => {
    expect(completionFlags({ resumeText: "summary" }).resume).toBe(true);
    expect(completionFlags({ resumeUrl: "https://example.com/cv" }).resume).toBe(true);
  });

  it("counts preferences when openToWork or workMode is set", () => {
    expect(completionFlags({ openToWork: null }).preferences).toBe(false);
    expect(completionFlags({ openToWork: false }).preferences).toBe(true);
    expect(completionFlags({ workMode: "hybrid" }).preferences).toBe(true);
  });

  it("increases after profile and skill", () => {
    const afterProfile = completionFlags({
      headline: "Python developer",
      location: "Bengaluru",
    });
    const afterSkill = completionFlags({
      headline: "Python developer",
      location: "Bengaluru",
      skillCount: 1,
    });
    expect(completionPercent(afterProfile)).toBe(9);
    expect(completionPercent(afterSkill)).toBe(18);
    expect(completionPercent(afterSkill)).toBeGreaterThan(completionPercent(afterProfile));
  });

  it("is 100% when every section is filled", () => {
    const flags = completionFlags({
      headline: "Engineer",
      location: "Remote",
      resumeText: "resume",
      experienceCount: 1,
      educationCount: 1,
      skillCount: 1,
      technologyCount: 1,
      projectCount: 1,
      certificationCount: 1,
      achievementCount: 1,
      linkCount: 1,
      openToWork: true,
    });
    expect(completionPercent(flags)).toBe(100);
  });
});
