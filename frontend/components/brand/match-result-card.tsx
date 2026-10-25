import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const BARS: { key: string; label: string }[] = [
  { key: "skills", label: "Skills" },
  { key: "experience", label: "Experience" },
  { key: "projects", label: "Projects" },
  { key: "education", label: "Education" },
  { key: "technology", label: "Technology" },
];

function percent(value: number | undefined): string {
  return `${Math.round((value ?? 0) * 1000) / 10}%`;
}

export function MatchResultCard({
  rank,
  name,
  subtitle,
  score,
  parts,
  matched,
  missing,
  profileHref,
  detailsHref,
}: {
  rank: number;
  name: string;
  subtitle?: string;
  score: number;
  parts: Record<string, number>;
  matched?: string[];
  missing?: string[];
  profileHref?: string;
  detailsHref?: string;
}) {
  return (
    <Card className="border-zinc-200/80 shadow-sm transition hover:shadow-md">
      <CardContent className="flex flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">#{rank}</p>
            <h3 className="mt-1 text-lg font-semibold tracking-tight">{name}</h3>
            {subtitle ? <p className="mt-1 text-sm text-zinc-500">{subtitle}</p> : null}
          </div>
          <p className="text-right text-2xl font-semibold tabular-nums">{percent(score)} MATCH</p>
        </div>
        <div className="flex flex-col gap-2">
          {BARS.map((bar) => (
            <div key={bar.key} className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-3 text-sm">
              <span className="text-zinc-500">{bar.label}</span>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                <div
                  className="h-full rounded-full bg-zinc-900 dark:bg-zinc-100"
                  style={{ width: `${Math.max(0, Math.min(100, (parts[bar.key] ?? 0) * 100))}%` }}
                />
              </div>
              <span className="text-right tabular-nums">{percent(parts[bar.key])}</span>
            </div>
          ))}
        </div>
        {matched && matched.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {matched.slice(0, 8).map((item) => (
              <span key={item} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-800">
                {item}
              </span>
            ))}
          </div>
        ) : null}
        {missing && missing.length > 0 ? (
          <p className="text-sm text-zinc-600">Missing: {missing.slice(0, 6).join(", ")}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {profileHref ? (
            <Link href={profileHref} className={cn(buttonVariants({ variant: "outline" }), "inline-flex")}>
              View Profile
            </Link>
          ) : null}
          {detailsHref ? (
            <Link href={detailsHref} className={cn(buttonVariants(), "inline-flex")}>
              Match Details
            </Link>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
