import { RecruiterShell } from "@/components/dashboard/recruiter-shell";
import { requireDashboardAccess } from "@/lib/auth/guard";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireDashboardAccess();
  return <RecruiterShell>{children}</RecruiterShell>;
}
