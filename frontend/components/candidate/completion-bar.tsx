"use client";

import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";

export function CompletionBar({ percent }: { percent: number }) {
  return (
    <Progress value={percent} className="w-full items-center">
      <ProgressLabel>Profile completion</ProgressLabel>
      <ProgressValue>{(formatted) => formatted ?? `${percent}%`}</ProgressValue>
    </Progress>
  );
}
