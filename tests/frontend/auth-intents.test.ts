import { describe, expect, it } from "vitest";

import {
  isAuthIntent,
  loginPathForIntent,
  parseAuthIntent,
  roleForIntent,
  roleMatchesIntent,
  roleMismatchMessage,
  shouldRedirectSignedInFromAuth,
} from "../../frontend/lib/auth/intents";

describe("parseAuthIntent", () => {
  it("accepts known intents", () => {
    expect(parseAuthIntent("candidate")).toBe("candidate");
    expect(parseAuthIntent("recruiter")).toBe("recruiter");
    expect(parseAuthIntent("company")).toBe("company");
    expect(isAuthIntent("company")).toBe(true);
  });

  it("falls back to candidate for unknown values", () => {
    expect(parseAuthIntent(null)).toBe("candidate");
    expect(parseAuthIntent("admin")).toBe("candidate");
    expect(isAuthIntent("admin")).toBe(false);
  });

  it("maps intents to login paths", () => {
    expect(loginPathForIntent("candidate")).toBe("/login/candidate");
    expect(loginPathForIntent("company")).toBe("/login/company");
  });
});

describe("role vs intent", () => {
  it("maps company intent to company_admin", () => {
    expect(roleForIntent("company")).toBe("company_admin");
    expect(roleForIntent("candidate")).toBe("candidate");
    expect(roleMatchesIntent("company_admin", "company")).toBe(true);
    expect(roleMatchesIntent("company_admin", "candidate")).toBe(false);
  });

  it("explains a company Google account on candidate login", () => {
    expect(roleMismatchMessage("candidate", "company_admin")).toBe(
      "This Google account is already a company admin. Use Company sign-in, or a different Google account.",
    );
  });

  it("keeps a company session on candidate login instead of bouncing to dashboard", () => {
    expect(shouldRedirectSignedInFromAuth("company_admin", "/login/company")).toBe(true);
    expect(shouldRedirectSignedInFromAuth("company_admin", "/login/candidate")).toBe(false);
    expect(shouldRedirectSignedInFromAuth("candidate", "/login/candidate")).toBe(true);
    expect(shouldRedirectSignedInFromAuth("candidate", "/signup/candidate")).toBe(true);
    expect(shouldRedirectSignedInFromAuth("recruiter", "/login/company")).toBe(false);
  });
});