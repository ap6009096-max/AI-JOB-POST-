"use client";

import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function SpotlightShader({ className }: { className?: string }) {
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
      surface.width = Math.max(1, Math.floor(surface.clientWidth * ratio));
      surface.height = Math.max(1, Math.floor(surface.clientHeight * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function paint(time: number) {
      const width = surface.clientWidth;
      const height = surface.clientHeight;
      ctx.fillStyle = "#020617";
      ctx.fillRect(0, 0, width, height);
      const drift = reduced ? 0 : Math.sin(time / 1600) * 24;
      const lights = [
        { x: width * 0.18 + drift, y: height * 0.2, color: "rgba(56, 189, 248, 0.28)" },
        { x: width * 0.82 - drift, y: height * 0.25, color: "rgba(167, 139, 250, 0.26)" },
        { x: width * 0.5, y: height * 0.9, color: "rgba(244, 114, 182, 0.18)" },
      ];
      for (const light of lights) {
        const glow = ctx.createRadialGradient(light.x, light.y, 10, light.x, light.y, Math.max(width, height) * 0.45);
        glow.addColorStop(0, light.color);
        glow.addColorStop(1, "rgba(2, 6, 23, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, width, height);
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
    return () => {
      running = false;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return <canvas ref={canvasRef} className={cn("absolute inset-0 h-full w-full", className)} aria-hidden />;
}
