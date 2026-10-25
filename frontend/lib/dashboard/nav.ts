export const COMPANY_NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/company", label: "Company Profile" },
  { href: "/dashboard/jobs", label: "Jobs" },
  { href: "/dashboard/jobs/new", label: "Create Job" },
  { href: "/dashboard/ranking/portal", label: "Portal Ranking" },
  { href: "/dashboard/ranking/internet", label: "Internet Talent Search" },
  { href: "/dashboard/runs", label: "Matching Runs" },
  { href: "/dashboard/settings", label: "Settings" },
] as const;

export function isDashboardNavActive(href: string, pathname: string): boolean {
  if (href === "/dashboard") {
    return pathname === "/dashboard";
  }
  if (href === "/dashboard/jobs") {
    return (
      pathname === "/dashboard/jobs" ||
      /\/dashboard\/jobs\/[^/]+\/(edit|preview)(\/|$)/.test(pathname)
    );
  }
  if (href === "/dashboard/jobs/new") {
    return pathname.startsWith("/dashboard/jobs/new");
  }
  if (href === "/dashboard/ranking/portal") {
    return pathname.startsWith("/dashboard/ranking/portal") || /\/dashboard\/jobs\/[^/]+\/portal/.test(pathname);
  }
  if (href === "/dashboard/ranking/internet") {
    return (
      pathname.startsWith("/dashboard/ranking/internet") || /\/dashboard\/jobs\/[^/]+\/internet/.test(pathname)
    );
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
