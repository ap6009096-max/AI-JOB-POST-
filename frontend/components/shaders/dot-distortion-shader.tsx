"use client";

import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function DotDistortionShader({ className, subtle = false }: { className?: string; subtle?: boolean }) {
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
    const mouse = { x: -9999, y: -9999 };
    const gap = subtle ? 22 : 18;

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
      for (let x = gap; x < width; x += gap) {
        for (let y = gap; y < height; y += gap) {
          const dx = x - mouse.x;
          const dy = y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const push = reduced || dist > 90 ? 0 : ((90 - dist) / 90) * 10;
          const px = x + (dx === 0 ? 0 : (dx / dist) * push);
          const py = y + (dy === 0 ? 0 : (dy / dist) * push);
          const glow = reduced ? 0.35 : 0.28 + Math.sin(time / 700 + x * 0.02 + y * 0.02) * 0.18;
          ctx.fillStyle = `rgba(125, 211, 252, ${glow})`;
          ctx.beginPath();
          ctx.arc(px, py, subtle ? 1.1 : 1.4, 0, Math.PI * 2);
          ctx.fill();
        }
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

    function onMove(event: PointerEvent) {
      const box = surface.getBoundingClientRect();
      mouse.x = event.clientX - box.left;
      mouse.y = event.clientY - box.top;
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
    surface.addEventListener("pointermove", onMove);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      running = false;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      surface.removeEventListener("pointermove", onMove);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [subtle]);

  return <canvas ref={canvasRef} className={cn("absolute inset-0 h-full w-full", className)} aria-hidden />;
}
