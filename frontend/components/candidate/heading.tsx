"use client";

import type { ReactNode } from "react";

export function CandidateHeading({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {children ? (
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{children}</p>
      ) : null}
    </div>
  );
}

export function GraphGate({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: string | null;
  children: ReactNode;
}) {
  if (loading) {
    return <p className="text-sm text-zinc-500">Loading profile…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  return children;
}
