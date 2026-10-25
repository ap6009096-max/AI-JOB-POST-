"use client";

import { ShaderHero } from "@/components/brand/shader-hero";

export function AiProgressScreen({
  title,
  message,
  active,
}: {
  title: string;
  message: string;
  active: boolean;
}) {
  if (!active) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6" role="status" aria-live="polite">
      <div className="w-full max-w-xl">
        <ShaderHero shader="dots" subtle title={title} subtitle={message} />
      </div>
    </div>
  );
}
