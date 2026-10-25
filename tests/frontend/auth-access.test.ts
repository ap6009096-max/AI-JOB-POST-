import { describe, expect, it } from "vitest";

import { canAccessPath, redirectForDenied } from "../../frontend/lib/auth/access";

describe("canAccessPath", () => {
  it("blocks candidates from recruiter dashboards", () => {
    expect(canAccessPath("candidate", "/dashboard")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/jobs/1/portal")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/company")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/jobs")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/jobs/new")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/jobs/abc/edit")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/jobs/abc/preview")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/ranking/portal")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/ranking/internet")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/runs")).toBe(false);
    expect(canAccessPath("candidate", "/dashboard/settings")).toBe(false);
    expect(redirectForDenied("candidate", "/dashboard")).toBe("/candidate");
    expect(redirectForDenied("candidate", "/dashboard/company")).toBe("/candidate");
  });

  it("blocks recruiters from candidate and admin pages", () => {
    expect(canAccessPath("recruiter", "/candidate")).toBe(false);
    expect(canAccessPath("recruiter", "/admin")).toBe(false);
    expect(redirectForDenied("recruiter", "/candidate")).toBe("/dashboard");
    expect(redirectForDenied("recruiter", "/admin")).toBe("/dashboard");
  });

  it("allows company admins on dashboard only", () => {
    expect(canAccessPath("company_admin", "/dashboard")).toBe(true);
    expect(canAccessPath("company_admin", "/candidate")).toBe(false);
    expect(canAccessPath("company_admin", "/admin")).toBe(false);
  });

  it("allows platform admins on admin and dashboard", () => {
    expect(canAccessPath("platform_admin", "/admin")).toBe(true);
    expect(canAccessPath("platform_admin", "/dashboard")).toBe(true);
  });

  it("sends anonymous dashboard visitors to company login", () => {
    expect(canAccessPath(null, "/dashboard")).toBe(false);
    expect(redirectForDenied(null, "/dashboard")).toBe("/login/company");
    expect(redirectForDenied(null, "/candidate")).toBe("/login/candidate");
  });
});
