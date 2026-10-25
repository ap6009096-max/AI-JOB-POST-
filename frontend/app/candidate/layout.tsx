import { CandidateShell } from "@/components/candidate/shell";
import { requireCandidateAccess } from "@/lib/auth/guard";

export default async function CandidateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireCandidateAccess();
  return <CandidateShell>{children}</CandidateShell>;
}
