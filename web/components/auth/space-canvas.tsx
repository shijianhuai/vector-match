"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const COLD = { r: 123, g: 144, b: 255 };
const WARM = { r: 255, g: 138, b: 102 };

const CLUSTER_CENTERS = [
  { x: 0.3, y: 0.3 },
  { x: 0.66, y: 0.52 },
  { x: 0.38, y: 0.74 },
];

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

interface Star {
  bx: number;
  by: number;
  z: number;
  phase: number;
  speed: number;
  drift: number;
  cluster: number;
  warm: number;
  x: number;
  y: number;
}

interface NeighborLink {
  idx: number;
  score: number;
}

type Mode = "wander" | "seek" | "lock" | "release";

interface QueryPoint {
  x: number;
  y: number;
  sx: number;
  sy: number;
  tx: number;
  ty: number;
  mode: Mode;
  t: number;
  dur: number;
  targetCluster: number;
  links: NeighborLink[];
  burst: number;
}

function buildScene(): Star[] {
  const rand = mulberry32(20260723);
  const stars: Star[] = [];
  CLUSTER_CENTERS.forEach((c, ci) => {
    for (let i = 0; i < 22; i++) {
      const angle = rand() * Math.PI * 2;
      const radius = Math.pow(rand(), 0.6) * 0.12;
      stars.push({
        bx: c.x + Math.cos(angle) * radius,
        by: c.y + Math.sin(angle) * radius * 0.82,
        z: rand(),
        phase: rand() * Math.PI * 2,
        speed: 0.12 + rand() * 0.25,
        drift: 3 + rand() * 9,
        cluster: ci,
        warm: 0,
        x: 0,
        y: 0,
      });
    }
  });
  for (let i = 0; i < 26; i++) {
    stars.push({
      bx: rand(),
      by: rand(),
      z: rand(),
      phase: rand() * Math.PI * 2,
      speed: 0.1 + rand() * 0.2,
      drift: 4 + rand() * 10,
      cluster: -1,
      warm: 0,
      x: 0,
      y: 0,
    });
  }
  return stars;
}

function pickLinks(
  stars: Star[],
  q: { x: number; y: number },
  targetCluster: number,
): NeighborLink[] {
  const rand = mulberry32(Math.floor(q.x * 1000) + 7);
  return stars
    .map((s, idx) => ({ s, idx }))
    .filter(({ s }) => s.cluster === targetCluster)
    .map(({ s, idx }) => ({
      idx,
      d: Math.hypot(s.x - q.x, s.y - q.y),
    }))
    .sort((a, b) => a.d - b.d)
    .slice(0, 3)
    .map(({ idx }, rank) => ({
      idx,
      score: 0.978 - rank * 0.023 - rand() * 0.006,
    }));
}

function drawScoreTag(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  top: boolean,
  alpha: number,
) {
  ctx.font = '500 10px "Geist Mono", ui-monospace, SFMono-Regular, monospace';
  const width = ctx.measureText(text).width;
  const padX = 5;
  const h = 15;
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.roundRect(x - width / 2 - padX, y - h / 2, width + padX * 2, h, 4);
  ctx.fillStyle = "rgba(7, 11, 20, 0.78)";
  ctx.fill();
  ctx.strokeStyle = top
    ? "rgba(255, 138, 102, 0.45)"
    : "rgba(123, 144, 255, 0.28)";
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = top ? "#FF8A66" : "#A9B8F5";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.5);
  ctx.globalAlpha = 1;
}

export function SpaceCanvas({ className }: { className?: string }) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const stars = buildScene();
    const query: QueryPoint = {
      x: 0.55,
      y: 0.25,
      sx: 0,
      sy: 0,
      tx: 0,
      ty: 0,
      mode: "wander",
      t: 0,
      dur: 1.6,
      targetCluster: 0,
      links: [],
      burst: Infinity,
    };

    let w = 0;
    let h = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    let redrawStatic: (() => void) | null = null;
    const observer = new ResizeObserver(() => {
      resize();
      redrawStatic?.();
    });
    observer.observe(canvas);
    resize();

    const margin = 24;
    const px = (nx: number) => margin + nx * (w - margin * 2);
    const py = (ny: number) => margin + ny * (h - margin * 2);

    const pointer = { x: 0, y: 0 };
    const camera = { x: 0, y: 0 };
    const onPointerMove = (e: PointerEvent) => {
      pointer.x = (e.clientX / window.innerWidth - 0.5) * 2;
      pointer.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };

    const positionStars = (time: number) => {
      for (const s of stars) {
        s.x =
          px(s.bx) +
          Math.cos(time * s.speed + s.phase) * s.drift +
          camera.x * (0.4 + s.z * 0.6);
        s.y =
          py(s.by) +
          Math.sin(time * s.speed * 0.9 + s.phase) * s.drift +
          camera.y * (0.4 + s.z * 0.6);
      }
    };

    const queryPos = (time: number) => {
      const driftX = Math.cos(time * 0.5) * 4 + camera.x * 0.9;
      const driftY = Math.sin(time * 0.42) * 4 + camera.y * 0.9;
      return { x: px(query.x) + driftX, y: py(query.y) + driftY };
    };

    const tick = (dt: number) => {
      query.t += dt;
      query.burst += dt;
      switch (query.mode) {
        case "wander": {
          if (query.t >= query.dur) {
            query.targetCluster = Math.floor(Math.random() * 3);
            const c = CLUSTER_CENTERS[query.targetCluster];
            query.sx = query.x;
            query.sy = query.y;
            query.tx = c.x + (Math.random() - 0.5) * 0.06;
            query.ty = c.y + (Math.random() - 0.5) * 0.06;
            query.mode = "seek";
            query.t = 0;
            query.dur = 0.9;
          }
          break;
        }
        case "seek": {
          const p = easeInOutCubic(Math.min(1, query.t / query.dur));
          query.x = lerp(query.sx, query.tx, p);
          query.y = lerp(query.sy, query.ty, p);
          if (query.t >= query.dur) {
            query.mode = "lock";
            query.t = 0;
            query.dur = 2.6;
            query.links = pickLinks(
              stars,
              { x: px(query.x), y: py(query.y) },
              query.targetCluster,
            );
            query.burst = 0;
          }
          break;
        }
        case "lock": {
          if (query.t >= query.dur) {
            query.mode = "release";
            query.t = 0;
            query.dur = 0.5;
          }
          break;
        }
        case "release": {
          if (query.t >= query.dur) {
            query.mode = "wander";
            query.t = 0;
            query.dur = 1.4 + Math.random() * 0.8;
            query.links = [];
          }
          break;
        }
      }
      const linked = new Set(query.links.map((l) => l.idx));
      stars.forEach((s, idx) => {
        const target = query.mode !== "wander" && linked.has(idx) ? 1 : 0;
        s.warm += (target - s.warm) * Math.min(1, dt * 6);
      });
    };

    const draw = (time: number) => {
      ctx.clearRect(0, 0, w, h);

      for (const s of stars) {
        const alpha = 0.2 + s.z * 0.45;
        const r = 1 + s.z * 1.5;
        const cr = Math.round(lerp(COLD.r, WARM.r, s.warm));
        const cg = Math.round(lerp(COLD.g, WARM.g, s.warm));
        const cb = Math.round(lerp(COLD.b, WARM.b, s.warm));
        ctx.beginPath();
        ctx.arc(s.x, s.y, r + s.warm * 0.8, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${cr}, ${cg}, ${cb}, ${alpha + s.warm * 0.4})`;
        ctx.fill();
      }

      const q = queryPos(time);
      const qx = q.x;
      const qy = q.y;

      if (query.mode === "lock" || query.mode === "release") {
        const fade =
          query.mode === "release" ? 1 - query.t / query.dur : 1;
        query.links.forEach((link, i) => {
          const appear =
            query.mode === "lock"
              ? Math.min(1, Math.max(0, query.t * 2.2 - i * 0.28))
              : 1;
          if (appear <= 0) return;
          const s = stars[link.idx];
          const ex = lerp(qx, s.x, appear);
          const ey = lerp(qy, s.y, appear);
          const gradient = ctx.createLinearGradient(qx, qy, ex, ey);
          gradient.addColorStop(0, `rgba(255, 138, 102, ${0.75 * fade})`);
          gradient.addColorStop(1, `rgba(123, 144, 255, ${0.5 * fade})`);
          ctx.beginPath();
          ctx.moveTo(qx, qy);
          ctx.lineTo(ex, ey);
          ctx.strokeStyle = gradient;
          ctx.lineWidth = 1.1;
          ctx.stroke();
          if (appear >= 1) {
            const mx = (qx + s.x) / 2;
            const my = (qy + s.y) / 2 - 8 + (i - 1) * 17;
            drawScoreTag(
              ctx,
              mx,
              my,
              link.score.toFixed(3),
              i === 0,
              fade,
            );
          }
        });
      }

      if (query.burst < 0.8) {
        const p = query.burst / 0.8;
        ctx.beginPath();
        ctx.arc(qx, qy, 6 + p * 56, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255, 138, 102, ${(1 - p) * 0.4})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      const breath = 5.5 + Math.sin(time * 2.4) * 1.6;
      ctx.beginPath();
      ctx.arc(qx, qy, breath, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255, 138, 102, 0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();

      const glow = ctx.createRadialGradient(qx, qy, 0, qx, qy, 14);
      glow.addColorStop(0, "rgba(255, 138, 102, 0.5)");
      glow.addColorStop(1, "rgba(255, 138, 102, 0)");
      ctx.beginPath();
      ctx.arc(qx, qy, 14, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(qx, qy, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#FF8A66";
      ctx.fill();
    };

    if (reduced) {
      const c = CLUSTER_CENTERS[1];
      query.x = c.x + 0.03;
      query.y = c.y - 0.02;
      query.mode = "lock";
      query.targetCluster = 1;
      positionStars(0);
      query.links = pickLinks(
        stars,
        { x: px(query.x), y: py(query.y) },
        query.targetCluster,
      );
      query.t = 1;
      for (const link of query.links) stars[link.idx].warm = 1;
      redrawStatic = () => {
        positionStars(0);
        draw(0);
      };
      redrawStatic();
      return () => {
        observer.disconnect();
      };
    }

    let raf = 0;
    let last = performance.now();
    let time = 0;
    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      time += dt;
      camera.x += (pointer.x * 9 - camera.x) * Math.min(1, dt * 3);
      camera.y += (pointer.y * 9 - camera.y) * Math.min(1, dt * 3);
      tick(dt);
      positionStars(time);
      draw(time);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    window.addEventListener("pointermove", onPointerMove);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("pointermove", onPointerMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn("h-full w-full", className)}
    />
  );
}
