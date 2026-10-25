"use client";

import type { ReactNode } from "react";

import { DotDistortionShader } from "@/components/shaders/dot-distortion-shader";
import { LinesGradientShader } from "@/components/shaders/lines-gradient-shader";
import { SpotlightShader } from "@/components/shaders/spotlight-shader";
import { cn } from "@/lib/utils";

const SHADERS = {
  lines: LinesGradientShader,
  dots: DotDistortionShader,
  spotlight: SpotlightShader,
} as const;

export function ShaderHero({
  shader,
  eyebrow,
  title,
  subtitle,
  completion,
  actions,
  className,
  children,
  subtle,
}: {
  shader: keyof typeof SHADERS;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  completion?: number;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
  subtle?: boolean;
}) {
  const Shader = SHADERS[shader];
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-3xl border border-white/10 text-white",
        className,
      )}
    >
      <Shader className="opacity-90" {...(shader === "dots" ? { subtle } : {})} />
      <div className="relative z-10 bg-gradient-to-b from-black/20 via-black/45 to-black/75 px-6 py-10 sm:px-8 sm:py-12">
        {eyebrow ? (
          <p className="text-xs font-medium tracking-[0.22em] text-cyan-200/80 uppercase">{eyebrow}</p>
        ) : null}
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        {subtitle ? <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-200/90 sm:text-base">{subtitle}</p> : null}
        {typeof completion === "number" ? (
          <p className="mt-5 text-sm font-medium text-white">
            Profile Completion <span className="ml-2 text-2xl font-semibold tabular-nums">{completion}%</span>
          </p>
        ) : null}
        {actions ? <div className="mt-6 flex flex-wrap gap-3">{actions}</div> : null}
        {children}
      </div>
    </section>
  );
}
