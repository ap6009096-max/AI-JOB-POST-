"use client";

import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function LinesGradientShader({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const surface: HTMLCanvasElement = canvas;
    const ctx: CanvasRenderingContext2D = context;

    let frame = 0;
    let running = true;
    const reduced = prefersReducedMotion();

    function resize() {
      const ratio = window.devicePixelRatio || 1;
      const width = surface.clientWidth;
      const height = surface.clientHeight;
      surface.width = Math.max(1, Math.floor(width * ratio));
      surface.height = Math.max(1, Math.floor(height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function paint(time: number) {
      const width = surface.clientWidth;
      const height = surface.clientHeight;
      ctx.clearRect(0, 0, width, height);
      const gradient = ctx.createLinearGradient(0, 0, width, height);
      gradient.addColorStop(0, "#020617");
      gradient.addColorStop(1, "#0f172a");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      const bands = 14;
      for (let index = 0; index < bands; index += 1) {
        const wave = reduced ? 0 : Math.sin(time / 900 + index * 0.45) * 18;
        const y = (height / bands) * index + wave;
        const band = ctx.createLinearGradient(0, y, width, y + 40);
        band.addColorStop(0, "rgba(56, 189, 248, 0.05)");
        band.addColorStop(0.5, "rgba(167, 139, 250, 0.22)");
        band.addColorStop(1, "rgba(244, 114, 182, 0.08)");
        ctx.fillStyle = band;
        ctx.fillRect(0, y, width, 10);
      }
    }

    function loop(stamp: number) {
      if (!running) {
        return;
      }
      paint(stamp);
      if (!reduced) {
        frame = window.requestAnimationFrame(loop);
      }
    }

    function onVisibility() {
      running = document.visibilityState === "visible";
      if (running && !reduced) {
        frame = window.requestAnimationFrame(loop);
      }
    }

    resize();
    paint(0);
    if (!reduced) {
      frame = window.requestAnimationFrame(loop);
    }
    const observer = new ResizeObserver(resize);
    observer.observe(surface);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", resize);
    return () => {
      running = false;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className={cn("absolute inset-0 h-full w-full", className)} aria-hidden />;
}
